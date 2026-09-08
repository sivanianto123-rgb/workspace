"""Flask application factory for ModelWatch."""

import os

from flask import Flask, jsonify
from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

from config import Config, config_by_name

db = SQLAlchemy()
migrate = Migrate()


def create_app(config_name=None):
    config_name = config_name or os.environ.get("FLASK_CONFIG", "default")

    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.config.from_object(config_by_name[config_name])

    # Make sure local filesystem locations exist (SQLite file, artifacts, data).
    for path in (
        app.config["DATA_DIR"],
        app.config["RAW_DATA_DIR"],
        app.config["STREAM_DATA_DIR"],
        app.config["MODELS_DIR"],
    ):
        os.makedirs(path, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)

    # Import models so Alembic autogenerate + create_all can see them.
    from app import models  # noqa: F401

    from app.routes.dashboard import bp as dashboard_bp
    from app.routes.drift import bp as drift_bp
    from app.routes.predict import bp as predict_bp
    from app.routes.train import bp as train_bp

    app.register_blueprint(train_bp)
    app.register_blueprint(predict_bp)
    app.register_blueprint(drift_bp)
    app.register_blueprint(dashboard_bp)

    @app.get("/health")
    def health():
        """Liveness probe: confirms the process and DB connection are up."""
        db_ok = True
        try:
            db.session.execute(db.text("SELECT 1"))
        except Exception:  # noqa: BLE001
            db_ok = False
        status = "ok" if db_ok else "degraded"
        code = 200 if db_ok else 503
        return (
            jsonify(
                status=status,
                service="modelwatch",
                database="ok" if db_ok else "unavailable",
            ),
            code,
        )

    return app
