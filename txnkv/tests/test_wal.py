from txnkv.wal import WALRecord, WriteAheadLog


def test_records_survive_a_fresh_instance(tmp_path):
    """A new WriteAheadLog on the same path is our stand-in for crash + restart.

    If records written by one instance come back identically from a separate
    instance, the fsync-on-every-append durability guarantee holds.
    """
    path = str(tmp_path / "test.wal")

    written = [
        WALRecord(txn_id=1, op="PUT", key="a", value="1"),
        WALRecord(txn_id=1, op="PUT", key="b", value="2"),
        WALRecord(txn_id=1, op="COMMIT"),
        WALRecord(txn_id=2, op="PUT", key="c", value="3"),
        WALRecord(txn_id=2, op="ABORT"),
    ]

    wal = WriteAheadLog(path)
    for record in written:
        wal.append(record)
    wal.close()

    # Fresh instance == "process restarted after a crash".
    reopened = WriteAheadLog(path)
    replayed = reopened.read_all()
    reopened.close()

    assert replayed == written
