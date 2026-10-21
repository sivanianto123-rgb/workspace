"""Command-line entry points: run the local server, sign a test request, or
run the retrieval+answer eval."""

from __future__ import annotations

import argparse
import json
import sys

from ragdesk.webhook import sign


def _cmd_serve(args: argparse.Namespace) -> None:
    from ragdesk.app import create_app

    app = create_app(secret=args.secret)
    app.run(port=args.port)


def _cmd_sign(args: argparse.Namespace) -> None:
    body = args.body.encode("utf-8")
    print(sign(args.secret, body))


def _cmd_eval(args: argparse.Namespace) -> None:
    from eval.run_eval import main as run_eval_main

    sys.exit(run_eval_main(["--dataset", args.dataset, "--top-k", str(args.top_k)]))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="ragdesk")
    sub = parser.add_subparsers(dest="command", required=True)

    serve = sub.add_parser("serve", help="run the local Flask dev server")
    serve.add_argument("--port", type=int, default=8080)
    serve.add_argument("--secret", default=None)
    serve.set_defaults(func=_cmd_serve)

    signer = sub.add_parser("sign", help="compute the X-Ragdesk-Signature header for a body")
    signer.add_argument("--secret", required=True)
    signer.add_argument("--body", required=True, help="raw JSON body, as a string")
    signer.set_defaults(func=_cmd_sign)

    evaluator = sub.add_parser("eval", help="run the retrieval + answer eval suite")
    evaluator.add_argument("--dataset", default="eval/dataset.jsonl")
    evaluator.add_argument("--top-k", type=int, default=4)
    evaluator.set_defaults(func=_cmd_eval)

    args = parser.parse_args(argv)
    args.func(args)


if __name__ == "__main__":
    main()
