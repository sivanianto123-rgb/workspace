"""AWS Lambda handler: the serverless entry point for ragdesk.

No framework dependency (no Flask, no Mangum) -- just stdlib parsing of the
API Gateway proxy-integration event, so the deployed artifact has zero
third-party layers beyond `ragdesk` itself. The pipeline and its index are
built once at module import time (cold start) and reused across warm
invocations of the same execution environment, which is the whole reason
Lambda billing rewards keeping a function warm and light.

Two caveats worth being explicit about, because glossing over them is how
"serverless RAG" demos become production incidents:

- The index lives in the function's memory. A warm invocation after an
  `/webhook/ingest` call sees the update; a fresh cold start does not --
  it rebuilds from `data/docs` only. Real deployments persist the index
  (S3, DynamoDB, EFS) and load it at cold start instead of re-chunking
  text every time.
- Concurrent invocations of the same function do not share memory. Writes
  from one don't appear in another until it's rebuilt. This is fine for a
  demo/eval corpus; it's not a substitute for a real document store once
  write-concurrency matters.
"""

from __future__ import annotations

import base64
import json
import logging
import os
from typing import Any

from ragdesk.pipeline import RagPipeline
from ragdesk.webhook import route

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("ragdesk.lambda")

_DATA_DIR = os.environ.get("RAGDESK_DOCS_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "docs"))
_SECRET = os.environ.get("RAGDESK_WEBHOOK_SECRET", "dev-secret-change-me")

_pipeline: RagPipeline | None = None


def _get_pipeline() -> RagPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = RagPipeline()
        if os.path.isdir(_DATA_DIR):
            n = _pipeline.ingest_dir(_DATA_DIR)
            logger.info(json.dumps({"event": "cold_start_ingest", "docs": n}))
    return _pipeline


def _extract_request(event: dict) -> tuple[str, str, dict, bytes]:
    """Normalizes API Gateway REST (v1) and HTTP API (v2) proxy events."""
    if "requestContext" in event and "http" in event.get("requestContext", {}):
        method = event["requestContext"]["http"]["method"]
        path = event["requestContext"]["http"]["path"]
    else:
        method = event.get("httpMethod", "POST")
        path = event.get("path", event.get("rawPath", "/"))

    headers = event.get("headers") or {}
    body = event.get("body") or ""
    if event.get("isBase64Encoded"):
        raw_body = base64.b64decode(body)
    else:
        raw_body = body.encode("utf-8")
    return method, path, headers, raw_body


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    method, path, headers, raw_body = _extract_request(event)
    logger.info(json.dumps({"event": "invoke", "method": method, "path": path}))

    resp = route(_get_pipeline(), _SECRET, method, path, headers, raw_body)

    return {
        "statusCode": resp.status,
        "headers": {"Content-Type": "application/json"},
        "body": resp.to_json(),
    }
