"""SQLAlchemy models for ModelWatch.

Relationship overview::

    Experiment 1---* Run 1---* PredictionLog
                       Run 1---* DriftReport
                       Run 1---* RetrainEvent   (as the run that triggered a retrain)
"""

from datetime import datetime, timezone

from app import db


def _utcnow():
    return datetime.now(timezone.utc)


# Status values for a training Run.
RUN_STATUSES = ("pending", "running", "completed", "failed")


class Experiment(db.Model):
    """A modelling problem definition: which target, which features, which algo family."""

    __tablename__ = "experiments"

    id = db.Column(db.Integer, primary_key=True)
    model_name = db.Column(db.String(128), nullable=False, index=True)
    model_type = db.Column(db.String(64), nullable=False)  # e.g. logistic_regression | random_forest
    hyperparams = db.Column(db.JSON, nullable=False, default=dict)
    feature_columns = db.Column(db.JSON, nullable=False, default=list)
    target_column = db.Column(db.String(128), nullable=False)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    runs = db.relationship(
        "Run",
        back_populates="experiment",
        cascade="all, delete-orphan",
        order_by="Run.created_at",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "model_name": self.model_name,
            "model_type": self.model_type,
            "hyperparams": self.hyperparams,
            "feature_columns": self.feature_columns,
            "target_column": self.target_column,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Experiment id={self.id} name={self.model_name!r} type={self.model_type!r}>"


class Run(db.Model):
    """A single training run of an Experiment, with its metrics and serialized artifact."""

    __tablename__ = "runs"

    id = db.Column(db.Integer, primary_key=True)
    experiment_id = db.Column(
        db.Integer,
        db.ForeignKey("experiments.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # {"accuracy":.., "precision":.., "recall":.., "f1":.., "auc":..}
    metrics = db.Column(db.JSON, nullable=False, default=dict)
    train_duration_seconds = db.Column(db.Float)
    model_artifact_path = db.Column(db.String(512))
    status = db.Column(
        db.Enum(*RUN_STATUSES, name="run_status"),
        nullable=False,
        default="pending",
        index=True,
    )
    # Number of rows used as the training baseline — needed for drift comparisons.
    n_training_rows = db.Column(db.Integer)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    experiment = db.relationship("Experiment", back_populates="runs")
    prediction_logs = db.relationship(
        "PredictionLog",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    drift_reports = db.relationship(
        "DriftReport",
        back_populates="run",
        cascade="all, delete-orphan",
    )
    retrain_events = db.relationship(
        "RetrainEvent",
        back_populates="run",
        foreign_keys="RetrainEvent.run_id",
        cascade="all, delete-orphan",
    )

    def to_dict(self):
        return {
            "id": self.id,
            "experiment_id": self.experiment_id,
            "model_name": self.experiment.model_name if self.experiment else None,
            "model_type": self.experiment.model_type if self.experiment else None,
            "metrics": self.metrics,
            "train_duration_seconds": self.train_duration_seconds,
            "model_artifact_path": self.model_artifact_path,
            "status": self.status,
            "n_training_rows": self.n_training_rows,
            "notes": self.notes,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return f"<Run id={self.id} experiment_id={self.experiment_id} status={self.status!r}>"


class PredictionLog(db.Model):
    """One scored inference request, retained so we can watch the input distribution over time."""

    __tablename__ = "prediction_logs"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer,
        db.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    input_features = db.Column(db.JSON, nullable=False)  # {feature_name: value}
    prediction = db.Column(db.Integer)                    # predicted class label
    prediction_proba = db.Column(db.Float)               # P(y == positive class)
    actual_label = db.Column(db.Integer, nullable=True)   # filled in later if ground truth arrives
    timestamp = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    run = db.relationship("Run", back_populates="prediction_logs")

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "input_features": self.input_features,
            "prediction": self.prediction,
            "prediction_proba": self.prediction_proba,
            "actual_label": self.actual_label,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
        }

    def __repr__(self):
        return f"<PredictionLog id={self.id} run_id={self.run_id} pred={self.prediction}>"


class DriftReport(db.Model):
    """Result of a single feature's drift test at a point in time."""

    __tablename__ = "drift_reports"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer,
        db.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    feature_name = db.Column(db.String(128), nullable=False, index=True)
    test_statistic = db.Column(db.Float)   # PSI value or KS statistic depending on method
    p_value = db.Column(db.Float)          # KS p-value (None for PSI-only rows)
    drift_score = db.Column(db.Float)      # canonical severity number == PSI
    drift_detected = db.Column(db.Boolean, default=False, nullable=False)
    severity = db.Column(db.String(16))    # stable | moderate | significant
    method = db.Column(db.String(16))      # 'PSI' | 'KS' | 'PSI+KS'
    window_start = db.Column(db.DateTime)
    window_end = db.Column(db.DateTime)
    sample_size = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    run = db.relationship("Run", back_populates="drift_reports")

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "feature_name": self.feature_name,
            "test_statistic": self.test_statistic,
            "p_value": self.p_value,
            "drift_score": self.drift_score,
            "drift_detected": self.drift_detected,
            "severity": self.severity,
            "method": self.method,
            "window_start": self.window_start.isoformat() if self.window_start else None,
            "window_end": self.window_end.isoformat() if self.window_end else None,
            "sample_size": self.sample_size,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (
            f"<DriftReport id={self.id} run_id={self.run_id} "
            f"feature={self.feature_name!r} psi={self.drift_score} detected={self.drift_detected}>"
        )


class RetrainEvent(db.Model):
    """Audit record for an automatic drift-triggered retrain decision."""

    __tablename__ = "retrain_events"

    id = db.Column(db.Integer, primary_key=True)
    run_id = db.Column(
        db.Integer,
        db.ForeignKey("runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )  # the run that was being monitored
    triggered_by = db.Column(db.String(64), nullable=False, default="drift_monitor")
    reason = db.Column(db.Text)
    drift_summary = db.Column(db.JSON)  # snapshot of the drift check that caused this
    new_run_id = db.Column(
        db.Integer,
        db.ForeignKey("runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_at = db.Column(db.DateTime, default=_utcnow, nullable=False, index=True)

    run = db.relationship("Run", back_populates="retrain_events", foreign_keys=[run_id])
    new_run = db.relationship("Run", foreign_keys=[new_run_id])

    def to_dict(self):
        return {
            "id": self.id,
            "run_id": self.run_id,
            "triggered_by": self.triggered_by,
            "reason": self.reason,
            "drift_summary": self.drift_summary,
            "new_run_id": self.new_run_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }

    def __repr__(self):
        return (
            f"<RetrainEvent id={self.id} run_id={self.run_id} "
            f"new_run_id={self.new_run_id} by={self.triggered_by!r}>"
        )
