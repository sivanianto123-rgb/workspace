"""HNSW: the hierarchical multi-layer version of the NSW graph.

Same greedy graph search as :mod:`vecsearch.nsw`, but nodes live on a stack of
layers. Higher layers are exponentially sparser, so a query first takes long
hops near the top and progressively shorter hops on the way down, reaching
layer 0 already close to the answer.

This is a separate index from :class:`vecsearch.nsw.NSWGraph`; that one stays
around for comparison.

Vectors are stored in a metric-friendly form (L2-normalized for cosine) so the
hot distance call is a single dot product or difference norm -- this is what
keeps building a 50k-node graph in pure Python tractable.
"""

from __future__ import annotations

import heapq
import math

import numpy as np

_EPS = 1e-12
_VALID_METRICS = ("cosine", "euclidean", "l2")


class HNSWIndex:
    """Incrementally-built Hierarchical Navigable Small World index."""

    def __init__(
        self,
        m: int = 8,
        m0: int | None = None,
        seed: int | None = None,
        metric: str = "cosine",
        heuristic: bool = True,
    ) -> None:
        if m < 2:
            raise ValueError("m must be >= 2 (level assignment uses 1 / ln(m))")
        if metric not in _VALID_METRICS:
            raise ValueError(
                f"unknown metric {metric!r}; choose from {list(_VALID_METRICS)}"
            )

        self.metric = metric
        self.m = m
        self.m0 = 2 * m if m0 is None else m0
        self.heuristic = heuristic
        self._level_mult = 1.0 / math.log(m)  # 1 / ln(m)

        self._vectors: dict[int, np.ndarray] = {}
        # node_id -> {layer -> set(neighbor_id)}
        self._neighbors: dict[int, dict[int, set[int]]] = {}
        self._node_level: dict[int, int] = {}
        self.entry_point: int | None = None
        self.max_level: int = -1
        self._next_id = 0
        self._rng = np.random.default_rng(seed)

    # -- introspection -------------------------------------------------------

    def __len__(self) -> int:
        return len(self._vectors)

    def __contains__(self, node_id: int) -> bool:
        return node_id in self._vectors

    def node_level(self, node_id: int) -> int:
        return self._node_level[node_id]

    def neighbors(self, node_id: int, layer: int) -> frozenset[int]:
        return frozenset(self._neighbors[node_id].get(layer, ()))

    # -- vector storage / distance ------------------------------------------

    def _prepare(self, vector: np.ndarray) -> np.ndarray:
        """Convert an input vector to the stored form for this metric."""
        vector = np.asarray(vector, dtype=np.float64).ravel()
        if self.metric == "cosine":
            norm = float(np.sqrt(vector @ vector))
            return vector / norm if norm > _EPS else vector
        return vector

    def _distance(self, a: np.ndarray, b: np.ndarray) -> float:
        if self.metric == "cosine":  # a, b are unit vectors
            return 1.0 - float(a @ b)
        diff = a - b
        return float(np.sqrt(diff @ diff))

    # -- level assignment -------------------------------------------------

    def _assign_level(self) -> int:
        """Draw a layer for a new node from an exponential distribution.

        ``level = floor(-ln(U) / ln(m))`` with ``U`` uniform in ``(0, 1]``. The
        probability of reaching layer ``l`` is ``m**-l``, so each layer up holds
        roughly ``1 / m`` of the layer below it.
        """
        u = 1.0 - self._rng.random()  # (0, 1], avoids ln(0)
        return int(math.floor(-math.log(u) * self._level_mult))

    # -- core search primitive ------------------------------------------

    def _search_layer(
        self,
        query: np.ndarray,
        entry_ids: list[int],
        ef: int,
        layer: int,
    ) -> list[tuple[float, int]]:
        """Beam search restricted to one layer's edges.

        This is :meth:`vecsearch.nsw.NSWGraph._beam_search`, generalized to take
        several entry points and to follow only ``self._neighbors[c][layer]``.
        Returns up to ``ef`` ``(distance, id)`` pairs, nearest first.
        """
        vectors = self._vectors
        neighbors = self._neighbors
        visited: set[int] = set(entry_ids)
        candidates: list[tuple[float, int]] = []  # min-heap by distance
        best: list[tuple[float, int]] = []  # max-heap: (-distance, id)

        for eid in entry_ids:
            d = self._distance(query, vectors[eid])
            heapq.heappush(candidates, (d, eid))
            heapq.heappush(best, (-d, eid))
        while len(best) > ef:
            heapq.heappop(best)

        while candidates:
            dist_c, c = heapq.heappop(candidates)
            if dist_c > -best[0][0] and len(best) >= ef:
                break

            for nb in neighbors[c].get(layer, ()):
                if nb in visited:
                    continue
                visited.add(nb)
                d_nb = self._distance(query, vectors[nb])
                if len(best) < ef or d_nb < -best[0][0]:
                    heapq.heappush(candidates, (d_nb, nb))
                    heapq.heappush(best, (-d_nb, nb))
                    if len(best) > ef:
                        heapq.heappop(best)

        return sorted((-neg_d, node_id) for neg_d, node_id in best)

    # -- neighbor selection ------------------------------------------------

    def _select_neighbors_heuristic(
        self,
        query_vector: np.ndarray,
        candidates: list[tuple[int, np.ndarray, float]],
        m: int,
    ) -> list[int]:
        """Diversity heuristic from the HNSW paper (Algorithm 4).

        ``candidates`` is ``(id, vector, distance_to_query)`` sorted nearest
        first. Walking outward, a candidate is kept only if it is closer to the
        query than to every already-selected neighbor -- so a candidate that
        merely duplicates the direction of one we already have is skipped. This
        spreads a node's edges across directions instead of piling them into the
        densest cluster. Fewer than ``m`` results is allowed.
        """
        selected: list[tuple[int, np.ndarray]] = []
        for cand_id, cand_vec, d_query in candidates:
            if len(selected) >= m:
                break
            if all(
                d_query < self._distance(cand_vec, sel_vec)
                for _, sel_vec in selected
            ):
                selected.append((cand_id, cand_vec))
        return [cid for cid, _ in selected]

    def _select(
        self, query_vector: np.ndarray, found: list[tuple[float, int]], m: int
    ) -> list[int]:
        """Pick up to ``m`` neighbors from a beam-search result."""
        if not self.heuristic:
            return [node_id for _, node_id in found[:m]]
        candidates = [(node_id, self._vectors[node_id], d) for d, node_id in found]
        return self._select_neighbors_heuristic(query_vector, candidates, m)

    def _trim(self, node_id: int, layer: int, max_conn: int) -> None:
        """Prune ``node_id``'s edge list at ``layer`` back to ``max_conn``.

        Uses the same diversity heuristic as insertion; reverse edges of any
        dropped link are removed so the layer stays undirected.
        """
        nbrs = self._neighbors[node_id][layer]
        if len(nbrs) <= max_conn:
            return
        v = self._vectors[node_id]
        ranked = sorted(
            ((o, self._distance(v, self._vectors[o])) for o in nbrs),
            key=lambda t: t[1],
        )
        found = [(dist, o) for o, dist in ranked]
        keep = set(self._select(v, found, max_conn))
        for dropped in nbrs - keep:
            self._neighbors[dropped][layer].discard(node_id)
        self._neighbors[node_id][layer] = keep

    # -- construction ----------------------------------------------------

    def insert(self, vector: np.ndarray, ef_construction: int = 100) -> int:
        """Add ``vector`` to the index and return its assigned id."""
        raw = np.asarray(vector, dtype=np.float64)
        if raw.ndim != 1:
            raise ValueError(f"expected a 1-D vector, got shape {raw.shape}")
        stored = self._prepare(raw)

        node_id = self._next_id
        self._next_id += 1
        level = self._assign_level()

        self._vectors[node_id] = stored
        self._neighbors[node_id] = {lyr: set() for lyr in range(level + 1)}
        self._node_level[node_id] = level

        if self.entry_point is None:
            self.entry_point = node_id
            self.max_level = level
            return node_id

        ep = self.entry_point
        top = self.max_level

        # Phase 1: from the top layer down to just above the new node's level,
        # greedily hop to the single closest node -- this only picks a good
        # entry point, it makes no edges.
        for lc in range(top, level, -1):
            ep = self._search_layer(stored, [ep], ef=1, layer=lc)[0][1]

        # Phase 2: from min(level, top) down to layer 0, connect the new node.
        ep_ids = [ep]
        for lc in range(min(level, top), -1, -1):
            found = self._search_layer(stored, ep_ids, ef_construction, layer=lc)
            max_conn = self.m0 if lc == 0 else self.m
            selected = self._select(stored, found, max_conn)

            for nb in selected:
                self._neighbors[node_id][lc].add(nb)
                self._neighbors[nb][lc].add(node_id)
            for nb in selected:
                self._trim(nb, lc, max_conn)

            ep_ids = [node_id for _, node_id in found] or ep_ids

        if level > self.max_level:
            self.entry_point = node_id
            self.max_level = level
        return node_id

    # -- query -------------------------------------------------------------

    def search(
        self, query: np.ndarray, k: int, ef_search: int = 50
    ) -> tuple[np.ndarray, np.ndarray]:
        """Approximate ``k`` nearest neighbours of ``query``.

        Greedy ``ef=1`` descent through the upper layers, then one wide
        ``ef_search`` beam search at layer 0. Returns ``(ids, distances)``
        sorted nearest-first, length ``min(k, len(self))``.
        """
        if k < 1:
            raise ValueError("k must be >= 1")
        if self.entry_point is None:
            return np.empty(0, dtype=np.int64), np.empty(0, dtype=np.float64)

        query = self._prepare(query)
        ep = self.entry_point
        for lc in range(self.max_level, 0, -1):
            ep = self._search_layer(query, [ep], ef=1, layer=lc)[0][1]

        found = self._search_layer(query, [ep], max(ef_search, k), layer=0)[:k]
        ids = np.fromiter((i for _, i in found), dtype=np.int64, count=len(found))
        dists = np.fromiter((d for d, _ in found), dtype=np.float64, count=len(found))
        return ids, dists
