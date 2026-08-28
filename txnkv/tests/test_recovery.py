"""The payoff test: the write-ahead log actually protects data.

A committed write must come back after a crash. An uncommitted write must not —
it has to be as if it never happened.
"""

from txnkv.engine import Engine


def test_recover_keeps_committed_writes_and_drops_the_crashed_transaction(
    tmp_path,
):
    path = str(tmp_path / "recovery.wal")
    engine = Engine(path)

    # Txn 1: committed.
    t1 = engine.begin()
    engine.put(t1, "a", "1")
    engine.put(t1, "b", "2")
    engine.commit(t1)

    # Txn 2: committed, overwrites "a".
    t2 = engine.begin()
    engine.put(t2, "a", "10")
    engine.commit(t2)

    # Txn 3: writes, then the process "crashes" — no commit, no abort.
    t3 = engine.begin()
    engine.put(t3, "c", "never-durable")
    engine.put(t3, "a", "999")

    # The crash: drop the engine object. Only the WAL file on disk survives.
    del engine

    recovered = Engine.recover(path)
    txn = recovered.begin()

    assert recovered.get(txn, "a") == "10"   # last committed value wins
    assert recovered.get(txn, "b") == "2"
    assert recovered.get(txn, "c") is None   # crashed txn's writes vanished

    # Fresh transactions get non-colliding ids after recovery.
    assert txn.txn_id > 3
    recovered.close()
