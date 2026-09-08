"""Application configuration.

Values are read from environment variables (loaded from a local ``.env`` file
when present). PostgreSQL is used when ``DATABASE_URL`` is set; otherwise the app
falls back to a local SQLite file so it runs with zero external services.
"""

import os

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _normalize_db_url(url: str) -> str:
    # SQLAlchemy 1.4+ dropped the legacy "postgres://" scheme that some hosts
    # (Heroku-style) still hand out.
    if url.startswith("postgres://"):
        url = url.replace("postgres://", "postgresql://", 1)
    return url


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-secret-change-me")

    _db_url = os.environ.get("DATABASE_URL", "").strip()
    SQLALCHEMY_DATABASE_URI = (
        _normalize_db_url(_db_url)
        if _db_url
        else "sqlite:///" + os.path.join(BASE_DIR, "data", "modelwatch.db")
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    JSON_SORT_KEYS = False

    # Filesystem locations used by the ML pipeline.
    MODELS_DIR = os.environ.get("MODELS_DIR", os.path.join(BASE_DIR, "models"))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    RAW_DATA_DIR = os.path.join(BASE_DIR, "data", "raw")
    STREAM_DATA_DIR = os.path.join(BASE_DIR, "data", "stream")

    # ---- Drift-detection tuning -------------------------------------------------
    # PSI severity bands: <0.1 stable, 0.1-0.2 moderate, >0.2 significant.
    PSI_STABLE_MAX = float(os.environ.get("PSI_STABLE_MAX", 0.1))
    PSI_MODERATE_MAX = float(os.environ.get("PSI_MODERATE_MAX", 0.2))
    KS_P_VALUE_THRESHOLD = float(os.environ.get("KS_P_VALUE_THRESHOLD", 0.05))

    # How many of the most recent predictions to compare against baseline.
    DRIFT_WINDOW_SIZE = int(os.environ.get("DRIFT_WINDOW_SIZE", 300))

    # Auto-retrain trips when this fraction of monitored features drift "significantly".
    RETRAIN_DRIFT_FRACTION = float(os.environ.get("RETRAIN_DRIFT_FRACTION", 0.30))

    # Default held-out test split for training.
    TEST_SIZE = float(os.environ.get("TEST_SIZE", 0.2))
    RANDOM_STATE = int(os.environ.get("RANDOM_STATE", 42))


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


class TestingConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "TEST_DATABASE_URL", "sqlite:///:memory:"
    )


config_by_name = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
    "default": DevelopmentConfig,
}
