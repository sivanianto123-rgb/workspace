"""Framework-agnostic webhook handling: signature verification + request routing.

Kept independent of Flask and of Lambda's `event` shape on purpose. Both
`app.py` (local/dev) and `lambda_function.py` (serverless) parse their own
transport's request shape into plain `(headers, raw_body)` and then call the
same `handle_request` here -- the integration logic is written and tested
exactly once, and only gets a thin adapter per host.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
from dataclasses import dataclass

from ragdesk.pipeline import RagPipeline

logger = logging.getLogger("ragdesk.webhook")

SIGNATURE_HEADER = "X-Ragdesk-Signature"
_SIG_PREFIX = "sha256="


@dataclass
class WebhookResponse:
    status: int
    body: dict

    def to_json(self) -> str:
        return json.dumps(self.body)


class SignatureError(ValueError):
    pass


def sign(secret: str, raw_body: bytes) -> str:
    """Produces the `X-Ragdesk-Signature` value a caller should send."""
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"{_SIG_PREFIX}{digest}"


def verify_signature(secret: str, raw_body: bytes, header_value: str | None) -> None:
    """Raises SignatureError unless `header_value` is a valid HMAC-SHA256
    signature of `raw_body` under `secret`. Mirrors how GitHub/Stripe/Slack
    sign webhook deliveries so this generalizes to a real provider's hook."""
    if not header_value:
        raise SignatureError(f"missing {SIGNATURE_HEADER} header")
    if not header_value.startswith(_SIG_PREFIX):
        raise SignatureError(f"signature must be prefixed with '{_SIG_PREFIX}'")
    expected = sign(secret, raw_body)
    if not hmac.compare_digest(expected, header_value):
        raise SignatureError("signature mismatch")


def _get_header(headers: dict, name: str) -> str | None:
    # HTTP headers are case-insensitive; API Gateway and Flask disagree on casing.
    lower = name.lower()
    for key, value in headers.items():
        if key.lower() == lower:
            return value
    return None


def handle_query(
    pipeline: RagPipeline,
    secret: str,
    headers: dict,
    raw_body: bytes,
) -> WebhookResponse:
    """POST /webhook/query — body: {"question": str, "top_k": int?}."""
    try:
        verify_signature(secret, raw_body, _get_header(headers, SIGNATURE_HEADER))
    except SignatureError as exc:
        logger.warning(json.dumps({"event": "auth_rejected", "endpoint": "query", "reason": str(exc)}))
        return WebhookResponse(401, {"error": str(exc)})

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        return WebhookResponse(400, {"error": "body must be valid JSON"})

    question = payload.get("question")
    if not question or not isinstance(question, str):
        return WebhookResponse(400, {"error": "'question' (string) is required"})

    result = pipeline.answer(question, top_k=payload.get("top_k"))
    return WebhookResponse(200, result.to_dict())


def handle_ingest(
    pipeline: RagPipeline,
    secret: str,
    headers: dict,
    raw_body: bytes,
) -> WebhookResponse:
    """POST /webhook/ingest — body: {"docs": [{"id": str, "text": str}, ...]}
    or {"remove": [doc_id, ...]}. Models a CMS/repo "content changed" hook
    that keeps the index fresh without redeploying the function."""
    try:
        verify_signature(secret, raw_body, _get_header(headers, SIGNATURE_HEADER))
    except SignatureError as exc:
        logger.warning(json.dumps({"event": "auth_rejected", "endpoint": "ingest", "reason": str(exc)}))
        return WebhookResponse(401, {"error": str(exc)})

    try:
        payload = json.loads(raw_body or b"{}")
    except json.JSONDecodeError:
        return WebhookResponse(400, {"error": "body must be valid JSON"})

    docs = payload.get("docs", [])
    removals = payload.get("remove", [])
    if not docs and not removals:
        return WebhookResponse(400, {"error": "provide 'docs' and/or 'remove'"})

    ingested, removed = [], []
    for doc in docs:
        doc_id, text = doc.get("id"), doc.get("text")
        if not doc_id or not isinstance(text, str):
            return WebhookResponse(400, {"error": "each doc needs 'id' and 'text'"})
        chunks = pipeline.ingest_text(doc_id, text)
        ingested.append({"id": doc_id, "chunks": chunks})
    for doc_id in removals:
        removed.append({"id": doc_id, "chunks_removed": pipeline.remove_doc(doc_id)})

    return WebhookResponse(200, {"ingested": ingested, "removed": removed})


ROUTES = {
    ("POST", "/webhook/query"): handle_query,
    ("POST", "/webhook/ingest"): handle_ingest,
}


def route(
    pipeline: RagPipeline,
    secret: str,
    method: str,
    path: str,
    headers: dict,
    raw_body: bytes,
) -> WebhookResponse:
    handler = ROUTES.get((method.upper(), path))
    if handler is None:
        return WebhookResponse(404, {"error": f"no route for {method} {path}"})
    return handler(pipeline, secret, headers, raw_body)
