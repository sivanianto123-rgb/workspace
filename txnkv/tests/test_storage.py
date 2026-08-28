from txnkv.storage import VersionedStore


def test_version_bookkeeping_across_commit_and_discard():
    """No visibility logic here — just prove the raw version list is
    maintained correctly through add / mark_committed / discard."""
    store = VersionedStore()

    # Two txns write "x"; one txn writes "y"; a third writes a "y" tombstone.
    store.add_version("x", "1", txn_id=1)
    store.add_version("x", "2", txn_id=2)
    store.add_version("y", "a", txn_id=1)
    store.add_version("y", None, txn_id=3)

    store.mark_committed(1, commit_order=10)  # commit txn 1's versions
    store.discard_txn(3)                       # abort txn 3

    xs = store.get_versions("x")
    assert len(xs) == 2
    assert (xs[0].value, xs[0].created_by_txn) == ("1", 1)
    assert xs[0].committed is True and xs[0].commit_order == 10
    assert (xs[1].value, xs[1].created_by_txn) == ("2", 2)
    assert xs[1].committed is False and xs[1].commit_order is None

    ys = store.get_versions("y")
    assert len(ys) == 1  # txn 3's tombstone is gone entirely
    assert (ys[0].value, ys[0].created_by_txn) == ("a", 1)
    assert ys[0].committed is True and ys[0].commit_order == 10

    assert store.get_versions("never-written") == []
