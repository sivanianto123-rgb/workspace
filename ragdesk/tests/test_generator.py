import pytest

from ragdesk.generator import AnthropicGenerator, ExtractiveGenerator
from ragdesk.index import ScoredChunk
from ragdesk.chunking import Chunk


def make_hit(doc_id: str, text: str, score: float = 1.0) -> ScoredChunk:
    return ScoredChunk(chunk=Chunk(doc_id=doc_id, chunk_id=f"{doc_id}#0", text=text, position=0), score=score)


def test_extractive_generator_handles_no_hits():
    gen = ExtractiveGenerator()
    assert "couldn't find" in gen.generate("anything?", []).lower()


def test_extractive_generator_picks_sentence_overlapping_question():
    gen = ExtractiveGenerator(max_sentences=1)
    hits = [
        make_hit(
            "raft",
            "Raft elects a leader per term. Followers replicate the leader's log entries faithfully.",
        )
    ]
    answer = gen.generate("How does Raft elect a leader?", hits)
    assert "leader" in answer.lower()


def test_extractive_generator_falls_back_when_no_overlap():
    gen = ExtractiveGenerator(max_sentences=2)
    hits = [make_hit("doc", "This sentence mentions zebras. This one mentions giraffes only.")]
    answer = gen.generate("tell me about quasars", hits)
    assert "zebras" in answer.lower() or "giraffes" in answer.lower()


def test_anthropic_generator_requires_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    gen = AnthropicGenerator()
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        gen.generate("question", [])
