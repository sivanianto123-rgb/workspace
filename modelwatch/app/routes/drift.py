"""Drift-check and auto-retrain endpoints."""

from __future__ import annotations

from datetime import datetime, timezone

import pandas as pd
from flask import Blueprint, current_app, jsonify, request

from app import db
from app.ml.drift_detection import compare_distributions
from app.ml.training import run_training
from app.models import DriftReport, PredictionLog, RetrainEvent, Run
from app.utils.datasets import load_dataframe, run_baseline_path

bp = Blueprint("drift", __name__, url_prefix="/api")


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #

def _load_baseline_frame(run: Run) -> pd.DataFrame:
    """Feature snapshot captured at training time for this run."""
    path = run_baseline_path(run.id)
    return load_dataframe(path)


def _recent_prediction_frame(run_id: int, n: int):
    """Return (feature_df, has_labels, target_series, window_start, window_end).

    Pulls the most recent ``n`` prediction logs and explodes their
    ``input_features`` JSON back into a DataFrame.
    """
    logs = (
        PredictionLog.query.filter_by(run_id=run_id)
        .order_by(PredictionLog.timestamp.desc())
        .limit(n)
        .all()
    )
    logs = list(reversed(logs))  # chronological
    if not logs:
        return pd.DataFrame(), False, None, None, None

    rows = [dict(log.input_features or {}) for log in logs]
    feature_df = pd.DataFrame(rows)

    labels = [log.actual_label for log in logs]
    has_labels = any(v is not None for v in labels)
    target = pd.Series(labels, name="target") if has_labels else None

    return feature_df, has_labels, target, logs[0].timestamp, logs[-1].timestamp


def _run_drift_check(run: Run, window_size: int) -> dict:
    """Compare the recent prediction window against the training baseline.

    Persists one :class:`DriftReport` row per feature and returns a summary dict.
    """
    cfg = current_app.config
    baseline_df = _load_baseline_frame(run)
    feature_columns = run.experiment.feature_columns or [
        c for c in baseline_df.columns if c != run.experiment.target_column
    ]

    current_df, _has_labels, _target, win_start, win_end = _recent_prediction_frame(
        run.id, window_size
    )
    if current_df.empty:
        return {
            "run_id": run.id,
            "error": "no predictions logged yet for this run",
            "features": {},
            "summary": {"n_features_checked": 0},
        }

    comparison = compare_distributions(
        baseline_df,
        current_df,
        feature_columns,
        stable_max=cfg["PSI_STABLE_MAX"],
        moderate_max=cfg["PSI_MODERATE_MAX"],
        ks_p_threshold=cfg["KS_P_VALUE_THRESHOLD"],
    )

    created_at = datetime.now(timezone.utc)
    sample_size = int(len(current_df))
    for feature, res in comparison["features"].items():
        db.session.add(
            DriftReport(
                run_id=run.id,
                feature_name=feature,
                test_statistic=res["psi"],
                p_value=res["ks_p_value"],
                drift_score=res["psi"],
                drift_detected=res["drift_detected"],
                severity=res["severity"],
                method=res["method"],
                window_start=win_start,
                window_end=win_end,
                sample_size=sample_size,
                created_at=created_at,
            )
        )
    db.session.commit()

    summary = comparison["summary"]
    return {
        "run_id": run.id,
        "checked_at": created_at.isoformat(),
        "window": {
            "size": sample_size,
            "start": win_start.isoformat() if win_start else None,
            "end": win_end.isoformat() if win_end else None,
        },
        "thresholds": {
            "psi_stable_max": cfg["PSI_STABLE_MAX"],
            "psi_moderate_max": cfg["PSI_MODERATE_MAX"],
            "ks_p_value": cfg["KS_P_VALUE_THRESHOLD"],
        },
        "summary": summary,
        "features": {
            f: {
                "psi": round(r["psi"], 5),
                "ks_statistic": round(r["ks_statistic"], 5),
                "ks_p_value": round(r["ks_p_value"], 6),
                "severity": r["severity"],
                "drift_detected": r["drift_detected"],
                "significant": r["significant"],
                "baseline_mean": r["baseline_mean"],
                "current_mean": r["current_mean"],
                "baseline_std": r["baseline_std"],
                "current_std": r["current_std"],
            }
            for f, r in comparison["features"].items()
        },
    }


# --------------------------------------------------------------------------- #
# routes
# --------------------------------------------------------------------------- #

@bp.get("/drift-check/<int:run_id>")
def drift_check(run_id: int):
    """Run a drift check for ``run_id`` against its training baseline.

    Query params: ``?window=`` (default ``DRIFT_WINDOW_SIZE``).
    """
    run = db.session.get(Run, run_id)
    if run is None:
        return jsonify(error=f"run {run_id} not found"), 404

    window_size = int(request.args.get("window", current_app.config["DRIFT_WINDOW_SIZE"]))
    result = _run_drift_check(run, window_size)
    status = 200 if "error" not in result else 409
    return jsonify(result), status


