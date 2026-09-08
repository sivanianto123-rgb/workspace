"""Replay the simulated production batches against a running ModelWatch server.

Reads ``data/stream/batch_001.csv`` ... in order and POSTs each batch to
``/api/predict/<run_id>`` (one HTTP call per batch, all rows in the payload),
pausing ``--delay`` seconds between batches so the drift builds up over "time".

The batch CSVs still contain the ``target`` column; it is sent as
``actual_labels`` so the server can log ground truth (needed for auto-retrain).

Usage::

    python -m app.ml.simulate_traffic --run-id 1 --base-url http://127.0.0.1:5000 --delay 0.5
    python -m app.ml.simulate_traffic --run-id 1 --speed fast      # delay 0.1
    python -m app.ml.simulate_traffic --run-id 1 --drift-check-every 2
"""

from __future__ import annotations

import argparse
import sys
import time

import pandas as pd
import requests

from config import Config

SPEED_PRESETS = {"slow": 1.5, "normal": 0.5, "fast": 0.1, "instant": 0.0}
TARGET_COLUMN = "target"


def _stream_files() -> list[str]:
    import os

    d = Config.STREAM_DATA_DIR
    if not os.path.isdir(d):
        return []
    return sorted(
        os.path.join(d, f)
        for f in os.listdir(d)
        if f.startswith("batch_") and f.endswith(".csv")
    )


def send_batch(base_url: str, run_id: int, df: pd.DataFrame) -> dict:
    features = df.drop(columns=[TARGET_COLUMN], errors="ignore")
    payload = {"records": features.to_dict("records")}
    if TARGET_COLUMN in df.columns:
        payload["actual_labels"] = [int(v) for v in df[TARGET_COLUMN].tolist()]
    resp = requests.post(f"{base_url}/api/predict/{run_id}", json=payload, timeout=30)
    resp.raise_for_status()
    return resp.json()


def drift_check(base_url: str, run_id: int, window: int | None = None) -> dict:
    params = {"window": window} if window else {}
    resp = requests.get(f"{base_url}/api/drift-check/{run_id}", params=params, timeout=60)
    resp.raise_for_status()
    return resp.json()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", type=int, required=True)
    parser.add_argument("--base-url", default="http://127.0.0.1:5000")
    parser.add_argument("--delay", type=float, default=None, help="seconds between batches")
    parser.add_argument(
        "--speed", choices=sorted(SPEED_PRESETS), default="normal",
        help="preset delay if --delay is not given",
    )
    parser.add_argument(
        "--drift-check-every", type=int, default=0,
        help="call /api/drift-check every N batches (0 = never)",
    )
    parser.add_argument("--limit", type=int, default=0, help="only send the first N batches")
    args = parser.parse_args()

    delay = args.delay if args.delay is not None else SPEED_PRESETS[args.speed]
    files = _stream_files()
    if not files:
        print("no stream batches found — run:  python -m app.ml.data_simulation", file=sys.stderr)
        return 1
    if args.limit:
        files = files[: args.limit]

    print(f"Replaying {len(files)} batches -> {args.base_url}/api/predict/{args.run_id} "
          f"(delay {delay}s)\n")

    for i, path in enumerate(files, start=1):
        df = pd.read_csv(path)
        result = send_batch(args.base_url, args.run_id, df)
        preds = result.get("predictions", [])
        pos_rate = (sum(preds) / len(preds)) if preds else 0.0
        name = path.rsplit("/", 1)[-1]
        print(f"  [{i:2d}/{len(files)}] {name:16s}  rows={result.get('logged', 0):3d}  "
              f"pred_positive_rate={pos_rate:0.2f}")

        if args.drift_check_every and i % args.drift_check_every == 0:
            dc = drift_check(args.base_url, args.run_id)
            summ = dc.get("summary", {})
            print(f"        drift-check: {summ.get('n_significant', 0)}/{summ.get('n_features_checked', 0)} "
                  f"features significant  (fraction {summ.get('drift_fraction', 0):.2f})")

        if delay and i < len(files):
            time.sleep(delay)

    print("\ndone.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
