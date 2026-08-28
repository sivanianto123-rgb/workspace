"""Save / load an :class:`~vecsearch.hnsw.HNSWIndex` with pickle.

Pickle is fine at this project's scale. The whole index state -- vectors,
per-node per-layer neighbor sets, ``entry_point`` and ``max_level`` -- lives in
plain dicts and ints on the instance, so a straight pickle round-trips it
exactly. The RNG is pickled too, so a loaded index keeps inserting
deterministically from where it left off.
"""

from __future__ import annotations

import pickle
from pathlib import Path

from .hnsw import HNSWIndex

_PICKLE_PROTOCOL = pickle.HIGHEST_PROTOCOL


def save_index(index: HNSWIndex, path: str | Path) -> None:
    """Pickle ``index`` to ``path``."""
    if not isinstance(index, HNSWIndex):
        raise TypeError(f"expected an HNSWIndex, got {type(index).__name__}")
    path = Path(path)
    with path.open("wb") as fh:
        pickle.dump(index, fh, protocol=_PICKLE_PROTOCOL)


def load_index(path: str | Path) -> HNSWIndex:
    """Load an :class:`HNSWIndex` previously written by :func:`save_index`."""
    path = Path(path)
    with path.open("rb") as fh:
        index = pickle.load(fh)
    if not isinstance(index, HNSWIndex):
        raise TypeError(f"{path} did not contain an HNSWIndex")
    return index
