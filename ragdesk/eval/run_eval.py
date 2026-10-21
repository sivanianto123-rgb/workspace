"""Retrieval + answer eval harness for ragdesk.

This is the piece that turns "the assistant seems to work" into a number
you can diff across changes: swap the chunk size, swap the generator,
change top_k, and re-run this to see whether it actually helped.

Two metrics, deliberately simple and dependency-free:

- `retrieval_hit@k`: did a chunk from the question's expected source
  document appear anywhere in the top-k retrieved chunks? This isolates
  the retriever from the generator -- a wrong answer with a right source
  is a generator problem, not a retrieval problem.
- `keyword_recall`: of the keywords a human judge would expect to see in
  a correct answer, what fraction actually appear (case-insensitive) in
  the generated answer? A cheap, deterministic stand-in for an LLM-judge
  grader, chosen so the eval runs offline with no API key and no
  nondeterminism.

Usage:
    python -m eval.run_eval
    python -m eval.run_eval --dataset eval/dataset.jsonl --top-k 4 --out eval/results.json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from ragdesk.generator import ExtractiveGenerator  # noqa: E402
from ragdesk.pipeline import RagPipeline  # noqa: E402

DEFAULT_DOCS_DIR = REPO_ROOT / "data" / "docs"


def load_dataset(path: str | Path) -> list[dict]:
    cases = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                cases.append(json.loads(line))
    return cases


def evaluate_case(pipeline: RagPipeline, case: dict, top_k: int) -> dict:
    result = pipeline.answer(case["question"], top_k=top_k)
    retrieved_docs = {s.doc_id for s in result.sources}
    retrieval_hit = case["expected_doc_id"] in retrieved_docs

    answer_lower = result.answer.lower()
    keywords = case.get("expected_keywords", [])
    hits = [kw for kw in keywords if kw.lower() in answer_lower]
    keyword_recall = len(hits) / len(keywords) if keywords else 1.0

    return {
        "id": case["id"],
        "question": case["question"],
        "expected_doc_id": case["expected_doc_id"],
        "retrieved_docs": sorted(retrieved_docs),
        "retrieval_hit": retrieval_hit,
        "answer": result.answer,
        "keyword_recall": round(keyword_recall, 3),
        "missing_keywords": [kw for kw in keywords if kw not in hits],
        "latency_ms": round(result.latency_ms, 2),
    }


def run(dataset_path: str | Path, docs_dir: str | Path, top_k: int) -> dict:
    pipeline = RagPipeline(generator=ExtractiveGenerator(), top_k=top_k)
    pipeline.ingest_dir(docs_dir)

    cases = load_dataset(dataset_path)
    results = [evaluate_case(pipeline, case, top_k) for case in cases]

    n = len(results) or 1
    summary = {
        "num_cases": len(results),
        "retrieval_hit_rate": round(sum(r["retrieval_hit"] for r in results) / n, 3),
        "mean_keyword_recall": round(sum(r["keyword_recall"] for r in results) / n, 3),
        "mean_latency_ms": round(sum(r["latency_ms"] for r in results) / n, 2),
    }
    return {"summary": summary, "cases": results}


def _print_report(report: dict) -> None:
    summary = report["summary"]
    print(f"cases: {summary['num_cases']}")
    print(f"retrieval hit-rate@k: {summary['retrieval_hit_rate']:.0%}")
    print(f"mean keyword recall:  {summary['mean_keyword_recall']:.0%}")
    print(f"mean latency:         {summary['mean_latency_ms']:.2f} ms")
    print()
    for case in report["cases"]:
        mark = "✓" if case["retrieval_hit"] else "✗"
        print(f"  [{mark}] {case['id']:4s} recall={case['keyword_recall']:.2f}  {case['question']}")
        if case["missing_keywords"]:
            print(f"        missing: {case['missing_keywords']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run the ragdesk retrieval+answer eval suite")
    parser.add_argument("--dataset", default=str(HERE / "dataset.jsonl"))
    parser.add_argument("--docs-dir", default=str(DEFAULT_DOCS_DIR))
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--out", default=str(HERE / "results.json"))
    parser.add_argument("--fail-under", type=float, default=0.0, help="exit 1 if hit-rate falls below this")
    args = parser.parse_args(argv)

    report = run(args.dataset, args.docs_dir, args.top_k)
    _print_report(report)

    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)
    print(f"\nwrote {args.out}")

    if report["summary"]["retrieval_hit_rate"] < args.fail_under:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
