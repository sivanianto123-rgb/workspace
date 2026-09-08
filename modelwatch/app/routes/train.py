"""Training endpoints."""

from __future__ import annotations

from flask import Blueprint, jsonify, request

from app import db
from app.ml.training import MODEL_REGISTRY, run_training
from app.models import Experiment, Run

bp = Blueprint("train", __name__, url_prefix="/api")


@bp.post("/train")
def train():
    """Train a model synchronously.

    Request JSON::

        {
          "model_name":  "tumor-classifier",        # optional, defaults per model_type
          "model_type":  "logistic_regression" | "random_forest",
          "hyperparams": { ... },                    # optional, merged over defaults
          "baseline_csv": "data/stream/batch_010.csv", # optional override of training data
          "target_column": "target",                 # optional, auto-detected
          "feature_columns": [...],                  # optional, auto-detected (numeric)
          "notes": "..."                             # optional
        }

    Response: ``{"run_id": .., "experiment_id": .., "status": "completed", "metrics": {...}}``
    """
    payload = request.get_json(silent=True) or {}

    model_type = payload.get("model_type", "logistic_regression")
    if model_type not in MODEL_REGISTRY:
        return (
            jsonify(error=f"unknown model_type {model_type!r}", allowed=sorted(MODEL_REGISTRY)),
            400,
        )

    model_name = payload.get("model_name") or f"tumor-classifier-{model_type}"
    hyperparams = payload.get("hyperparams") or {}
    if not isinstance(hyperparams, dict):
        return jsonify(error="hyperparams must be an object"), 400

    try:
        run = run_training(
            model_name=model_name,
            model_type=model_type,
            hyperparams=hyperparams,
            baseline_source=payload.get("baseline_csv"),
            feature_columns=payload.get("feature_columns"),
            target_column=payload.get("target_column"),
            notes=payload.get("notes"),
        )
    except (ValueError, FileNotFoundError) as exc:
        return jsonify(error=str(exc)), 400

    return (
        jsonify(
            run_id=run.id,
            experiment_id=run.experiment_id,
            status=run.status,
            model_type=model_type,
            model_name=model_name,
            metrics=run.metrics,
            train_duration_seconds=run.train_duration_seconds,
            n_training_rows=run.n_training_rows,
            model_artifact_path=run.model_artifact_path,
        ),
        201,
    )


@bp.get("/runs")
def list_runs():
    """All runs, newest first, with their experiment metadata and metrics."""
    runs = Run.query.order_by(Run.created_at.desc()).all()
    return jsonify(runs=[r.to_dict() for r in runs], count=len(runs))


@bp.get("/runs/<int:run_id>")
def get_run(run_id: int):
    run = db.session.get(Run, run_id)
    if run is None:
        return jsonify(error="run not found"), 404
    return jsonify(run.to_dict())


@bp.get("/experiments")
def list_experiments():
    experiments = Experiment.query.order_by(Experiment.created_at.desc()).all()
    return jsonify(
        experiments=[
            {**e.to_dict(), "run_ids": [r.id for r in e.runs]} for e in experiments
        ],
        count=len(experiments),
    )
