import json

from ragdesk.app import create_app
from ragdesk.webhook import SIGNATURE_HEADER, sign
from ragdesk.pipeline import RagPipeline

SECRET = "flask-test-secret"


def client(pipeline: RagPipeline):
    app = create_app(pipeline=pipeline, secret=SECRET)
    app.config["TESTING"] = True
    return app.test_client()


def test_health_endpoint(pipeline: RagPipeline):
    c = client(pipeline)
    resp = c.get("/health")
    assert resp.status_code == 200
    assert resp.get_json() == {"status": "ok"}


def test_webhook_query_end_to_end(pipeline: RagPipeline):
    c = client(pipeline)
    body = json.dumps({"question": "How does Raft elect a leader?"}).encode()
    resp = c.post(
        "/webhook/query",
        data=body,
        headers={SIGNATURE_HEADER: sign(SECRET, body)},
        content_type="application/json",
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["sources"][0]["doc_id"] == "raftsim"


def test_webhook_query_rejects_unsigned_request(pipeline: RagPipeline):
    c = client(pipeline)
    resp = c.post("/webhook/query", data=json.dumps({"question": "hi"}), content_type="application/json")
    assert resp.status_code == 401


def test_webhook_ingest_end_to_end(pipeline: RagPipeline):
    c = client(pipeline)
    body = json.dumps({"docs": [{"id": "new", "text": "a document about penguins"}]}).encode()
    resp = c.post(
        "/webhook/ingest",
        data=body,
        headers={SIGNATURE_HEADER: sign(SECRET, body)},
        content_type="application/json",
    )
    assert resp.status_code == 200
    assert resp.get_json()["ingested"][0]["id"] == "new"
