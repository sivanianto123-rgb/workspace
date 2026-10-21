import base64
import json

import ragdesk.lambda_function as lf
from ragdesk.webhook import SIGNATURE_HEADER, sign


def setup_function():
    # Each test gets a clean module-level pipeline rather than the
    # bundled data/docs corpus, so assertions don't depend on it.
    lf._pipeline = None


def test_cold_start_builds_pipeline_from_bundled_docs():
    pipeline = lf._get_pipeline()
    assert len(pipeline.index) > 0
    # second call reuses the same (warm) instance
    assert lf._get_pipeline() is pipeline


def test_handler_rest_api_v1_event_shape():
    body = json.dumps({"question": "What is a write-ahead log?"}).encode()
    event = {
        "httpMethod": "POST",
        "path": "/webhook/query",
        "headers": {SIGNATURE_HEADER: sign(lf._SECRET, body)},
        "body": body.decode(),
        "isBase64Encoded": False,
    }
    resp = lf.handler(event, context=None)
    assert resp["statusCode"] == 200
    payload = json.loads(resp["body"])
    assert payload["sources"][0]["doc_id"] == "txnkv"


def test_handler_http_api_v2_event_shape():
    body = json.dumps({"question": "What algorithm does vecsearch implement?"}).encode()
    event = {
        "requestContext": {"http": {"method": "POST", "path": "/webhook/query"}},
        "headers": {SIGNATURE_HEADER: sign(lf._SECRET, body)},
        "body": body.decode(),
        "isBase64Encoded": False,
    }
    resp = lf.handler(event, context=None)
    assert resp["statusCode"] == 200
    payload = json.loads(resp["body"])
    assert payload["sources"][0]["doc_id"] == "vecsearch"


def test_handler_decodes_base64_body():
    body = json.dumps({"question": "What is Raft?"}).encode()
    event = {
        "httpMethod": "POST",
        "path": "/webhook/query",
        "headers": {SIGNATURE_HEADER: sign(lf._SECRET, body)},
        "body": base64.b64encode(body).decode(),
        "isBase64Encoded": True,
    }
    resp = lf.handler(event, context=None)
    assert resp["statusCode"] == 200


def test_handler_rejects_bad_signature():
    event = {
        "httpMethod": "POST",
        "path": "/webhook/query",
        "headers": {SIGNATURE_HEADER: "sha256=deadbeef"},
        "body": json.dumps({"question": "hi"}),
        "isBase64Encoded": False,
    }
    resp = lf.handler(event, context=None)
    assert resp["statusCode"] == 401


def test_handler_unknown_route_returns_404():
    event = {
        "httpMethod": "GET",
        "path": "/not-a-route",
        "headers": {},
        "body": "",
        "isBase64Encoded": False,
    }
    resp = lf.handler(event, context=None)
    assert resp["statusCode"] == 404
