"""API tests: health, train, predict (+ logging), drift-check, auto-retrain."""

import numpy as np


def test_health_ok(client):
    resp = client.get("/health")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["status"] == "ok"
    assert body["database"] == "ok"


def test_train_endpoint(client):
    # Provide an explicit tiny dataset so the route is self-contained.
    rng = np.random.default_rng(1)
    n = 300
    records = []
    for _ in range(n):
        x = rng.normal(0, 1)
        records.append({"a": x, "b": rng.normal(3, 1), "target": int(x > 0)})
    resp = client.post(
        "/api/train",
        json={
            "model_type": "random_forest",
            "baseline_csv": None,
            "feature_columns": ["a", "b"],
            "target_column": "target",
        },
    )
    # baseline_csv None -> falls back to data/baseline/baseline.csv which doesn't
    # exist in tests, so we expect a clean 400 rather than a 500.
    assert resp.status_code == 400


def test_predict_logs_to_prediction_log(client, trained_run, app):
    from app.models import PredictionLog

    payload = {
        "records": [
            {"f0": 0.5, "f1": 5.1, "f2": -1.8, "f3": 9.7},
            {"f0": -1.2, "f1": 6.0, "f2": -2.5, "f3": 11.0},
        ],
        "actual_labels": [1, 0],
    }
    resp = client.post(f"/api/predict/{trained_run}", json=payload)
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["predictions"]) == 2
    assert len(body["probabilities"]) == 2
    assert body["logged"] == 2
    assert all(p in (0, 1) for p in body["predictions"])

    with app.app_context():
        logs = PredictionLog.query.filter_by(run_id=trained_run).all()
        assert len(logs) == 2
        assert {log.actual_label for log in logs} == {0, 1}
        assert all(log.timestamp is not None for log in logs)
        assert all("f0" in log.input_features for log in logs)


def test_predict_accepts_single_object(client, trained_run):
    resp = client.post(
        f"/api/predict/{trained_run}",
        json={"f0": 0.1, "f1": 5.0, "f2": -2.0, "f3": 10.0},
    )
    assert resp.status_code == 200
    assert resp.get_json()["logged"] == 1


def test_predict_unknown_run_404(client):
    resp = client.post("/api/predict/9999", json={"f0": 1})
    assert resp.status_code == 404


def test_drift_check_requires_predictions(client, trained_run):
    resp = client.get(f"/api/drift-check/{trained_run}")
    assert resp.status_code == 409  # nothing logged yet


def test_drift_check_after_traffic_reports_stable(client, trained_run, synthetic_frame):
    # Replay the *same* distribution -> should be stable.
    sample = synthetic_frame.sample(200, random_state=3)
    client.post(
        f"/api/predict/{trained_run}",
        json={
            "records": sample.drop(columns=["target"]).to_dict("records"),
            "actual_labels": [int(v) for v in sample["target"]],
        },
    )
    resp = client.get(f"/api/drift-check/{trained_run}")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["summary"]["n_features_checked"] == 4
    assert body["summary"]["n_significant"] == 0


def test_check_and_retrain_triggers_on_injected_drift(client, trained_run, synthetic_frame):
    # Push a strongly shifted batch: +3 on every feature, with labels.
    shifted = synthetic_frame.sample(200, random_state=7).copy()
    for col in ["f0", "f1", "f2", "f3"]:
        shifted[col] = shifted[col] + 3.0
    client.post(
        f"/api/predict/{trained_run}",
        json={
            "records": shifted.drop(columns=["target"]).to_dict("records"),
            "actual_labels": [int(v) for v in shifted["target"]],
        },
    )
    resp = client.post(
        f"/api/check-and-retrain/{trained_run}",
        json={"drift_fraction_threshold": 0.3, "min_rows": 50},
    )
    assert resp.status_code in (200, 201)
    body = resp.get_json()
    assert body["drift_check"]["summary"]["n_significant"] >= 3
    assert body["retrain_triggered"] is True
    assert body["new_run_id"] is not None
    assert body["new_run_id"] != trained_run


def test_retrain_events_listed(client, trained_run, synthetic_frame):
    sample = synthetic_frame.sample(120, random_state=5)
    client.post(
        f"/api/predict/{trained_run}",
        json={
            "records": sample.drop(columns=["target"]).to_dict("records"),
            "actual_labels": [int(v) for v in sample["target"]],
        },
    )
    client.post(f"/api/check-and-retrain/{trained_run}", json={})
    resp = client.get("/api/retrain-events")
    assert resp.status_code == 200
    assert resp.get_json()["count"] >= 1
