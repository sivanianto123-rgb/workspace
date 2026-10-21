from ragdesk.chunking import chunk_document, split_paragraphs


def test_split_paragraphs_drops_blank_entries():
    text = "para one\n\n\npara two\n\npara three"
    assert split_paragraphs(text) == ["para one", "para two", "para three"]


def test_chunk_document_packs_short_paragraphs_together():
    text = "a" * 10 + "\n\n" + "b" * 10 + "\n\n" + "c" * 10
    chunks = chunk_document("doc", text, max_chars=50, overlap_chars=0)
    assert len(chunks) == 1
    assert chunks[0].text.count("a") == 10


def test_chunk_document_splits_when_over_max_chars():
    para_a = "a" * 40
    para_b = "b" * 40
    text = f"{para_a}\n\n{para_b}"
    chunks = chunk_document("doc", text, max_chars=50, overlap_chars=0)
    assert len(chunks) == 2
    assert chunks[0].text == para_a
    assert chunks[1].text == para_b


def test_chunk_document_keeps_oversized_paragraph_whole():
    huge = "x" * 500
    chunks = chunk_document("doc", huge, max_chars=100, overlap_chars=10)
    assert len(chunks) == 1
    assert chunks[0].text == huge


def test_chunk_ids_are_unique_and_ordered():
    text = "\n\n".join(f"paragraph {i} " + "z" * 60 for i in range(5))
    chunks = chunk_document("mydoc", text, max_chars=80, overlap_chars=5)
    ids = [c.chunk_id for c in chunks]
    assert len(ids) == len(set(ids))
    assert all(c.doc_id == "mydoc" for c in chunks)
    assert [c.position for c in chunks] == list(range(len(chunks)))


def test_overlap_carries_tail_into_next_chunk():
    para_a = "alpha " * 10
    para_b = "beta " * 10
    text = f"{para_a}\n\n{para_b}"
    chunks = chunk_document("doc", text, max_chars=len(para_a) + 5, overlap_chars=15)
    assert len(chunks) == 2
    # chunk_document strips each paragraph before packing it (see
    # split_paragraphs), so the carried tail comes from the stripped text.
    assert chunks[1].text.startswith(para_a.strip()[-15:])
