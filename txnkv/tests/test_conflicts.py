import pytest

from txnkv.engine import ConflictError, Engine


def test_write_write_conflict_is_raised_not_silently_lost(tmp_path):
    engine = Engine(str(tmp_path / "conflict.wal"))

    # Both snapshots taken before either commits.
    a = engine.begin()
    b = engine.begin()

    # A writes x and commits.
    engine.put(a, "x", "1")
    engine.commit(a)

    # B writes x too — B's snapshot predates A's commit, so this is realistic.
    engine.put(b, "x", "2")
    with pytest.raises(ConflictError):
        engine.commit(b)

    # The caller decides what to do; here it aborts.
    engine.abort(b)

    # A's value survived; B's conflicting write did not.
    c = engine.begin()
    assert engine.get(c, "x") == "1"
    engine.close()


def test_no_conflict_when_transactions_write_different_keys(tmp_path):
    engine = Engine(str(tmp_path / "conflict.wal"))

    a = engine.begin()
    b = engine.begin()

    engine.put(a, "x", "1")
    engine.put(b, "y", "2")

    engine.commit(a)
    engine.commit(b)  # must not raise

    c = engine.begin()
    assert engine.get(c, "x") == "1"
    assert engine.get(c, "y") == "2"
    engine.close()
