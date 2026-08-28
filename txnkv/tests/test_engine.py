from txnkv.engine import Engine


def test_put_commit_then_read_from_a_later_transaction(tmp_path):
    engine = Engine(str(tmp_path / "engine.wal"))

    t1 = engine.begin()
    engine.put(t1, "a", "1")
    engine.put(t1, "b", "2")
    engine.put(t1, "c", "3")
    engine.commit(t1)

    t2 = engine.begin()
    assert engine.get(t2, "a") == "1"
    assert engine.get(t2, "b") == "2"
    assert engine.get(t2, "c") == "3"
    assert engine.get(t2, "missing") is None
    engine.close()


def test_delete_makes_a_later_get_return_none(tmp_path):
    engine = Engine(str(tmp_path / "engine.wal"))

    t1 = engine.begin()
    engine.put(t1, "k", "v")
    engine.commit(t1)

    t2 = engine.begin()
    assert engine.get(t2, "k") == "v"
    engine.delete(t2, "k")
    engine.commit(t2)

    t3 = engine.begin()
    assert engine.get(t3, "k") is None
    engine.close()


def test_uncommitted_writes_are_invisible_to_a_concurrent_transaction(tmp_path):
    engine = Engine(str(tmp_path / "engine.wal"))

    a = engine.begin()
    b = engine.begin()

    engine.put(a, "x", "from-a")
    assert engine.get(a, "x") == "from-a"   # a sees its own write
    assert engine.get(b, "x") is None       # b does not
    engine.close()
