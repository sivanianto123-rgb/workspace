from ragdesk.pipeline import RagPipeline


def test_ingest_text_returns_chunk_count(pipeline: RagPipeline):
    count = pipeline.ingest_text("extra", "short extra document about nothing in particular")
    assert count == 1


def test_answer_cites_correct_source_doc(pipeline: RagPipeline):
    result = pipeline.answer("How does Raft's leader get elected?")
    assert result.sources
    assert result.sources[0].doc_id == "raftsim"
    assert "leader" in result.answer.lower()


def test_answer_includes_request_id_and_latency(pipeline: RagPipeline):
    result = pipeline.answer("What is HNSW used for?")
    assert result.request_id
    assert result.latency_ms >= 0
    d = result.to_dict()
    assert d["request_id"] == result.request_id
    assert "sources" in d and isinstance(d["sources"], list)


def test_remove_doc_drops_it_from_future_retrieval(pipeline: RagPipeline):
    removed = pipeline.remove_doc("raftsim")
    assert removed > 0
    result = pipeline.answer("How does Raft's leader get elected?")
    assert all(s.doc_id != "raftsim" for s in result.sources)


def test_reingesting_same_doc_id_replaces_old_content(pipeline: RagPipeline):
    pipeline.ingest_text("raftsim", "completely different content about oceanography")
    result = pipeline.answer("Tell me about oceanography")
    assert result.sources[0].doc_id == "raftsim"
    assert "leader" not in " ".join(s.excerpt for s in result.sources).lower()
