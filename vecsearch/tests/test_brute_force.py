"""Ground-truth tests for BruteForceIndex.

Each dataset is small enough that the correct neighbour ordering is known by
construction, so these tests pin down exact behaviour rather than approximate
recall.
"""

import numpy as np
import pytest

from vecsearch import BruteForceIndex


def _unit(v):
    v = np.asarray(v, dtype=float)
    return v / np.linalg.norm(v)


# 5 unit vectors in 2-D at known angles from the +x axis. Against the query
# [1, 0] both cosine and euclidean distance are monotonic in the angle, so the
# nearest-to-farthest id order is exactly 0, 1, 2, 3, 4.
ANGLES_DEG = [0.0, 10.0, 25.0, 60.0, 90.0]
CIRCLE_VECTORS = np.array(
    [[np.cos(np.deg2rad(t)), np.sin(np.deg2rad(t))] for t in ANGLES_DEG]
)
QUERY_X = np.array([1.0, 0.0])


@pytest.fixture
def circle_index():
    idx = BruteForceIndex()
    idx.add(CIRCLE_VECTORS)
    return idx


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
def test_full_ordering_matches_construction(circle_index, metric):
    ids, dists = circle_index.search(QUERY_X, k=5, metric=metric)
    assert list(ids) == [0, 1, 2, 3, 4]
    # distances strictly increasing with the angle
    assert np.all(np.diff(dists) > 0)
    assert dists[0] == pytest.approx(0.0, abs=1e-12)


@pytest.mark.parametrize("metric", ["cosine", "euclidean"])
def test_top_k_is_prefix_of_full_order(circle_index, metric):
    ids, dists = circle_index.search(QUERY_X, k=3, metric=metric)
    assert list(ids) == [0, 1, 2]
    assert list(dists) == sorted(dists)


def test_cosine_distance_values_are_exact(circle_index):
    ids, dists = circle_index.search(QUERY_X, k=5, metric="cosine")
    # cosine distance to a unit query along +x is 1 - cos(angle)
    expected = [1.0 - np.cos(np.deg2rad(ANGLES_DEG[i])) for i in ids]
    np.testing.assert_allclose(dists, expected, atol=1e-12)


def test_euclidean_distance_values_are_exact(circle_index):
    ids, dists = circle_index.search(QUERY_X, k=5, metric="euclidean")
    expected = [np.linalg.norm(CIRCLE_VECTORS[i] - QUERY_X) for i in ids]
    np.testing.assert_allclose(dists, expected, atol=1e-12)


def test_query_equal_to_stored_vector_has_zero_distance(circle_index):
    ids, dists = circle_index.search(CIRCLE_VECTORS[2], k=1, metric="cosine")
    assert list(ids) == [2]
    assert dists[0] == pytest.approx(0.0, abs=1e-12)


def test_euclidean_collinear_ordering():
    # Collinear points on the +x axis: direction is identical (so cosine cannot
    # tell them apart), but euclidean orders them by distance from the query.
    index = BruteForceIndex()
    index.add(np.array([[0.0, 0.0], [1.0, 0.0], [2.0, 0.0], [3.0, 0.0], [10.0, 0.0]]))
    query = np.array([0.1, 0.0])
    ids, dists = index.search(query, k=5, metric="euclidean")
    assert list(ids) == [0, 1, 2, 3, 4]
    np.testing.assert_allclose(dists, [0.1, 0.9, 1.9, 2.9, 9.9], atol=1e-12)


def test_ties_break_by_ascending_id():
    # Two vectors are equidistant from the query; the smaller id must come first.
    index = BruteForceIndex()
    index.add(np.array([[1.0, 0.0], [0.0, 1.0], [-1.0, 0.0], [0.0, -1.0]]))
    query = np.array([1.0, 0.0])  # ids 1 and 3 both at cosine distance 1.0
    ids, dists = index.search(query, k=3, metric="cosine")
    assert list(ids) == [0, 1, 3]
    np.testing.assert_allclose(dists, [0.0, 1.0, 1.0], atol=1e-12)


def test_k_larger_than_index_is_clamped(circle_index):
    ids, dists = circle_index.search(QUERY_X, k=99, metric="cosine")
    assert len(ids) == 5
    assert len(dists) == 5


def test_add_can_be_called_incrementally():
    index = BruteForceIndex()
    index.add(CIRCLE_VECTORS[:2])
    index.add(CIRCLE_VECTORS[2:])
    assert len(index) == 5
    ids, _ = index.search(QUERY_X, k=5, metric="cosine")
    assert list(ids) == [0, 1, 2, 3, 4]


def test_search_matches_naive_python_reference():
    # Independent, un-vectorized implementation over a random dataset.
    rng = np.random.default_rng(0)
    data = rng.standard_normal((50, 8))
    index = BruteForceIndex()
    index.add(data)
    query = rng.standard_normal(8)

    def naive_cosine(q, mat):
        out = []
        for i, v in enumerate(mat):
            sim = float(np.dot(q, v) / (np.linalg.norm(q) * np.linalg.norm(v)))
            out.append((1.0 - sim, i))
        out.sort()  # by distance, then id
        return out

    expected = naive_cosine(query, data)[:10]
    ids, dists = index.search(query, k=10, metric="cosine")
    assert list(ids) == [i for _, i in expected]
    np.testing.assert_allclose(dists, [d for d, _ in expected], atol=1e-12)


def test_unknown_metric_raises(circle_index):
    with pytest.raises(ValueError):
        circle_index.search(QUERY_X, k=1, metric="manhattan")


def test_search_on_empty_index_raises():
    with pytest.raises(ValueError):
        BruteForceIndex().search(QUERY_X, k=1)


def test_wrong_query_dim_raises(circle_index):
    with pytest.raises(ValueError):
        circle_index.search(np.array([1.0, 0.0, 0.0]), k=1)
