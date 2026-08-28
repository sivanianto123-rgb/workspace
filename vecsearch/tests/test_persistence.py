"""Round-trip test for save_index / load_index."""

import numpy as np

from vecsearch import HNSWIndex, generate_random_vectors
from vecsearch.persistence import load_index, save_index

DIM = 24


def _build():
    idx = HNSWIndex(m=8, seed=42, metric="cosine")
    for v in generate_random_vectors(300, DIM, seed=7):
        idx.insert(v, ef_construction=64)
    return idx


def test_index_round_trips_identically(tmp_path):
    idx = _build()
    path = tmp_path / "index.pkl"
    save_index(idx, path)
    loaded = load_index(path)

    # scalar state
    assert loaded.entry_point == idx.entry_point
    assert loaded.max_level == idx.max_level
    assert len(loaded) == len(idx)
    assert loaded.m == idx.m and loaded.m0 == idx.m0
    assert loaded.metric == idx.metric

    # full neighbor structure, every node, every layer
    for node_id in range(len(idx)):
        assert loaded.node_level(node_id) == idx.node_level(node_id)
        np.testing.assert_array_equal(
            loaded._vectors[node_id], idx._vectors[node_id]
        )
        for layer in range(idx.node_level(node_id) + 1):
            assert loaded.neighbors(node_id, layer) == idx.neighbors(node_id, layer)

    # identical query results
    for q in generate_random_vectors(30, DIM, seed=123):
        a_ids, a_d = idx.search(q, k=10, ef_search=50)
        b_ids, b_d = loaded.search(q, k=10, ef_search=50)
        np.testing.assert_array_equal(a_ids, b_ids)
        np.testing.assert_allclose(a_d, b_d, rtol=0, atol=0)


def test_loaded_index_can_keep_inserting(tmp_path):
    idx = _build()
    path = tmp_path / "index.pkl"
    save_index(idx, path)
    loaded = load_index(path)

    extra = generate_random_vectors(1, DIM, seed=555)[0]
    new_id = loaded.insert(extra)
    assert new_id == len(idx)
    ids, _ = loaded.search(extra, k=1, ef_search=50)
    assert ids[0] == new_id
