"""Portfolio dashboard: HTML view + JSON feeds for the Chart.js widgets."""

from __future__ import annotations

import numpy as np
import pandas as pd
from flask import Blueprint, current_app, jsonify, render_template, request

from app import db
from app.models import DriftReport, Experiment, PredictionLog, RetrainEvent, Run
from app.utils.datasets import load_dataframe, run_baseline_path

bp = Blueprint("dashboard", __name__)


@bp.get("/")
def index():
    return render_template("index.html")


@bp.get("/dashboard")
def dashboard():
    runs = Run.query.order_by(Run.created_at.asc()).all()
    default_run = runs[-1].id if runs else None
    return render_template("dashboard.html", default_run_id=default_run)


# --------------------------------------------------------------------------- #
# JSON feeds
# --------------------------------------------------------------------------- #

@bp.get("/dashboard/api/summary")
def summary():
    """Runs table + retrain-event list."""
    runs = Run.query.order_by(Run.created_at.asc()).all()
    events = RetrainEvent.query.order_by(RetrainEvent.created_at.desc()).all()
    return jsonify(
        experiments=Experiment.query.count(),
        runs=[r.to_dict() for r in runs],
        retrain_events=[e.to_dict() for e in events],
        prediction_count=PredictionLog.query.count(),
    )


@bp.get("/dashboard/api/performance")
def performance():
    """Metric-vs-run series for the performance line chart."""
    runs = (
        Run.query.filter(Run.status == "completed")
        .order_by(Run.created_at.asc())
        .all()
    )
    points = []
    for r in runs:
        m = r.metrics or {}
        points.append(
            {
                "run_id": r.id,
                "label": f"run {r.id} ({r.experiment.model_type})" if r.experiment else f"run {r.id}",
                "created_at": r.created_at.isoformat() if r.created_at else None,
                "accuracy": m.get("accuracy"),
                "f1": m.get("f1"),
                "auc": m.get("auc"),
                "precision": m.get("precision"),
                "recall": m.get("recall"),
            }
        )
    return jsonify(points=points)


@bp.get("/dashboard/api/drift-timeline/<int:run_id>")
def drift_timeline(run_id: int):
    """Per-feature PSI (and KS p-value) across every drift check for this run."""
    reports = (
        DriftReport.query.filter_by(run_id=run_id)
        .order_by(DriftReport.created_at.asc())
        .all()
    )
    checkpoints: list[str] = []
    features: dict[str, dict[str, list]] = {}
    for rep in reports:
        ts = rep.created_at.isoformat() if rep.created_at else None
        if ts not in checkpoints:
            checkpoints.append(ts)
        feat = features.setdefault(rep.feature_name, {"psi": [], "ks_p_value": []})
        feat["psi"].append({"t": ts, "value": rep.drift_score})
        feat["ks_p_value"].append({"t": ts, "value": rep.p_value})

    return jsonify(
        run_id=run_id,
        checkpoints=checkpoints,
        features=features,
        psi_threshold=current_app.config["PSI_MODERATE_MAX"],
        ks_p_threshold=current_app.config["KS_P_VALUE_THRESHOLD"],
    )


@bp.get("/dashboard/api/feature-distribution/<int:run_id>")
def feature_distribution(run_id: int):
    """Histogram of baseline vs. current window for one feature (dropdown-driven)."""
    run = db.session.get(Run, run_id)
    if run is None:
        return jsonify(error="run not found"), 404

    baseline_df = load_dataframe(run_baseline_path(run_id))
    feature_columns = run.experiment.feature_columns or list(baseline_df.columns)
    feature = request.args.get("feature") or (feature_columns[0] if feature_columns else None)
    if feature is None or feature not in baseline_df.columns:
        return jsonify(error=f"unknown feature {feature!r}", features=feature_columns), 400

    window = int(request.args.get("window", current_app.config["DRIFT_WINDOW_SIZE"]))
    bins = int(request.args.get("bins", 20))

    logs = (
        PredictionLog.query.filter_by(run_id=run_id)
        .order_by(PredictionLog.timestamp.desc())
        .limit(window)
        .all()
    )
    current_vals = pd.Series(
        [(_l.input_features or {}).get(feature) for _l in logs], dtype="float64"
    ).dropna()
    baseline_vals = pd.to_numeric(baseline_df[feature], errors="coerce").dropna()

    combined = np.concatenate(
        [baseline_vals.to_numpy(), current_vals.to_numpy()]
    ) if len(current_vals) else baseline_vals.to_numpy()
    lo, hi = float(np.min(combined)), float(np.max(combined))
    if lo == hi:
        hi = lo + 1.0
    edges = np.linspace(lo, hi, bins + 1)
    centers = ((edges[:-1] + edges[1:]) / 2).round(4)

    base_counts, _ = np.histogram(baseline_vals, bins=edges)
    cur_counts, _ = (
        np.histogram(current_vals, bins=edges) if len(current_vals) else (np.zeros(bins), None)
    )

    return jsonify(
        run_id=run_id,
        feature=feature,
        features=feature_columns,
        bin_centers=centers.tolist(),
        baseline_counts=base_counts.astype(int).tolist(),
        current_counts=np.asarray(cur_counts).astype(int).tolist(),
        baseline_n=int(len(baseline_vals)),
        current_n=int(len(current_vals)),
    )
