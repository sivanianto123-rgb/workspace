"""Inference endpoint + prediction logging."""

from __future__ import annotations

from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from app import db
from app.ml.inference import predict as run_predict
from app.models import PredictionLog, Run

bp = Blueprint("predict", __name__, url_prefix="/api")


@bp.post("/predict/<int:run_id>")
def predict(run_id: int):
    """Score one row or a batch of rows and log every scored row to ``prediction_logs``.

    Accepts any of::

        {"feature_a": 1.2, "feature_b": 3.4}                       # single row
        {"features": {"feature_a": 1.2, ...}}                      # single row, wrapped
        {"features": [ {...}, {...} ]}                             # batch
        {"records": [ {...}, {...} ], "actual_labels": [0, 1]}     # batch + ground truth

    Response: ``{"run_id", "predictions": [...], "probabilities": [...], "logged": N}``
    """
    run = db.session.get(Run, run_id)
    if run is None:
        return jsonify(error=f"run {run_id} not found"), 404
    if not run.model_artifact_path:
        return jsonify(error=f"run {run_id} has no trained artifact (status={run.status})"), 409

    payload = request.get_json(silent=True)
    if payload is None:
        return jsonify(error="request body must be JSON"), 400

    if "features" in payload:
        features = payload["features"]
    elif "records" in payload:
        features = payload["records"]
    else:
        # Treat the whole object as a single feature row.
        features = payload

    rows = features if isinstance(features, list) else [features]
    if not rows or not all(isinstance(r, dict) for r in rows):
        return jsonify(error="no feature rows supplied"), 400

    actual_labels = payload.get("actual_labels")
    if actual_labels is not None and len(actual_labels) != len(rows):
        return jsonify(error="actual_labels length must match number of rows"), 400

    try:
        result = run_predict(run_id, rows)
    except LookupError as exc:
        return jsonify(error=str(exc)), 404
    except ValueError as exc:
        return jsonify(error=str(exc)), 400

    now = datetime.now(timezone.utc)
    feature_cols = result["feature_columns"]
    for i, row in enumerate(rows):
        logged_features = {c: _num(row.get(c)) for c in feature_cols}
        db.session.add(
            PredictionLog(
                run_id=run_id,
                input_features=logged_features,
                prediction=result["predictions"][i],
                prediction_proba=result["probabilities"][i],
                actual_label=(
                    int(actual_labels[i])
                    if actual_labels is not None and actual_labels[i] is not None
                    else None
                ),
                timestamp=now,
            )
        )
    db.session.commit()

    return jsonify(
        run_id=run_id,
        predictions=result["predictions"],
        probabilities=result["probabilities"],
        logged=len(rows),
    )


@bp.get("/predictions/<int:run_id>")
def list_predictions(run_id: int):
    """Recent prediction logs for a run (default newest 100, ``?limit=``, ``?order=asc``)."""
    limit = min(int(request.args.get("limit", 100)), 5000)
    order = request.args.get("order", "desc")
    q = PredictionLog.query.filter_by(run_id=run_id)
    q = q.order_by(
        PredictionLog.timestamp.asc() if order == "asc" else PredictionLog.timestamp.desc()
    )
    logs = q.limit(limit).all()
    return jsonify(
        run_id=run_id,
        count=len(logs),
        predictions=[log.to_dict() for log in logs],
    )


def _num(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return value
