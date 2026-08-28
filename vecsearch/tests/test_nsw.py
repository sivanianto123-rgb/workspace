"""Recall check for the single-layer NSW graph against exact ground truth.

This is the approximate, un-tuned version: recall should be clearly useful but
short of 1.0. The printed number is the baseline to beat once the hierarchical
(HNSW) layers are added.
"""

import numpy as np
import pytest

from vecsearch import BruteForceIndex, NSWGraph, generate_random_vectors

N_VECTORS = 500
DIM = 32
N_QUERIES = 25
K = 10
EF = 50


@pytest.fixture(scope="module")
def indexes():
    data = generate_random_vectors(N_VECTORS, DIM, seed=7)

    truth = BruteForceIndex()
    truth.add(data)

    graph = NSWGraph(seed=42, metric="cosine")
    for vec in data:
        graph.insert(vec, ef_construction=EF, m=8)

    return truth, graph


def _recall(truth, graph):
    queries = generate_random_vectors(N_QUERIES, DIM, seed=99)
    per_query = []
    for q in queries:
        true_ids = set(truth.search(q, k=K, metric="cosine")[0].tolist())
        approx_ids = set(graph.search(q, k=K, ef_search=EF)[0].tolist())
        per_query.append(len(true_ids & approx_ids) / K)
    return float(np.mean(per_query)), per_query


def test_nsw_recall_vs_brute_force(indexes):
    truth, graph = indexes
    assert len(graph) == N_VECTORS

    recall, per_query = _recall(truth, graph)

    print(
        f"\nNSW single-layer recall@{K}: {recall:.3f} "
        f"(min {min(per_query):.2f}, max {max(per_query):.2f}, "
        f"over {N_QUERIES} queries, N={N_VECTORS}, dim={DIM}, ef={EF})"
    )

    # Decent but imperfect: far above a random baseline (K/N ~= 0.02). The
    # single-layer graph does well at this scale; the hierarchical version is
    # expected to hold recall while touching fewer nodes as N grows.
    assert recall > 0.75


def test_search_returns_sorted_k(indexes):
    _, graph = indexes
    q = generate_random_vectors(1, DIM, seed=1)[0]
    ids, dists = graph.search(q, k=K, ef_search=EF)
    assert len(ids) == K
    assert len(dists) == K
    assert list(dists) == sorted(dists)
    assert len(set(ids.tolist())) == K  # no duplicates


def test_edges_are_bidirectional(indexes):
    _, graph = indexes
    for node_id in range(len(graph)):
        for nb in graph.node(node_id).neighbors:
            assert node_id in graph.node(nb).neighbors


def test_empty_and_single_node_graph():
    graph = NSWGraph(seed=0)
    ids, dists = graph.search(np.zeros(DIM), k=5)
    assert len(ids) == 0 and len(dists) == 0

    graph.insert(generate_random_vectors(1, DIM, seed=0)[0])
    assert len(graph) == 1
    ids, _ = graph.search(generate_random_vectors(1, DIM, seed=2)[0], k=5)
    assert list(ids) == [0]
    assert graph.node(0).neighbors == frozenset()
