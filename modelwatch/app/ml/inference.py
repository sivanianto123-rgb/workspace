"""Load a trained run's artifact and score new feature rows."""

from __future__ import annotations

import functools

import joblib
import numpy as np
import pandas as pd

from app import db
from app.models import Run


@functools.lru_cache(maxsize=16)
def _load_artifact(path: str):
    return joblib.load(path)


def load_model_for_run(run_id: int):
    """Return ``(pipeline, feature_columns, target_column)`` for a completed run."""
    run = db.session.get(Run, run_id)
    if run is None:
        raise LookupError(f"run {run_id} not found")
    if not run.model_artifact_path:
        raise LookupError(f"run {run_id} has no serialized artifact (status={run.status})")
    payload = _load_artifact(run.model_artifact_path)
    return payload["pipeline"], payload["feature_columns"], payload["target_column"]


def _coerce_frame(features, feature_columns: list[str]) -> pd.DataFrame:
    if isinstance(features, dict):
        rows = [features]
    elif isinstance(features, list):
        rows = features
    elif isinstance(features, pd.DataFrame):
        rows = features.to_dict("records")
    else:
        raise ValueError("features must be an object or a list of objects")

    df = pd.DataFrame(rows)
    # Keep only known columns, add any missing ones as 0, order consistently.
    df = df.reindex(columns=feature_columns)
    df = df.apply(pd.to_numeric, errors="coerce").fillna(0.0)
    return df


def predict(run_id: int, features):
    """Score one or many feature rows.

    Returns ``{"predictions": [...], "probabilities": [...], "feature_columns": [...]}``
    where ``probabilities`` is P(y == positive class) per row.
    """
    pipeline, feature_columns, _ = load_model_for_run(run_id)
    X = _coerce_frame(features, feature_columns)

    preds = pipeline.predict(X)
    try:
        proba = pipeline.predict_proba(X)[:, 1]
    except (AttributeError, ValueError):
        proba = np.full(len(X), np.nan)

    return {
        "predictions": [int(p) for p in preds],
        "probabilities": [None if np.isnan(p) else float(p) for p in proba],
        "feature_columns": feature_columns,
        "n_rows": int(len(X)),
    }
