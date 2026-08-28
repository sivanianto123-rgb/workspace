"""vecsearch: vector search experiments.

The brute-force index in :mod:`vecsearch.brute_force` computes exact nearest
neighbours and serves as the ground truth for measuring the accuracy of
approximate indexes (HNSW) added later.
"""

from .brute_force import BruteForceIndex
from .dataset import generate_random_vectors
from .distance import cosine_distance, euclidean_distance
from .hnsw import HNSWIndex
from .nsw import NSWGraph, Node

__all__ = [
    "BruteForceIndex",
    "HNSWIndex",
    "NSWGraph",
    "Node",
    "generate_random_vectors",
    "cosine_distance",
    "euclidean_distance",
]

__version__ = "0.1.0"
