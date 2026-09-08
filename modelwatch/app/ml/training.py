"""Training pipeline: fit a classifier, evaluate it, serialize it, record it.

Public entry point is :func:`run_training`, which must be called inside a Flask
app context (it writes to the database and to the configured ``MODELS_DIR``).
"""

from __future__ import annotations

import time
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from flask import current_app
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

from app import db
from app.models import Experiment, Run
from app.utils.datasets import (
    baseline_csv_path,
    load_dataframe,
    run_baseline_path,
    run_model_path,
)

# model_type -> (estimator class, default hyperparameters)
MODEL_REGISTRY = {
    "logistic_regression": (
        LogisticRegression,
        {"max_iter": 1000, "C": 1.0, "solver": "lbfgs"},
    ),
    "random_forest": (
        RandomForestClassifier,
        {"n_estimators": 200, "max_depth": None, "random_state": 42, "n_jobs": -1},
    ),
}


def build_pipeline(model_type: str, hyperparams: dict | None = None) -> Pipeline:
    """StandardScaler -> classifier, as a single serializable sklearn Pipeline."""
    if model_type not in MODEL_REGISTRY:
        raise ValueError(
            f"Unknown model_type {model_type!r}. Options: {sorted(MODEL_REGISTRY)}"
        )
    estimator_cls, defaults = MODEL_REGISTRY[model_type]
    params = {**defaults, **(hyperparams or {})}
    return Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            ("classifier", estimator_cls(**params)),
        ]
    )


def _infer_feature_columns(df: pd.DataFrame, target_column: str) -> list[str]:
    numeric = df.select_dtypes(include=[np.number]).columns.tolist()
    return [c for c in numeric if c != target_column]


def evaluate(pipeline: Pipeline, X_test: pd.DataFrame, y_test: pd.Series) -> dict:
    """Standard binary-classification metrics on the held-out split."""
    y_pred = pipeline.predict(X_test)
    metrics = {
        "accuracy": float(accuracy_score(y_test, y_pred)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "recall": float(recall_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
    }
    try:
        y_proba = pipeline.predict_proba(X_test)[:, 1]
        metrics["auc"] = float(roc_auc_score(y_test, y_proba))
    except (AttributeError, ValueError):
        metrics["auc"] = None
    return metrics


def train_model(
    df: pd.DataFrame,
    feature_columns: list[str],
    target_column: str,
    model_type: str,
    hyperparams: dict | None = None,
    test_size: float = 0.2,
    random_state: int = 42,
) -> dict:
    """Fit + evaluate. Returns pipeline, metrics, and bookkeeping numbers."""
    X = df[feature_columns].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    y = df[target_column].astype(int)

    stratify = y if y.nunique() > 1 else None
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=stratify
    )

    pipeline = build_pipeline(model_type, hyperparams)
    start = time.perf_counter()
    pipeline.fit(X_train, y_train)
    duration = time.perf_counter() - start

    metrics = evaluate(pipeline, X_test, y_test)
    return {
        "pipeline": pipeline,
        "metrics": metrics,
        "train_duration_seconds": duration,
        "n_training_rows": int(len(X_train)),
        "X_train": X_train,
    }


def run_training(
    *,
    model_name: str,
    model_type: str,
    hyperparams: dict | None = None,
    baseline_source=None,
    feature_columns: list[str] | None = None,
    target_column: str | None = None,
    notes: str | None = None,
) -> Run:
    """Full training run: create Experiment + Run rows, train, serialize, persist.

    ``baseline_source`` may be a path, a DataFrame, or a list of records. When
    omitted, the canonical ``data/baseline/baseline.csv`` is used.
    """
    cfg = current_app.config
    hyperparams = hyperparams or {}

    source = baseline_source if baseline_source is not None else baseline_csv_path()
    df = load_dataframe(source)

    target_column = target_column or _detect_target(df)
    if target_column not in df.columns:
        raise ValueError(f"target column {target_column!r} not in dataset")
    if not feature_columns:
        feature_columns = _infer_feature_columns(df, target_column)
    if not feature_columns:
        raise ValueError("could not determine any numeric feature columns")

    experiment = Experiment(
        model_name=model_name,
        model_type=model_type,
        hyperparams=hyperparams,
        feature_columns=feature_columns,
        target_column=target_column,
    )
    db.session.add(experiment)
    db.session.flush()

    run = Run(experiment_id=experiment.id, status="running", metrics={}, notes=notes)
    db.session.add(run)
    db.session.flush()  # need run.id for artifact paths

    try:
        result = train_model(
            df,
            feature_columns=feature_columns,
            target_column=target_column,
            model_type=model_type,
            hyperparams=hyperparams,
            test_size=cfg["TEST_SIZE"],
            random_state=cfg["RANDOM_STATE"],
        )
    except Exception as exc:  # noqa: BLE001
        run.status = "failed"
        run.notes = f"{notes or ''}\nERROR: {exc}".strip()
        db.session.commit()
        raise

    model_path = run_model_path(run.id)
    joblib.dump(
        {
            "pipeline": result["pipeline"],
            "feature_columns": feature_columns,
            "target_column": target_column,
            "model_type": model_type,
            "trained_at": datetime.now(timezone.utc).isoformat(),
        },
        model_path,
    )

    # Snapshot the exact training feature distribution for later drift comparison.
    result["X_train"].to_csv(run_baseline_path(run.id), index=False)

    run.metrics = result["metrics"]
    run.train_duration_seconds = result["train_duration_seconds"]
    run.model_artifact_path = model_path
    run.n_training_rows = result["n_training_rows"]
    run.status = "completed"
    db.session.commit()
    return run


def _detect_target(df: pd.DataFrame) -> str:
    for candidate in ("target", "label", "y", "Churn", "default"):
        if candidate in df.columns:
            return candidate
    return df.columns[-1]
