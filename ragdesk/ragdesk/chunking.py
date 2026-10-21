"""Splits documents into overlapping, paragraph-aware chunks for indexing."""

from __future__ import annotations

import re
from dataclasses import dataclass

_WHITESPACE_RUN = re.compile(r"\n{2,}")


@dataclass(frozen=True)
class Chunk:
    doc_id: str
    chunk_id: str
    text: str
    position: int


def split_paragraphs(text: str) -> list[str]:
    """Splits on blank lines, dropping fenced-code and empty paragraphs."""
    raw = _WHITESPACE_RUN.split(text.strip())
    return [p.strip() for p in raw if p.strip()]


def chunk_document(
    doc_id: str,
    text: str,
    *,
    max_chars: int = 900,
    overlap_chars: int = 150,
) -> list[Chunk]:
    """Greedily packs paragraphs into chunks of at most `max_chars`.

    A paragraph longer than `max_chars` on its own is kept whole rather than
    cut mid-sentence -- retrieval quality suffers less from an oversized
    chunk than from a chunk that truncates a code block or a table.
    `overlap_chars` of trailing text from the previous chunk is carried into
    the next one so a fact split across a chunk boundary is still retrievable
    from either side.
    """
    paragraphs = split_paragraphs(text)
    chunks: list[Chunk] = []
    current = ""
    position = 0

    def flush(carry_overlap: bool) -> None:
        nonlocal current, position
        if not current.strip():
            return
        chunks.append(
            Chunk(
                doc_id=doc_id,
                chunk_id=f"{doc_id}#{position}",
                text=current.strip(),
                position=position,
            )
        )
        position += 1
        # `current[-0:]` is the *whole* string in Python, not an empty
        # slice, so overlap_chars == 0 needs its own branch.
        current = current[-overlap_chars:] if carry_overlap and overlap_chars > 0 else ""

    for para in paragraphs:
        candidate = f"{current}\n\n{para}" if current else para
        if len(candidate) <= max_chars or not current:
            current = candidate
        else:
            flush(carry_overlap=True)
            current = f"{current}\n\n{para}" if current else para
    flush(carry_overlap=False)

    return chunks


def chunk_documents(docs: dict[str, str], **kwargs) -> list[Chunk]:
    """Chunks a {doc_id: text} mapping, preserving document order."""
    out: list[Chunk] = []
    for doc_id, text in docs.items():
        out.extend(chunk_document(doc_id, text, **kwargs))
    return out
