"""Answer generation, pluggable behind a small interface.

Two backends ship:

- `ExtractiveGenerator` (default): builds an answer purely from the
  retrieved chunks, with no network call and no API key. It is what runs
  in tests, in the eval harness, and in Lambda when no LLM key is
  configured -- the integration has to be demonstrably correct on its own,
  independent of any third-party model's availability or cost.
- `AnthropicGenerator` (optional): calls the Claude API for a fluent,
  synthesized answer when `ANTHROPIC_API_KEY` is set. Swapping generators
  never touches the retriever or the webhook layer.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Protocol

from ragdesk.index import ScoredChunk, tokenize

_SENTENCE_RE = re.compile(r"(?<=[.!?])\s+")


class Generator(Protocol):
    def generate(self, question: str, hits: list[ScoredChunk]) -> str: ...


@dataclass
class ExtractiveGenerator:
    """Scores sentences from the retrieved chunks against the question and
    stitches the best ones into an answer. Deterministic and offline."""

    max_sentences: int = 3

    def generate(self, question: str, hits: list[ScoredChunk]) -> str:
        if not hits:
            return "I couldn't find anything in the knowledge base that answers this."

        q_terms = set(tokenize(question))
        candidates: list[tuple[float, str]] = []
        for hit in hits:
            for sentence in _SENTENCE_RE.split(hit.chunk.text.replace("\n", " ")):
                sentence = sentence.strip(" -#`*")
                if len(sentence) < 20:
                    continue
                overlap = len(q_terms & set(tokenize(sentence)))
                if overlap:
                    candidates.append((overlap + 0.001 * hit.score, sentence))

        if not candidates:
            # No sentence shares a term with the question; fall back to the
            # single most relevant chunk's opening sentence(s).
            top_text = hits[0].chunk.text.replace("\n", " ").strip()
            sentences = [s.strip() for s in _SENTENCE_RE.split(top_text) if s.strip()]
            return " ".join(sentences[: self.max_sentences])

        candidates.sort(key=lambda c: c[0], reverse=True)
        seen: set[str] = set()
        picked: list[str] = []
        for _, sentence in candidates:
            if sentence in seen:
                continue
            seen.add(sentence)
            picked.append(sentence)
            if len(picked) == self.max_sentences:
                break
        return " ".join(picked)


@dataclass
class AnthropicGenerator:
    """Calls Claude to synthesize an answer from the retrieved context.

    Requires `ANTHROPIC_API_KEY` and the `anthropic` package; both are
    optional so the rest of ragdesk works without either.
    """

    model: str = "claude-sonnet-5-5"
    max_tokens: int = 400

    def generate(self, question: str, hits: list[ScoredChunk]) -> str:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY is not set")
        import anthropic  # imported lazily: not a hard dependency of ragdesk

        context = "\n\n---\n\n".join(
            f"[source: {hit.chunk.doc_id}]\n{hit.chunk.text}" for hit in hits
        )
        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=self.max_tokens,
            system=(
                "Answer the question using only the provided context. "
                "If the context doesn't contain the answer, say so plainly."
            ),
            messages=[{"role": "user", "content": f"Context:\n{context}\n\nQuestion: {question}"}],
        )
        return "".join(block.text for block in response.content if hasattr(block, "text"))


def default_generator() -> Generator:
    """Picks AnthropicGenerator when a key is configured, else the offline fallback."""
    if os.environ.get("ANTHROPIC_API_KEY"):
        try:
            import anthropic  # noqa: F401

            return AnthropicGenerator()
        except ImportError:
            pass
    return ExtractiveGenerator()
