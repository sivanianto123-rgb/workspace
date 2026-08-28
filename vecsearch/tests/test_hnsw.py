"""HNSW correctness + recall, side by side with the single-layer NSW graph.

Prints three recall@10 numbers on the same 500-vector dataset:
  * NSW  (single layer)
  * HNSW without the neighbor-selection heuristic (plain m-closest)
  * HNSW with the paper's diversity heuristic

so the effect of the hierarchy and of the heuristic are both visible.
"""

import numpy as np
import pytest

from vecsearch import BruteForceIndex, HNSWIndex, NSWGraph, generate_random_vectors

N_VECTORS = 500
DIM = 32
N_QUERIES = 25
K = 10
EF = 50


@pytest.fixture(scope="module")
def data():
    return generate_random_vectors(N_VECTORS, DIM, seed=7)


@pytest.fixture(scope="module")
def truth(data):
    idx = BruteForceIndex()
    idx.add(data)
    return idx


@pytest.fixture(scope="module")
def queries():
    return generate_random_vectors(N_QUERIES, DIM, seed=99)


def _recall(truth, index, queries, *, search_kwargs):
    hits = 0
    for q in queries:
        true_ids = set(truth.search(q, k=K, metric="cosine")[0].tolist())
        got = set(index.search(q, **search_kwargs)[0].tolist())
        hits += len(true_ids & got)
    return hits / (K * len(queries))


def _build_nsw(data):
    g = NSWGraph(seed=42, metric="cosine")
    for v in data:
        g.insert(v, ef_construction=EF, m=8)
    return g


def _build_hnsw(data, *, heuristic):
    idx = HNSWIndex(m=8, seed=42, metric="cosine", heuristic=heuristic)
    for v in data:
        idx.insert(v, ef_construction=100)
    return idx


def test_recall_comparison(truth, data, queries):
    nsw = _build_nsw(data)
    hnsw_plain = _build_hnsw(data, heuristic=False)
    hnsw_heur = _build_hnsw(data, heuristic=True)

    nsw_r = _recall(truth, nsw, queries, search_kwargs=dict(k=K, ef_search=EF))
    plain_r = _recall(truth, hnsw_plain, queries, search_kwargs=dict(k=K, ef_search=EF))
    heur_r = _recall(truth, hnsw_heur, queries, search_kwargs=dict(k=K, ef_search=EF))

    print(
        f"\nrecall@{K} (N={N_VECTORS}, dim={DIM}, ef_search={EF}):"
        f"\n  NSW single-layer     : {nsw_r:.3f}"
        f"\n  HNSW, m-closest       : {plain_r:.3f}"
        f"\n  HNSW, diversity heur. : {heur_r:.3f}"
        f"\n  heuristic delta       : {heur_r - plain_r:+.3f}"
    )

    # All three should be clearly useful at this scale.
    assert nsw_r > 0.75
    assert plain_r > 0.75
    assert heur_r > 0.75
    # The heuristic should not hurt recall (it usually helps, more so at scale).
    assert heur_r >= plain_r - 0.02


def test_hierarchy_actually_forms(data):
    idx = _build_hnsw(data, heuristic=True)
    assert len(idx) == N_VECTORS
    assert idx.entry_point is not None
    assert idx.max_level >= 1  # more than one layer got used
    assert idx.node_level(idx.entry_point) == idx.max_level


def test_edges_are_bidirectional_per_layer(data):
    idx = _build_hnsw(data, heuristic=True)
    for node_id in range(len(idx)):
        for layer in range(idx.node_level(node_id) + 1):
            for nb in idx.neighbors(node_id, layer):
                assert node_id in idx.neighbors(nb, layer)


def test_layer0_respects_m0(data):
    idx = _build_hnsw(data, heuristic=True)
    for node_id in range(len(idx)):
        assert len(idx.neighbors(node_id, 0)) <= idx.m0


def test_search_returns_sorted_unique_k(data):
    idx = _build_hnsw(data, heuristic=True)
    ids, dists = idx.search(generate_random_vectors(1, DIM, seed=3)[0], k=K, ef_search=EF)
    assert len(ids) == K
    assert list(dists) == sorted(dists)
    assert len(set(ids.tolist())) == K


def test_empty_and_single_node():
    idx = HNSWIndex(m=8, seed=0)
    ids, dists = idx.search(np.zeros(DIM), k=5)
    assert len(ids) == 0 and len(dists) == 0

    idx.insert(generate_random_vectors(1, DIM, seed=0)[0])
    got, _ = idx.search(generate_random_vectors(1, DIM, seed=1)[0], k=5)
    assert list(got) == [0]
