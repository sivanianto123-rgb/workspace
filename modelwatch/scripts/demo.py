#!/usr/bin/env python
"""End-to-end ModelWatch demo for a screen recording (runs in well under 2 minutes).

Steps
  1. Reset the database (drop + recreate all tables)
  2. Regenerate the baseline dataset + drifting production stream
  3. Launch the Flask server
  4. Train an initial model on the clean baseline           -> POST /api/train
  5. Replay production batches with gradually injected drift -> POST /api/predict/<run_id>
  6. Call the drift check as batches arrive                  -> GET  /api/drift-check/<run_id>
  7. Watch the auto-retrain fire once drift crosses 30%      -> POST /api/check-and-retrain/<run_id>

Everything is narrated to stdout so you can talk over it while recording.

    python scripts/demo.py                 # default
    python scripts/demo.py --port 5055 --delay 0.05
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

STEP = 0


def say(msg: str = "") -> None:
    print(msg, flush=True)


def step(title: str) -> None:
    global STEP
    STEP += 1
    say("\n" + "=" * 72)
    say(f"  STEP {STEP}.  {title}")
    say("=" * 72)


def reset_database() -> None:
    from app import create_app, db

    app = create_app("development")
    with app.app_context():
        db.drop_all()
        db.create_all()
    say("  · dropped and recreated all tables")


def regenerate_data() -> dict:
    from app.ml.data_simulation import DRIFT_SPEC, simulate

    manifest = simulate(n_batches=12, batch_size=50)
    say(f"  · baseline: {manifest['baseline_rows']} rows  ->  data/baseline/baseline.csv")
    say(f"  · stream  : {len(manifest['batches'])} batches ->  data/stream/batch_XXX.csv")
    say(f"  · drift injected into: {', '.join(DRIFT_SPEC)} (batches 4-12, ramping)")
    say(f"  · concept drift (label noise) from batch 7 onward")
    say(f"  · 27 other features are untouched negative controls")
    return manifest


def wait_for_health(base_url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            r = requests.get(f"{base_url}/health", timeout=2)
            if r.ok:
                say(f"  · server up: {r.json()}")
                return
        except requests.RequestException:
            pass
        time.sleep(0.3)
    raise RuntimeError("server did not become healthy in time")


def train_initial(base_url: str) -> int:
    body = {"model_type": "logistic_regression", "model_name": "tumor-classifier"}
    r = requests.post(f"{base_url}/api/train", json=body, timeout=120)
    r.raise_for_status()
    data = r.json()
    m = data["metrics"]
    say(f"  · trained run #{data['run_id']} ({data['model_type']}) on {data['n_training_rows']} rows "
        f"in {data['train_duration_seconds']:.2f}s")
    say(f"  · baseline metrics: acc={m['accuracy']:.3f}  f1={m['f1']:.3f}  auc={m['auc']:.3f}")
    return data["run_id"]


def send_batch(base_url: str, run_id: int, path: Path) -> dict:
    df = pd.read_csv(path)
    payload = {
        "records": df.drop(columns=["target"], errors="ignore").to_dict("records"),
        "actual_labels": [int(v) for v in df["target"].tolist()],
    }
    r = requests.post(f"{base_url}/api/predict/{run_id}", json=payload, timeout=60)
    r.raise_for_status()
    return r.json()


def drift_check(base_url: str, run_id: int) -> dict:
    r = requests.get(f"{base_url}/api/drift-check/{run_id}", timeout=60)
    r.raise_for_status()
    return r.json()


def check_and_retrain(base_url: str, run_id: int) -> dict:
    r = requests.post(f"{base_url}/api/check-and-retrain/{run_id}", json={}, timeout=180)
    r.raise_for_status()
    return r.json()


def accuracy_so_far(base_url: str, run_id: int, window: int = 100) -> float | None:
    r = requests.get(
        f"{base_url}/api/predictions/{run_id}", params={"limit": window, "order": "desc"}, timeout=30
    )
    r.raise_for_status()
    rows = r.json()["predictions"]
    scored = [(row["prediction"], row["actual_label"]) for row in rows if row["actual_label"] is not None]
    if not scored:
        return None
    correct = sum(1 for p, a in scored if p == a)
    return correct / len(scored)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=5057)
    parser.add_argument("--delay", type=float, default=0.15, help="pause between batches (s)")
    parser.add_argument("--keep-db", action="store_true", help="use a file DB, don't reset it")
    args = parser.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"
    os.chdir(ROOT)

    say("\n" + "#" * 72)
    say("#  ModelWatch — automatic drift detection & retraining demo")
    say("#  Problem: a model in production silently rots as the input data shifts.")
    say("#  This pipeline measures that shift (PSI + KS) and retrains before it hurts.")
    say("#" * 72)

    step("Reset the database")
    if args.keep_db:
        say("  · --keep-db set, skipping reset")
    else:
        reset_database()

    step("Regenerate baseline + drifting production stream")
    regenerate_data()

    step("Launch the ModelWatch server")
    env = {**os.environ, "FLASK_DEBUG": "0", "PORT": str(args.port), "PYTHONUNBUFFERED": "1"}
    server = subprocess.Popen(
        [sys.executable, "run.py"],
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        wait_for_health(base_url)

        step("Train the initial model on the clean baseline")
        run_id = train_initial(base_url)

        step("Replay production traffic; drift-check as batches arrive")
        say("  Batches 1-3 are clean. Drift ramps from batch 4. Concept drift from batch 7.\n")
        batch_files = sorted((ROOT / "data" / "stream").glob("batch_*.csv"))

        active_run = run_id
        retrained_to = None
        for i, path in enumerate(batch_files, start=1):
            res = send_batch(base_url, active_run, path)
            preds = res.get("predictions", [])
            pos_rate = sum(preds) / len(preds) if preds else 0.0
            acc = accuracy_so_far(base_url, active_run)
            acc_str = f"{acc:.2f}" if acc is not None else " n/a"
            say(f"  batch {i:2d}/{len(batch_files)}  ->  logged {res['logged']:2d} preds   "
                f"positive_rate={pos_rate:0.2f}   rolling_acc(run {active_run})={acc_str}")

            if i >= 3 and i % 3 == 0 and retrained_to is None:
                say("     ↳ running drift check + auto-retrain policy ...")
                verdict = check_and_retrain(base_url, active_run)
                summ = verdict["drift_check"]["summary"]
                say(f"       PSI significant on {summ['n_significant']}/{summ['n_features_checked']} "
                    f"features  (fraction {verdict['drift_fraction']:.2f}, "
                    f"threshold {verdict['drift_fraction_threshold']:.2f})")
                sig = summ.get("significant_features", [])
                if sig:
                    say(f"       drifted features: {', '.join(sig)}")
                if verdict["retrain_triggered"]:
                    retrained_to = verdict["new_run_id"]
                    nm = verdict["new_run_metrics"]
                    say(f"       *** AUTO-RETRAIN TRIGGERED ***  new run #{retrained_to} "
                        f"(acc={nm['accuracy']:.3f} f1={nm['f1']:.3f} auc={nm['auc']:.3f})")
                    say(f"       trained on the most recent production rows; switching traffic to it")
                    active_run = retrained_to
                else:
                    say("       drift below threshold — keep serving the current model")

            time.sleep(args.delay)

        step("Summary")
        events = requests.get(f"{base_url}/api/retrain-events", timeout=30).json()["events"]
        say(f"  · retrain events recorded: {len(events)}")
        for e in events:
            marker = f"-> new run {e['new_run_id']}" if e["new_run_id"] else "(no retrain)"
            say(f"      run {e['run_id']} {marker}: {e['reason']}")
        if retrained_to:
            say(f"\n  Final: drift on the injected features was detected and the model was "
                f"automatically retrained (run {run_id} -> run {retrained_to}).")
        else:
            say("\n  Final: no retrain fired — try a longer stream or a lower threshold.")
        say(f"\n  Open the dashboard:  {base_url}/dashboard\n")
        return 0
    finally:
        server.terminate()
        try:
            server.wait(timeout=5)
        except subprocess.TimeoutExpired:
            server.kill()


if __name__ == "__main__":
    raise SystemExit(main())
