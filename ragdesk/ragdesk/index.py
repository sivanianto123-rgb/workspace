"""A from-scratch TF-IDF inverted index with cosine-similarity retrieval.

No numpy, no vector-DB dependency: the corpora this project targets (a
handful of markdown docs, chunked) are small enough that a pure-Python
inverted index is both fast enough and trivial to run inside a Lambda cold
start with zero extra layers.
"""

from __future__ import annotations

import math
import re
from collections import Counter, defaultdict
from dataclasses import dataclass

from ragdesk.chunking import Chunk

_TOKEN_RE = re.compile(r"[a-z0-9]+")

# A short stop-list rather than the usual giant one: this corpus is technical
# prose where words like "model" or "log" carry real signal.
_STOPWORDS = frozenset(
    """
    a an the and or but if then else for of to in on at by with from as is
    are was were be been being this that these those it its it's as not no
    do does did can could will would should may might must shall
    """.split()
)


def tokenize(text: str) -> list[str]:
    return [t for t in _TOKEN_RE.findall(text.lower()) if t not in _STOPWORDS and len(t) > 1]


@dataclass(frozen=True)
class ScoredChunk:
    chunk: Chunk
    score: float


class TfidfIndex:
    """In-memory TF-IDF index over a set of chunks, queryable by cosine similarity."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}
        self._term_freqs: dict[str, Counter[str]] = {}
        self._doc_freq: Counter[str] = Counter()
        self._norms: dict[str, float] = {}
        self._idf: dict[str, float] = {}
        self._dirty = True

    def __len__(self) -> int:
        return len(self._chunks)

    def upsert(self, chunks: list[Chunk]) -> None:
        """Adds or replaces chunks (keyed by chunk_id), then marks IDF stale."""
        for chunk in chunks:
            if chunk.chunk_id in self._term_freqs:
                self._remove_doc_freq(chunk.chunk_id)
            tf = Counter(tokenize(chunk.text))
            self._chunks[chunk.chunk_id] = chunk
            self._term_freqs[chunk.chunk_id] = tf
            for term in tf:
                self._doc_freq[term] += 1
        self._dirty = True

    def remove_doc(self, doc_id: str) -> int:
        """Removes every chunk belonging to `doc_id`; returns how many were removed."""
        stale = [cid for cid, c in self._chunks.items() if c.doc_id == doc_id]
        for chunk_id in stale:
            self._remove_doc_freq(chunk_id)
            del self._chunks[chunk_id]
            del self._term_freqs[chunk_id]
        if stale:
            self._dirty = True
        return len(stale)

    def _remove_doc_freq(self, chunk_id: str) -> None:
        for term in self._term_freqs[chunk_id]:
            self._doc_freq[term] -= 1
            if self._doc_freq[term] <= 0:
                del self._doc_freq[term]

    def _rebuild(self) -> None:
        n_docs = max(len(self._chunks), 1)
        self._idf = {
            term: math.log((1 + n_docs) / (1 + df)) + 1.0 for term, df in self._doc_freq.items()
        }
        self._norms = {}
        for chunk_id, tf in self._term_freqs.items():
            weight_sq = sum((count * self._idf.get(term, 0.0)) ** 2 for term, count in tf.items())
            self._norms[chunk_id] = math.sqrt(weight_sq) or 1.0
        self._dirty = False

    def search(self, query: str, top_k: int = 4) -> list[ScoredChunk]:
        if self._dirty:
            self._rebuild()
        query_tf = Counter(tokenize(query))
        if not query_tf or not self._chunks:
            return []

        query_weights = {term: count * self._idf.get(term, 0.0) for term, count in query_tf.items()}
        query_norm = math.sqrt(sum(w * w for w in query_weights.values())) or 1.0

        postings: dict[str, float] = defaultdict(float)
        for term, q_weight in query_weights.items():
            if q_weight == 0.0:
                continue
            idf = self._idf.get(term)
            if idf is None:
                continue
            for chunk_id, tf in self._term_freqs.items():
                count = tf.get(term)
                if count:
                    postings[chunk_id] += q_weight * (count * idf)

        scored = [
            ScoredChunk(chunk=self._chunks[chunk_id], score=dot / (query_norm * self._norms[chunk_id]))
            for chunk_id, dot in postings.items()
        ]
        scored.sort(key=lambda sc: sc.score, reverse=True)
        return scored[:top_k]
