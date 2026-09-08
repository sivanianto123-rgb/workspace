"""Build a baseline training set and a drifting "production stream" from a public dataset.

BASE DATASET
------------
Breast Cancer Wisconsin (Diagnostic) - bundled with scikit-learn
(:func:`sklearn.datasets.load_breast_cancer`), originally from the UCI ML
repository. 569 rows, 30 numeric features computed from digitized images of a
fine-needle aspirate of a breast mass. Real-world meaning: predict whether a
tumour is malignant (target = 0) or benign (target = 1). A genuine,
well-understood binary-classification problem with entirely numeric features,
which makes covariate drift easy to inject and verify.

If ``data/raw/breast_cancer.csv`` already exists it is reused; otherwise it is
written from the scikit-learn copy (no network required).

WHAT THIS SCRIPT PRODUCES
-------------------------
  data/baseline/baseline.csv        60% sample, no drift - used to train run #1
  data/stream/batch_001.csv ...     12 sequential "production" batches (50 rows each)
  data/stream/manifest.json         machine-readable description of injected drift

INJECTED DRIFT  (verify your detector against exactly this)
----------------------------------------------------------
Batches 1-3 are CLEAN: sampled (with replacement) from the 40% hold-out pool with
no modification. A good detector should report every feature "stable" here.

From batch 4 on, drift is injected into 12 of the 30 features (the other 18 are
untouched negative controls). Each drifted feature has its own onset batch and
its own ramp level ``k = max(0, batch_number - onset + 1)``, so the *number* of
features showing significant drift grows gradually over the stream rather than
all at once. Transforms, where ``mu`` / ``sigma`` are the baseline mean / std:

  mean_shift_up      : x' = x + rate * k * sigma
  mean_shift_down    : x' = x - rate * k * sigma
  variance_inflation : x' = mu + (x - mu) * (1 + rate * k)   (mean unchanged)

  feature                 transform            rate   onset(batch)
  ---------------------------------------------------------------
  mean_radius             mean_shift_up        0.30   4
  mean_perimeter          mean_shift_up        0.28   4
  mean_area               mean_shift_up        0.28   4
  mean_concavity          mean_shift_up        0.26   4
  worst_radius            mean_shift_up        0.28   4
  worst_perimeter         mean_shift_up        0.28   4
  mean_texture            variance_inflation   0.35   6
  mean_compactness        mean_shift_up        0.26   6
  worst_area              mean_shift_up        0.26   6
  worst_concavity         mean_shift_up        0.24   6
  worst_concave_points    mean_shift_down      0.24   8
  area_error              variance_inflation   0.35   8

Batches 7-12 add MILD CONCEPT DRIFT on top: each row's label is flipped with
probability ``p_flip = 0.04 * (batch_number - 6)`` (0.04 at batch 7 -> 0.24 at
batch 12). This degrades the feature/label relationship and drags model accuracy
down even where covariate drift alone is subtle.

Net effect (default config, DRIFT_WINDOW_SIZE=300, threshold 0.30): the drift
check reports ~0.07 significant-fraction after batch 3 (clean), ~0.17 after
batch 6 (building), and ~0.33 after batch 9 -- which crosses the auto-retrain
threshold, so the demo shows a real drift-triggered retrain around batch 9.

Caveat: a drift check run against a very small window (e.g. a single 50-row
batch) is noisy and will over-report drift; the 300-row rolling window used by
``/api/drift-check`` is what makes the numbers above stable.

Everything is seeded (SEED = 42) so runs are reproducible.
"""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime, timezone

import numpy as np
import pandas as pd
from sklearn.datasets import load_breast_cancer

from config import Config

SEED = 42

RAW_DIR = Config.RAW_DATA_DIR
BASELINE_DIR = os.path.join(Config.DATA_DIR, "baseline")
STREAM_DIR = Config.STREAM_DATA_DIR
RAW_CSV = os.path.join(RAW_DIR, "breast_cancer.csv")

TARGET_COLUMN = "target"

