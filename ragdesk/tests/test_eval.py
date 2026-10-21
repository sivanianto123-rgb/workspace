from pathlib import Path

from eval.run_eval import DEFAULT_DOCS_DIR, HERE, load_dataset, run

DATASET_PATH = HERE / "dataset.jsonl"


def test_dataset_file_is_well_formed():
    cases = load_dataset(DATASET_PATH)
    assert len(cases) >= 10
    for case in cases:
        assert {"id", "question", "expected_doc_id", "expected_keywords"} <= case.keys()


def test_eval_run_achieves_strong_retrieval_hit_rate():
    report = run(DATASET_PATH, DEFAULT_DOCS_DIR, top_k=4)
    assert report["summary"]["num_cases"] == len(load_dataset(DATASET_PATH))
    # Not 100%: the point of the eval is to measure, not to be tuned to pass.
    assert report["summary"]["retrieval_hit_rate"] >= 0.7


def test_eval_case_reports_missing_keywords_when_recall_is_partial():
    report = run(DATASET_PATH, DEFAULT_DOCS_DIR, top_k=4)
    for case in report["cases"]:
        if case["keyword_recall"] < 1.0:
            assert case["missing_keywords"]
