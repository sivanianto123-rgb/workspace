"""Navigable Small World (NSW) graph: a single-layer approximate index.

This proves the core idea behind HNSW -- *search a graph by greedy expansion
instead of scanning every vector* -- without the hierarchy. Adding the layered
structure on top of this is the next milestone.

Graph storage is deliberately plain: two dicts keyed by integer id, one holding
vectors and one holding neighbor-id sets (a dict-of-sets adjacency list). A
:class:`Node` is just a read-only view assembled on demand.
"""

from __future__ import annotations

import heapq
from typing import NamedTuple

import numpy as np

from .distance import cosine_distance, euclidean_distance

_METRICS = {
    "cosine": cosine_distance,
    "euclidean": euclidean_distance,
    "l2": euclidean_distance,
}


class Node(NamedTuple):
    """A read-only view of one graph node."""

    id: int
    vector: np.ndarray
    neighbors: frozenset[int]


class NSWGraph:
    """An incrementally-built Navigable Small World graph.

    Every ``insert`` connects the new node to the ``m`` closest nodes found by a
    greedy beam search, and those edges are bidirectional -- so early nodes
    accumulate long-range links and later nodes get short-range ones, which is
    what makes the graph navigable.
    """

    def __init__(self, seed: int | None = None, metric: str = "cosine") -> None:
        try:
            self._distance_fn = _METRICS[metric]
        except KeyError:
            raise ValueError(
                f"unknown metric {metric!r}; choose from {sorted(_METRICS)}"
            ) from None
        self.metric = metric
        self._vectors: dict[int, np.ndarray] = {}
        self._neighbors: dict[int, set[int]] = {}
        self._next_id = 0
        self._rng = np.random.default_rng(seed)

    # -- introspection -------------------------------------------------------

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, node_id: int) -> bool:
        return node_id in self._vectors

    def node(self, node_id: int) -> Node:
        """Return a :class:`Node` view for ``node_id``."""
        return Node(
            id=node_id,
            vector=self._vectors[node_id],
            neighbors=frozenset(self._neighbors[node_id]),
        )

    # -- distance helper ---------------------------------------------------

    def _distance(self, query: np.ndarray, vector: np.ndarray) -> float:
        return float(self._distance_fn(query, vector))

    # -- core search primitive ------------------------------------------

    def _beam_search(
        self, query: np.ndarray, entry_id: int, ef: int
    ) -> list[tuple[float, int]]:
        """Greedy best-first expansion from ``entry_id``.

        Maintains a min-heap of candidates to explore and a bounded max-heap of
        the ``ef`` best nodes seen so far. Pops the nearest candidate, expands
        its unvisited neighbors, and stops once the nearest remaining candidate
        is farther than the current worst of the best set. Returns up to ``ef``
        ``(distance, id)`` pairs sorted nearest-first.
        """
        d_entry = self._distance(query, self._vectors[entry_id])
        candidates: list[tuple[float, int]] = [(d_entry, entry_id)]  # min-heap
        best: list[tuple[float, int]] = [(-d_entry, entry_id)]  # max-heap: (-dist, id)
        visited: set[int] = {entry_id}

        while candidates:
            dist_c, c = heapq.heappop(candidates)
            worst_best = -best[0][0]
            if dist_c > worst_best and len(best) >= ef:
                break  # nothing left can improve the best set

            for nb in self._neighbors[c]:
                if nb in visited:
                    continue
                visited.add(nb)
                d_nb = self._distance(query, self._vectors[nb])
                worst_best = -best[0][0]
                if len(best) < ef or d_nb < worst_best:
                    heapq.heappush(candidates, (d_nb, nb))
                    heapq.heappush(best, (-d_nb, nb))
                    if len(best) > ef:
                        heapq.heappop(best)

        return sorted((-neg_d, node_id) for neg_d, node_id in best)

    # -- construction ----------------------------------------------------

    def _random_entry(self, exclude: int | None = None) -> int:
        ids = [i for i in self._vectors if i != exclude]
        return int(self._rng.choice(ids))

    def insert(
        self, vector: np.ndarray, ef_construction: int = 50, m: int = 8
    ) -> int:
        """Add ``vector`` to the graph and return its assigned id."""
        vector = np.asarray(vector, dtype=np.float64)
        if vector.ndim != 1:
            raise ValueError(f"expected a 1-D vector, got shape {vector.shape}")

        new_id = self._next_id
        self._next_id += 1

        if not self._vectors:
            self._vectors[new_id] = vector
            self._neighbors[new_id] = set()
            return new_id

        entry_id = self._random_entry()
        candidates = self._beam_search(vector, entry_id, ef_construction)
        chosen = [node_id for _, node_id in candidates[:m]]

        self._vectors[new_id] = vector
        self._neighbors[new_id] = set(chosen)
        for nb in chosen:
            self._neighbors[nb].add(new_id)
        return new_id

    # -- query -------------------------------------------------------------

    def search(
        self, query: np.ndarray, k: int, ef_search: int = 50
    ) -> tuple[np.ndarray, np.ndarray]:
        """Approximate ``k`` nearest neighbours of ``query``.

        Returns ``(ids, distances)`` sorted nearest-first, length
        ``min(k, len(self))``. ``ef_search`` widens the beam: larger is slower
        but more accurate.
        """
        if k < 1:
            raise ValueError("k must be >= 1")
        if not self._vectors:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)

        query = np.asarray(query, dtype=np.float64)
        entry_id = self._random_entry()
        results = self._beam_search(query, entry_id, max(ef_search, k))[:k]

        ids = np.fromiter((i for _, i in results), dtype=np.int64, count=len(results))
        dists = np.fromiter((d for d, _ in results), dtype=np.float64, count=len(results))
        return ids, dists