# feature -> {kind, rate, onset}. `onset` is the 1-based batch number at which
# this feature starts drifting; ramp level k = max(0, batch_number - onset + 1).
DRIFT_SPEC = {
    "mean_radius": {"kind": "mean_shift_up", "rate": 0.30, "onset": 4},
    "mean_perimeter": {"kind": "mean_shift_up", "rate": 0.28, "onset": 4},
    "mean_area": {"kind": "mean_shift_up", "rate": 0.28, "onset": 4},
    "mean_concavity": {"kind": "mean_shift_up", "rate": 0.26, "onset": 4},
    "worst_radius": {"kind": "mean_shift_up", "rate": 0.28, "onset": 4},
    "worst_perimeter": {"kind": "mean_shift_up", "rate": 0.28, "onset": 4},
    "mean_texture": {"kind": "variance_inflation", "rate": 0.35, "onset": 6},
    "mean_compactness": {"kind": "mean_shift_up", "rate": 0.26, "onset": 6},
    "worst_area": {"kind": "mean_shift_up", "rate": 0.26, "onset": 6},
    "worst_concavity": {"kind": "mean_shift_up", "rate": 0.24, "onset": 6},
    "worst_concave_points": {"kind": "mean_shift_down", "rate": 0.24, "onset": 8},
    "area_error": {"kind": "variance_inflation", "rate": 0.35, "onset": 8},
}
CLEAN_BATCHES = 3          # batches 1..3 are untouched
CONCEPT_DRIFT_START = 7    # batch index (1-based) where label noise begins
CONCEPT_DRIFT_RATE = 0.04  # p_flip per batch beyond (CONCEPT_DRIFT_START - 1)


def _snake(name: str) -> str:
    return name.strip().replace(" ", "_").replace("-", "_").lower()


def load_base_dataset() -> pd.DataFrame:
    """Load the raw dataset, materializing ``data/raw/breast_cancer.csv`` on first run."""
    os.makedirs(RAW_DIR, exist_ok=True)
    if os.path.exists(RAW_CSV):
        return pd.read_csv(RAW_CSV)

    bunch = load_breast_cancer(as_frame=True)
    df = bunch.frame.copy()
    df.columns = [_snake(c) for c in df.columns]
    if "target" not in df.columns:
        df["target"] = bunch.target
    df.to_csv(RAW_CSV, index=False)
    return df


def _ramp_level(batch_number: int, onset: int) -> int:
    return max(0, batch_number - onset + 1)


def _apply_covariate_drift(
    batch: pd.DataFrame, batch_number: int, baseline_stats: dict
) -> pd.DataFrame:
    """Apply every DRIFT_SPEC transform whose onset has been reached."""
    out = batch.copy()
    for feature, spec in DRIFT_SPEC.items():
        if feature not in out.columns:
            continue
        k = _ramp_level(batch_number, spec["onset"])
        if k <= 0:
            continue
        mu = baseline_stats[feature]["mean"]
        sigma = baseline_stats[feature]["std"]
        col = out[feature].to_numpy(dtype=float)
        if spec["kind"] == "mean_shift_up":
            col = col + spec["rate"] * k * sigma
        elif spec["kind"] == "mean_shift_down":
            col = col - spec["rate"] * k * sigma
        elif spec["kind"] == "variance_inflation":
            col = mu + (col - mu) * (1.0 + spec["rate"] * k)
        out[feature] = col
    return out


def _apply_concept_drift(
    batch: pd.DataFrame, batch_number: int, rng: np.random.Generator
) -> tuple[pd.DataFrame, float]:
    """Flip labels with probability that grows in later batches."""
    if batch_number < CONCEPT_DRIFT_START:
        return batch, 0.0
    p_flip = CONCEPT_DRIFT_RATE * (batch_number - (CONCEPT_DRIFT_START - 1))
    out = batch.copy()
    flip_mask = rng.random(len(out)) < p_flip
    out.loc[flip_mask, TARGET_COLUMN] = 1 - out.loc[flip_mask, TARGET_COLUMN]
    return out, float(p_flip)


