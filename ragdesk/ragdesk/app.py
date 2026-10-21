"""Local/dev host for ragdesk: a thin Flask adapter over webhook.route().

Run with `python -m ragdesk.app` or via `scripts/demo.sh`. The same
`route()` call this uses is exactly what `lambda_function.py` calls in
production, so behavior verified here carries over to the deployed function.
"""

from __future__ import annotations

import logging
import os

from flask import Flask, Response, request

from ragdesk.pipeline import RagPipeline
from ragdesk.webhook import route

logging.basicConfig(level=logging.INFO, format="%(message)s")

DEFAULT_SECRET = "dev-secret-change-me"


def create_app(pipeline: RagPipeline | None = None, secret: str | None = None) -> Flask:
    app = Flask(__name__)
    app.config["pipeline"] = pipeline or _default_pipeline()
    app.config["secret"] = secret or os.environ.get("RAGDESK_WEBHOOK_SECRET", DEFAULT_SECRET)

    @app.route("/webhook/<action>", methods=["POST"])
    def webhook(action: str) -> Response:
        resp = route(
            app.config["pipeline"],
            app.config["secret"],
            "POST",
            f"/webhook/{action}",
            dict(request.headers),
            request.get_data(),
        )
        return Response(resp.to_json(), status=resp.status, mimetype="application/json")

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        return Response('{"status": "ok"}', mimetype="application/json")

    return app


def _default_pipeline() -> RagPipeline:
    pipeline = RagPipeline()
    data_dir = os.environ.get("RAGDESK_DOCS_DIR", os.path.join(os.path.dirname(__file__), "..", "data", "docs"))
    if os.path.isdir(data_dir):
        pipeline.ingest_dir(data_dir)
    return pipeline


app = create_app()

if __name__ == "__main__":
    app.run(port=int(os.environ.get("PORT", 8080)), debug=False)
