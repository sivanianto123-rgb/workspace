"""Wires ingestion, retrieval and generation into one RAG pipeline.

Also the seam where observability lives: every `answer()` call emits one
structured log line with the question, which doc(s) backed the answer,
scores and latency -- the kind of trace you need to debug "why did the
assistant say that" after the fact, without re-running anything.
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from ragdesk.chunking import chunk_document
from ragdesk.generator import Generator, default_generator
from ragdesk.index import ScoredChunk, TfidfIndex

logger = logging.getLogger("ragdesk")


@dataclass
class Source:
    doc_id: str
    chunk_id: str
    score: float
    excerpt: str


@dataclass
class Answer:
    request_id: str
    question: str
    answer: str
    sources: list[Source]
    latency_ms: float

    def to_dict(self) -> dict:
        return {
            "request_id": self.request_id,
            "question": self.question,
            "answer": self.answer,
            "sources": [s.__dict__ for s in self.sources],
            "latency_ms": round(self.latency_ms, 2),
        }


@dataclass
class RagPipeline:
    generator: Generator = field(default_factory=default_generator)
    top_k: int = 4
    index: TfidfIndex = field(default_factory=TfidfIndex)

    def ingest_text(self, doc_id: str, text: str) -> int:
        """Chunks and (re)indexes a single document; returns chunk count."""
        self.index.remove_doc(doc_id)
        chunks = chunk_document(doc_id, text)
        self.index.upsert(chunks)
        logger.info(json.dumps({"event": "ingest", "doc_id": doc_id, "chunks": len(chunks)}))
        return len(chunks)

    def ingest_dir(self, directory: str | Path, pattern: str = "*.md") -> int:
        """Ingests every file matching `pattern` in `directory`; returns doc count."""
        count = 0
        for path in sorted(Path(directory).glob(pattern)):
            self.ingest_text(path.stem, path.read_text(encoding="utf-8"))
            count += 1
        return count

    def remove_doc(self, doc_id: str) -> int:
        removed = self.index.remove_doc(doc_id)
        logger.info(json.dumps({"event": "remove", "doc_id": doc_id, "chunks_removed": removed}))
        return removed

    def retrieve(self, question: str, top_k: int | None = None) -> list[ScoredChunk]:
        return self.index.search(question, top_k=top_k or self.top_k)

    def answer(self, question: str, top_k: int | None = None) -> Answer:
        start = time.perf_counter()
        request_id = str(uuid.uuid4())
        hits = self.retrieve(question, top_k=top_k)
        answer_text = self.generator.generate(question, hits)
        latency_ms = (time.perf_counter() - start) * 1000

        sources = [
            Source(
                doc_id=hit.chunk.doc_id,
                chunk_id=hit.chunk.chunk_id,
                score=round(hit.score, 4),
                excerpt=hit.chunk.text[:220],
            )
            for hit in hits
        ]
        logger.info(
            json.dumps(
                {
                    "event": "query",
                    "request_id": request_id,
                    "question": question,
                    "top_doc": sources[0].doc_id if sources else None,
                    "top_score": sources[0].score if sources else None,
                    "num_sources": len(sources),
                    "latency_ms": round(latency_ms, 2),
                }
            )
        )
        return Answer(
            request_id=request_id,
            question=question,
            answer=answer_text,
            sources=sources,
            latency_ms=latency_ms,
        )
