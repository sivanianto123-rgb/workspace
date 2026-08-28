"""Crash recovery: rebuild state from nothing but the WAL file.

This is the payoff of the write-ahead discipline. Because every mutation was
fsync'd to the log before it touched memory, a full and correct state can be
reconstructed after a crash by replaying the log:

* transactions with a COMMIT record are redone, in the order their COMMIT
  records appear;
* transactions with an ABORT record, or with no terminal record at all (the
  process died mid-transaction), are dropped — their writes never happened.
"""

from __future__ import annotations

from txnkv.storage import VersionedStore
from txnkv.transaction import TransactionManager
from txnkv.wal import WriteAheadLog


def replay(wal_path: str) -> tuple[VersionedStore, TransactionManager]:
    wal = WriteAheadLog(wal_path)
    try:
        records = wal.read_all()
    finally:
        wal.close()

    writes: dict[int, list] = {}       # txn_id -> [WALRecord, ...] (PUT/DELETE)
    terminal: dict[int, str] = {}      # txn_id -> "COMMIT" | "ABORT"
    commit_sequence: list[int] = []    # txn_ids in the order COMMIT was logged

    for rec in records:
        if rec.op in ("PUT", "DELETE"):
            writes.setdefault(rec.txn_id, []).append(rec)
        elif rec.op == "COMMIT":
            terminal[rec.txn_id] = "COMMIT"
            commit_sequence.append(rec.txn_id)
        elif rec.op == "ABORT":
            terminal[rec.txn_id] = "ABORT"

    store = VersionedStore()
    next_commit_order = 1
    for txn_id in commit_sequence:
        for rec in writes.get(txn_id, []):
            store.add_version(rec.key, rec.value, txn_id)
        store.mark_committed(txn_id, next_commit_order)
        next_commit_order += 1

    seen_txn_ids = set(writes) | set(terminal)
    max_txn_id = max(seen_txn_ids, default=0)

    txns = TransactionManager()
    txns.next_txn_id = max_txn_id + 1
    txns.next_commit_order = next_commit_order
    txns.committed_order = list(range(1, next_commit_order))

    return store, txns