def simulate(
    n_batches: int = 12,
    batch_size: int = 50,
    baseline_frac: float = 0.60,
) -> dict:
    """Generate baseline + stream files. Returns the manifest dict."""
    os.makedirs(BASELINE_DIR, exist_ok=True)
    os.makedirs(STREAM_DIR, exist_ok=True)

    df = load_base_dataset()
    rng = np.random.default_rng(SEED)

    # Split into baseline (train) and a hold-out pool that feeds the stream.
    shuffled = df.sample(frac=1.0, random_state=SEED).reset_index(drop=True)
    n_baseline = int(len(shuffled) * baseline_frac)
    baseline = shuffled.iloc[:n_baseline].reset_index(drop=True)
    pool = shuffled.iloc[n_baseline:].reset_index(drop=True)

    baseline_path = os.path.join(BASELINE_DIR, "baseline.csv")
    baseline.to_csv(baseline_path, index=False)

    feature_columns = [c for c in baseline.columns if c != TARGET_COLUMN]
    baseline_stats = {
        c: {
            "mean": float(baseline[c].mean()),
            "std": float(baseline[c].std(ddof=0)) or 1.0,
        }
        for c in feature_columns
    }

    # Clear any previous stream batches.
    for f in os.listdir(STREAM_DIR):
        if f.startswith("batch_") and f.endswith(".csv"):
            os.remove(os.path.join(STREAM_DIR, f))

    batch_records = []
    for b in range(1, n_batches + 1):
        idx = rng.integers(0, len(pool), size=batch_size)
        batch = pool.iloc[idx].reset_index(drop=True)

        active = {
            feat: _ramp_level(b, spec["onset"])
            for feat, spec in DRIFT_SPEC.items()
            if _ramp_level(b, spec["onset"]) > 0
        }
        if active:
            batch = _apply_covariate_drift(batch, b, baseline_stats)
        batch, p_flip = _apply_concept_drift(batch, b, rng)

        fname = f"batch_{b:03d}.csv"
        batch.to_csv(os.path.join(STREAM_DIR, fname), index=False)
        batch_records.append(
            {
                "batch": b,
                "file": fname,
                "rows": int(len(batch)),
                "drifting_features": sorted(active),
                "ramp_levels": {k: int(v) for k, v in sorted(active.items())},
                "concept_drift_p_flip": round(p_flip, 4),
                "clean": not active and p_flip == 0.0,
            }
        )

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "seed": SEED,
        "base_dataset": "sklearn.datasets.load_breast_cancer (UCI Breast Cancer Wisconsin Diagnostic)",
        "raw_csv": RAW_CSV,
        "baseline_csv": baseline_path,
        "baseline_rows": int(len(baseline)),
        "pool_rows": int(len(pool)),
        "target_column": TARGET_COLUMN,
        "feature_columns": feature_columns,
        "n_features": len(feature_columns),
        "clean_batches": CLEAN_BATCHES,
        "drift_spec": {
            "covariate": {
                feat: {
                    **spec,
                    "formula": _formula_for(feat, spec),
                    "baseline_mean": baseline_stats[feat]["mean"],
                    "baseline_std": baseline_stats[feat]["std"],
                }
                for feat, spec in DRIFT_SPEC.items()
            },
            "concept": {
                "starts_at_batch": CONCEPT_DRIFT_START,
                "p_flip_formula": f"{CONCEPT_DRIFT_RATE} * (batch_number - {CONCEPT_DRIFT_START - 1})",
            },
            "untouched_features": [c for c in feature_columns if c not in DRIFT_SPEC],
        },
        "batches": batch_records,
    }
    with open(os.path.join(STREAM_DIR, "manifest.json"), "w") as fh:
        json.dump(manifest, fh, indent=2)
    return manifest


def _formula_for(feature: str, spec: dict) -> str:
    if spec["kind"] == "mean_shift_up":
        return f"x' = x + {spec['rate']} * k * std({feature})"
    if spec["kind"] == "mean_shift_down":
        return f"x' = x - {spec['rate']} * k * std({feature})"
    if spec["kind"] == "variance_inflation":
        return f"x' = mean + (x - mean) * (1 + {spec['rate']} * k)"
    return "?"


def main() -> None:
    parser = argparse.ArgumentParser(description="Simulate baseline + drifting production stream")
    parser.add_argument("--batches", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--baseline-frac", type=float, default=0.60)
    args = parser.parse_args()

    manifest = simulate(
        n_batches=args.batches,
        batch_size=args.batch_size,
        baseline_frac=args.baseline_frac,
    )
    print(f"Base dataset      : {manifest['base_dataset']}")
    print(f"Baseline rows     : {manifest['baseline_rows']}  -> {manifest['baseline_csv']}")
    print(f"Stream batches    : {len(manifest['batches'])}  -> {STREAM_DIR}/batch_XXX.csv")
    print(f"Drifted features  : {len(DRIFT_SPEC)}/{manifest['n_features']}  ({', '.join(DRIFT_SPEC)})")
    print(f"Clean batches     : 1..{CLEAN_BATCHES}")
    print(f"Concept drift from: batch {CONCEPT_DRIFT_START}+")
    print(f"Manifest          : {os.path.join(STREAM_DIR, 'manifest.json')}")


if __name__ == "__main__":
    main()
