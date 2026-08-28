"""Exact nearest-neighbour search by brute force.

This is intentionally simple and fully vectorized: every query is compared
against the entire stored matrix in one NumPy op. It is the ground truth for
measuring the recall of approximate indexes (HNSW) later, so correctness beats
cleverness here.
"""

from __future__ import annotations

import numpy as np

from .distance import cosine_distance, euclidean_distance

_METRICS = {
    "cosine": cosine_distance,
    "euclidean": euclidean_distance,
    "l2": euclidean_distance,
}


class BruteForceIndex:
    """Stores vectors and answers exact k-NN queries against all of them."""

    def __init__(self) -> None:
        self._vectors: np.ndarray | None = None

    # -- construction ----------------------------------------------------

    def add(self, vectors: np.ndarray) -> None:
        """Append ``(m, dim)`` vectors to the index.

        Ids are assigned by insertion order: the first row ever added is id 0,
        and each subsequent row gets the next integer.
        """
        vectors = np.asarray(vectors, dtype=np.float64)
        if vectors.ndim != 2:
            raise ValueError(f"expected a 2-D (m, dim) array, got shape {vectors.shape}")
        if self._vectors is None:
            self._vectors = vectors.copy()
        elif vectors.shape[1] != self._vectors.shape[1]:
            raise ValueError(
                f"dimension mismatch: index holds dim={self._vectors.shape[1]}, "
                f"got dim={vectors.shape[1]}"
            )
        else:
            self._vectors = np.vstack((self._vectors, vectors))

    # -- introspection -------------------------------------------------------

    def __len__(self) -> int:
        return 0 if self._vectors is None else self._vectors.shape[0]

    @property
    def vectors(self) -> np.ndarray:
        """Read-only view of the stored matrix, shape ``(n, dim)``."""
        if self._vectors is None:
            return np.empty((0, 0))
        view = self._vectors.view()
        view.flags.writeable = False
        return view

    # -- query -------------------------------------------------------------

    def search(
        self, query: np.ndarray, k: int, metric: str = "cosine"
    ) -> tuple[np.ndarray, np.ndarray]:
        """Return the exact ``k`` nearest neighbours of ``query``.

        Returns ``(ids, distances)``, both length ``min(k, len(self))``, sorted
        by ascending distance. Ties are broken by ascending id so the result is
        deterministic.
        """
        if self._vectors is None:
            raise ValueError("index is empty; add() vectors before searching")
        if k < 1:
            raise ValueError("k must be >= 1")
        try:
            metric_fn = _METRICS[metric]
        except KeyError:
            raise ValueError(
                f"unknown metric {metric!r}; choose from {sorted(_METRICS)}"
            ) from None

        query = np.asarray(query, dtype=np.float64)
        if query.ndim != 1 or query.shape[0] != self._vectors.shape[1]:
            raise ValueError(
                f"query must be 1-D with dim={self._vectors.shape[1]}, "
                f"got shape {query.shape}"
            )

        distances = metric_fn(self._vectors, query)  # (n,), one vectorized pass

        n = distances.shape[0]
        k = min(k, n)
        # Cheap top-k: partition to get the k smallest, then order just those.
        candidates = np.argpartition(distances, k - 1)[:k]
        # lexsort: primary key = distance, secondary key = id (ascending).
        order = np.lexsort((candidates, distances[candidates]))
        ids = candidates[order]
        return ids, distances[ids]
