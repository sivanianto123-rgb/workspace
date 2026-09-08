"""Filesystem layout helpers for datasets and per-run artifacts.

Directory layout (all under the project root)::

    data/raw/       <name>.csv                 base dataset, as acquired
    data/baseline/  baseline.csv               training baseline (features + target)
    data/stream/    batch_001.csv ...          simulated production batches
                    manifest.json              description of injected drift
    models/         run_<id>/model.joblib      serialized sklearn Pipeline
                    run_<id>/baseline.csv      feature snapshot used for drift comparison
"""

from __future__ import annotations

import io
import os

import pandas as pd

from flask import current_app


# --- directory accessors -----------------------------------------------------

def raw_dir() -> str:
    return current_app.config["RAW_DATA_DIR"]


def stream_dir() -> str:
    return current_app.config["STREAM_DATA_DIR"]


def baseline_dir() -> str:
    path = os.path.join(current_app.config["DATA_DIR"], "baseline")
    os.makedirs(path, exist_ok=True)
    return path


def models_dir() -> str:
    return current_app.config["MODELS_DIR"]


def run_artifact_dir(run_id: int) -> str:
    path = os.path.join(models_dir(), f"run_{run_id}")
    os.makedirs(path, exist_ok=True)
    return path


def baseline_csv_path() -> str:
    return os.path.join(baseline_dir(), "baseline.csv")


def run_baseline_path(run_id: int) -> str:
    return os.path.join(run_artifact_dir(run_id), "baseline.csv")


def run_model_path(run_id: int) -> str:
    return os.path.join(run_artifact_dir(run_id), "model.joblib")


# --- loading ---------------------------------------------------------------

def load_dataframe(source) -> pd.DataFrame:
    """Load a DataFrame from a path, a list of dict records, a single record, or CSV text."""
    if isinstance(source, pd.DataFrame):
        return source
    if isinstance(source, dict):
        return pd.DataFrame([source])
    if isinstance(source, list):
        return pd.DataFrame(source)
    if isinstance(source, str):
        if os.path.exists(source):
            if source.endswith(".parquet"):
                return pd.read_parquet(source)
            if source.endswith(".json"):
                return pd.read_json(source)
            return pd.read_csv(source)
        return pd.read_csv(io.StringIO(source))
    raise ValueError(f"Unsupported dataset source: {type(source)!r}")


def list_stream_batches() -> list[str]:
    d = stream_dir()
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f)
        for f in os.listdir(d)
        if f.startswith("batch_") and f.endswith(".csv")
    )
