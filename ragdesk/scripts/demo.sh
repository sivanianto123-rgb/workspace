#!/usr/bin/env bash
# Starts the local dev server, fires a signed query and a signed ingest
# webhook at it with curl, and prints the responses. Run from the repo root
# (the ragdesk/ directory) with the package installed: pip install -e '.[dev]'
set -euo pipefail

export RAGDESK_WEBHOOK_SECRET="${RAGDESK_WEBHOOK_SECRET:-demo-secret}"
PORT="${PORT:-8080}"
BASE_URL="http://127.0.0.1:${PORT}"

python -m ragdesk.app &
SERVER_PID=$!
trap 'kill "$SERVER_PID" 2>/dev/null || true' EXIT

for _ in $(seq 1 20); do
  curl -sf "${BASE_URL}/health" >/dev/null 2>&1 && break
  sleep 0.25
done

sign() {
  python -m ragdesk.cli sign --secret "$RAGDESK_WEBHOOK_SECRET" --body "$1"
}

echo "== query: what algorithm does raftsim simulate? =="
BODY='{"question": "What consensus algorithm does raftsim simulate?"}'
curl -s -X POST "${BASE_URL}/webhook/query" \
  -H "Content-Type: application/json" \
  -H "X-Ragdesk-Signature: $(sign "$BODY")" \
  -d "$BODY" | python -m json.tool

echo
echo "== ingest: push a new doc, then ask about it =="
INGEST_BODY='{"docs": [{"id": "demo", "text": "The quick brown fox jumps over the lazy dog, repeatedly, in demo text."}]}'
curl -s -X POST "${BASE_URL}/webhook/ingest" \
  -H "Content-Type: application/json" \
  -H "X-Ragdesk-Signature: $(sign "$INGEST_BODY")" \
  -d "$INGEST_BODY" | python -m json.tool

QUERY_BODY='{"question": "What does the fox jump over?"}'
curl -s -X POST "${BASE_URL}/webhook/query" \
  -H "Content-Type: application/json" \
  -H "X-Ragdesk-Signature: $(sign "$QUERY_BODY")" \
  -d "$QUERY_BODY" | python -m json.tool
