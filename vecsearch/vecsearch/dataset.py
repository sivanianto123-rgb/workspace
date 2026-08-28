"""Synthetic data helpers for tests and benchmarks."""

from __future__ import annotations

import numpy as np

_EPS = 1e-12


def generate_random_vectors(n: int, dim: int, seed: int | None = None) -> np.ndarray:
    """Return an ``(n, dim)`` array of random unit vectors.

    Directions are drawn from a standard normal and normalized, which is
    uniform on the unit sphere. Pass ``seed`` for reproducibility.
    """
    if n < 0 or dim < 1:
        raise ValueError("n must be >= 0 and dim must be >= 1")
    rng = np.random.default_rng(seed)
    vecs = rng.standard_normal((n, dim))
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    return vecs / np.maximum(norms, _EPS)