@bp.get("/drift-reports/<int:run_id>")
def drift_reports(run_id: int):
    """Raw DriftReport history for a run (for the dashboard timeline)."""
    reports = (
        DriftReport.query.filter_by(run_id=run_id)
        .order_by(DriftReport.created_at.asc(), DriftReport.feature_name.asc())
        .all()
    )
    return jsonify(run_id=run_id, count=len(reports), reports=[r.to_dict() for r in reports])


@bp.post("/check-and-retrain/<int:run_id>")
def check_and_retrain(run_id: int):
    """Drift-check, then auto-retrain if too much of the feature space has drifted.

    Body (all optional)::

        {"window": 300, "drift_fraction_threshold": 0.30, "min_rows": 60}

    A retrain fires when
    ``(# features with severity == "significant") / (# features checked) > threshold``.
    The replacement model is trained on the most recent labelled production
    predictions, and a :class:`RetrainEvent` audit row is written either way.
    """
    run = db.session.get(Run, run_id)
    if run is None:
        return jsonify(error=f"run {run_id} not found"), 404

    cfg = current_app.config
    body = request.get_json(silent=True) or {}
    window_size = int(body.get("window", cfg["DRIFT_WINDOW_SIZE"]))
    threshold = float(body.get("drift_fraction_threshold", cfg["RETRAIN_DRIFT_FRACTION"]))
    min_rows = int(body.get("min_rows", 60))

    drift_result = _run_drift_check(run, window_size)
    if "error" in drift_result:
        return jsonify(drift_result), 409

    summary = drift_result["summary"]
    drift_fraction = summary.get("drift_fraction", 0.0)
    should_retrain = drift_fraction > threshold

    response = {
        "run_id": run_id,
        "drift_check": drift_result,
        "drift_fraction": drift_fraction,
        "drift_fraction_threshold": threshold,
        "retrain_triggered": False,
        "new_run_id": None,
    }

    if not should_retrain:
        db.session.add(
            RetrainEvent(
                run_id=run_id,
                triggered_by="drift_monitor",
                reason=(
                    f"No retrain: {summary['n_significant']}/{summary['n_features_checked']} "
                    f"features significant (fraction {drift_fraction:.2f} <= {threshold:.2f})"
                ),
                drift_summary=summary,
                new_run_id=None,
            )
        )
        db.session.commit()
        return jsonify(response), 200

    # --- build a fresh training set from recent labelled production data -------
    feature_df, has_labels, target, _s, _e = _recent_prediction_frame(run_id, window_size)
    if not has_labels or feature_df.empty or len(feature_df) < min_rows:
        reason = (
            f"Drift threshold exceeded (fraction {drift_fraction:.2f} > {threshold:.2f}) "
            f"but only {len(feature_df)} labelled rows available (need {min_rows}); retrain skipped"
        )
        db.session.add(
            RetrainEvent(
                run_id=run_id,
                triggered_by="drift_monitor",
                reason=reason,
                drift_summary=summary,
                new_run_id=None,
            )
        )
        db.session.commit()
        response["reason"] = reason
        return jsonify(response), 200

    new_training_df = feature_df.copy()
    new_training_df[run.experiment.target_column] = target.astype(int).to_numpy()

    reason = (
        f"Auto-retrain: {summary['n_significant']}/{summary['n_features_checked']} features "
        f"significantly drifted (fraction {drift_fraction:.2f} > threshold {threshold:.2f}); "
        f"retrained on {len(new_training_df)} recent production rows"
    )

    new_run = run_training(
        model_name=run.experiment.model_name,
        model_type=run.experiment.model_type,
        hyperparams=run.experiment.hyperparams,
        baseline_source=new_training_df,
        feature_columns=run.experiment.feature_columns,
        target_column=run.experiment.target_column,
        notes=f"drift-triggered retrain of run {run_id}",
    )

    db.session.add(
        RetrainEvent(
            run_id=run_id,
            triggered_by="drift_monitor",
            reason=reason,
            drift_summary=summary,
            new_run_id=new_run.id,
        )
    )
    db.session.commit()

    response["retrain_triggered"] = True
    response["new_run_id"] = new_run.id
    response["reason"] = reason
    response["new_run_metrics"] = new_run.metrics
    return jsonify(response), 201


@bp.get("/retrain-events")
def retrain_events():
    """All retrain events, newest first (optionally ``?run_id=``)."""
    q = RetrainEvent.query
    run_id = request.args.get("run_id", type=int)
    if run_id is not None:
        q = q.filter_by(run_id=run_id)
    events = q.order_by(RetrainEvent.created_at.desc()).all()
    return jsonify(count=len(events), events=[e.to_dict() for e in events])
