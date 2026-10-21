from ragdesk.chunking import Chunk
from ragdesk.index import TfidfIndex, tokenize


def test_tokenize_lowercases_and_drops_stopwords():
    tokens = tokenize("The Leader replicates its Log to the followers.")
    assert "the" not in tokens
    assert "leader" in tokens
    assert "log" in tokens


def make_chunk(doc_id: str, chunk_id: str, text: str) -> Chunk:
    return Chunk(doc_id=doc_id, chunk_id=chunk_id, text=text, position=0)


def test_search_ranks_most_relevant_chunk_first():
    index = TfidfIndex()
    index.upsert(
        [
            make_chunk("raft", "raft#0", "Raft elects a leader who replicates a log to followers."),
            make_chunk("vec", "vec#0", "HNSW builds a hierarchical graph for nearest neighbour search."),
            make_chunk("kv", "kv#0", "A write-ahead log guarantees durability via fsync."),
        ]
    )
    hits = index.search("How does Raft elect its leader?", top_k=3)
    assert hits[0].chunk.doc_id == "raft"
    assert hits[0].score > 0


def test_search_returns_empty_for_unseen_terms():
    index = TfidfIndex()
    index.upsert([make_chunk("a", "a#0", "completely unrelated content about gardening")])
    assert index.search("quantum entanglement", top_k=3) == []


def test_search_with_empty_index_returns_empty():
    index = TfidfIndex()
    assert index.search("anything", top_k=3) == []


def test_remove_doc_drops_all_its_chunks():
    index = TfidfIndex()
    index.upsert(
        [
            make_chunk("a", "a#0", "alpha text one"),
            make_chunk("a", "a#1", "alpha text two"),
            make_chunk("b", "b#0", "beta text"),
        ]
    )
    removed = index.remove_doc("a")
    assert removed == 2
    assert len(index) == 1
    hits = index.search("alpha", top_k=5)
    assert hits == []


def test_upsert_replaces_existing_chunk_by_id():
    index = TfidfIndex()
    index.upsert([make_chunk("a", "a#0", "old content about apples")])
    index.upsert([make_chunk("a", "a#0", "new content about oranges")])
    assert len(index) == 1
    hits = index.search("oranges", top_k=1)
    assert hits and hits[0].chunk.text == "new content about oranges"
    assert index.search("apples", top_k=1) == []


def test_common_terms_score_lower_than_rare_terms():
    index = TfidfIndex()
    index.upsert(
        [
            make_chunk("a", "a#0", "common word appears here common word"),
            make_chunk("b", "b#0", "common word appears here too"),
            make_chunk("c", "c#0", "common word appears here with a rareterm"),
        ]
    )
    hits = index.search("rareterm", top_k=3)
    assert hits[0].chunk.doc_id == "c"
