"""vacuum() must shrink version history without changing any live view."""

from txnkv.engine import Engine


def _write(engine, key, value):
    t = engine.begin()
    engine.put(t, key, value)
    engine.commit(t)


def test_vacuum_reduces_version_count_without_changing_visibility(tmp_path):
    engine = Engine(str(tmp_path / "vacuum.wal"))

    _write(engine, "k", "1")
    _write(engine, "k", "2")

    # An older reader: its snapshot sees commits 1 and 2 only (k == "2").
    old_reader = engine.begin()

    _write(engine, "k", "3")
    _write(engine, "k", "4")

    # A newer reader: sees all four commits (k == "4").
    new_reader = engine.begin()

    assert engine.get(old_reader, "k") == "2"
    assert engine.get(new_reader, "k") == "4"

    before = len(engine.versions("k"))
    assert before == 4

    removed = engine.vacuum()

    after = len(engine.versions("k"))
    assert removed > 0
    assert after < before

    # What each still-active transaction sees is unchanged.
    assert engine.get(old_reader, "k") == "2"
    assert engine.get(new_reader, "k") == "4"

    # And a brand-new transaction still reads the latest committed value.
    fresh = engine.begin()
    assert engine.get(fresh, "k") == "4"
    engine.close()


def test_vacuum_with_no_active_transactions_collapses_to_one_version(tmp_path):
    engine = Engine(str(tmp_path / "vacuum.wal"))

    _write(engine, "k", "1")
    _write(engine, "k", "2")
    _write(engine, "k", "3")

    assert len(engine.versions("k")) == 3
    removed = engine.vacuum()
    assert removed == 2
    assert len(engine.versions("k")) == 1

    fresh = engine.begin()
    assert engine.get(fresh, "k") == "3"
    engine.close()
