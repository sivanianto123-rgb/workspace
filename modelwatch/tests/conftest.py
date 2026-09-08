"""Shared pytest fixtures."""

import os

import numpy as np
import pandas as pd
import pytest

from app import create_app, db as _db


@pytest.fixture()
def app(tmp_path):
    application = create_app("testing")
    # Redirect all filesystem writes into the test's tmp dir.
    for key, sub in [
        ("DATA_DIR", "data"),
        ("RAW_DATA_DIR", "data/raw"),
        ("STREAM_DATA_DIR", "data/stream"),
        ("MODELS_DIR", "models"),
    ]:
        path = tmp_path / sub
        path.mkdir(parents=True, exist_ok=True)
        application.config[key] = str(path)

    with application.app_context():
        _db.create_all()
        yield application
        _db.session.remove()
        _db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


@pytest.fixture()
def synthetic_frame():
    """Small separable binary-classification dataset with 4 numeric features."""
    rng = np.random.default_rng(0)
    n = 400
    x0 = rng.normal(0, 1, n)
    x1 = rng.normal(5, 2, n)
    x2 = rng.normal(-2, 1, n)
    x3 = rng.normal(10, 3, n)
    logit = 1.5 * x0 - 0.5 * (x1 - 5) + 0.8 * (x2 + 2)
    y = (logit + rng.normal(0, 0.5, n) > 0).astype(int)
    return pd.DataFrame({"f0": x0, "f1": x1, "f2": x2, "f3": x3, "target": y})


@pytest.fixture()
def trained_run(app, synthetic_frame):
    """Train a real model inside the app context and return its run_id."""
    from app.ml.training import run_training

    run = run_training(
        model_name="test-model",
        model_type="logistic_regression",
        hyperparams={},
        baseline_source=synthetic_frame,
        feature_columns=["f0", "f1", "f2", "f3"],
        target_column="target",
    )
    return run.id
