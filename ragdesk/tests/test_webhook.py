import json

import pytest

from ragdesk.pipeline import RagPipeline
from ragdesk.webhook import SIGNATURE_HEADER, SignatureError, route, sign, verify_signature

SECRET = "test-secret"


def test_sign_is_deterministic_and_prefixed():
    body = b'{"question": "hi"}'
    sig = sign(SECRET, body)
    assert sig.startswith("sha256=")
    assert sign(SECRET, body) == sig


def test_verify_signature_accepts_valid_signature():
    body = b'{"question": "hi"}'
    verify_signature(SECRET, body, sign(SECRET, body))


def test_verify_signature_rejects_wrong_secret():
    body = b'{"question": "hi"}'
    with pytest.raises(SignatureError):
        verify_signature(SECRET, body, sign("wrong-secret", body))


def test_verify_signature_rejects_tampered_body():
    body = b'{"question": "hi"}'
    sig = sign(SECRET, body)
    with pytest.raises(SignatureError):
        verify_signature(SECRET, b'{"question": "tampered"}', sig)


def test_verify_signature_rejects_missing_header():
    with pytest.raises(SignatureError, match="missing"):
        verify_signature(SECRET, b"{}", None)


def test_verify_signature_rejects_bad_prefix():
    with pytest.raises(SignatureError, match="prefixed"):
        verify_signature(SECRET, b"{}", "plain-not-hmac")


def test_route_query_happy_path(pipeline: RagPipeline):
    body = json.dumps({"question": "How does Raft elect a leader?"}).encode()
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/query", headers, body)
    assert resp.status == 200
    assert resp.body["sources"][0]["doc_id"] == "raftsim"


def test_route_query_rejects_bad_signature(pipeline: RagPipeline):
    body = json.dumps({"question": "anything"}).encode()
    headers = {SIGNATURE_HEADER: "sha256=deadbeef"}
    resp = route(pipeline, SECRET, "POST", "/webhook/query", headers, body)
    assert resp.status == 401


def test_route_query_rejects_missing_question(pipeline: RagPipeline):
    body = json.dumps({}).encode()
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/query", headers, body)
    assert resp.status == 400


def test_route_query_rejects_invalid_json(pipeline: RagPipeline):
    body = b"not json"
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/query", headers, body)
    assert resp.status == 400


def test_route_ingest_adds_new_doc(pipeline: RagPipeline):
    body = json.dumps({"docs": [{"id": "new", "text": "a brand new document about kangaroos"}]}).encode()
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/ingest", headers, body)
    assert resp.status == 200
    assert resp.body["ingested"][0]["id"] == "new"

    query_body = json.dumps({"question": "tell me about kangaroos"}).encode()
    query_headers = {SIGNATURE_HEADER: sign(SECRET, query_body)}
    query_resp = route(pipeline, SECRET, "POST", "/webhook/query", query_headers, query_body)
    assert query_resp.body["sources"][0]["doc_id"] == "new"


def test_route_ingest_removes_doc(pipeline: RagPipeline):
    body = json.dumps({"remove": ["raftsim"]}).encode()
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/ingest", headers, body)
    assert resp.status == 200
    assert resp.body["removed"][0]["id"] == "raftsim"
    assert resp.body["removed"][0]["chunks_removed"] > 0


def test_route_ingest_rejects_empty_payload(pipeline: RagPipeline):
    body = json.dumps({}).encode()
    headers = {SIGNATURE_HEADER: sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/ingest", headers, body)
    assert resp.status == 400


def test_route_unknown_path_returns_404(pipeline: RagPipeline):
    resp = route(pipeline, SECRET, "POST", "/webhook/nope", {}, b"{}")
    assert resp.status == 404


def test_header_lookup_is_case_insensitive(pipeline: RagPipeline):
    body = json.dumps({"question": "How does Raft elect a leader?"}).encode()
    headers = {"x-ragdesk-signature": sign(SECRET, body)}
    resp = route(pipeline, SECRET, "POST", "/webhook/query", headers, body)
    assert resp.status == 200
