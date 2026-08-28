"""Vectorized distance functions.

Every function accepts either a single pair of vectors ``(dim,)`` vs ``(dim,)``
or a batch ``(n, dim)`` vs a single query ``(dim,)`` (in either argument
position). Batching relies on NumPy broadcasting over the last axis, so the
batched path costs one matrix op rather than a Python loop.
"""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def _unit(x: np.ndarray) -> np.ndarray:
    """Return ``x`` scaled to unit L2 norm along the last axis.

    A zero vector is left effectively zero (its norm is floored at ``_EPS``)
    rather than producing ``nan``/``inf``.
    """
    norm = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.maximum(norm, _EPS)


def cosine_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Cosine distance ``1 - cos(a, b)``.

    Result is in ``[0, 2]``. Shapes:

    * ``(dim,)``  vs ``(dim,)``   -> scalar
    * ``(n, dim)`` vs ``(dim,)``  -> ``(n,)``
    * ``(dim,)``  vs ``(n, dim)`` -> ``(n,)``
    """
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    sim = np.sum(_unit(a) * _unit(b), axis=-1)
    # Guard against tiny floating-point excursions outside [-1, 1].
    sim = np.clip(sim, -1.0, 1.0)
    return 1.0 - sim


def euclidean_distance(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Euclidean (L2) distance. Same broadcasting rules as :func:`cosine_distance`."""
    a = np.asarray(a, dtype=np.float64)
    b = np.asarray(b, dtype=np.float64)
    diff = a - b
    return np.sqrt(np.sum(diff * diff, axis=-1))
