"""Public API: WAL + VersionedStore + TransactionManager as one store.

The invariant this module enforces is *write-ahead*: a mutation is appended to
the WAL (and thereby fsync'd to disk) before it is ever applied to in-memory
storage. If the process dies between the two steps, the log still has the
record and replay can redo it; the reverse order could lose an acknowledged
write.
"""

from __future__ import annotations

from txnkv.recovery import replay
from txnkv.storage import Version, VersionedStore
from txnkv.transaction import Transaction, TransactionManager, is_visible
from txnkv.wal import WALRecord, WriteAheadLog


class ConflictError(Exception):
    """Raised by :meth:`Engine.commit` when another transaction committed a
    write to a key this transaction also wrote, after this transaction's
    snapshot was taken. The caller should :meth:`Engine.abort` and, if it
    wants, retry from a fresh transaction."""


class Engine:
    def __init__(self, wal_path: str) -> None:
        self._wal = WriteAheadLog(wal_path)
        self._store = VersionedStore()
        self._txns = TransactionManager()

    @classmethod
    def recover(cls, wal_path: str) -> "Engine":
        """Build an Engine from an existing WAL file instead of starting empty.

        Committed transactions in the log are replayed; aborted or
        crashed-mid-transaction ones are dropped.
        """
        store, txns = replay(wal_path)
        engine = cls(wal_path)
        engine._store = store
        engine._txns = txns
        return engine

    # -- transaction lifecycle ------------------------------------------------

    def begin(self) -> Transaction:
        return self._txns.begin()

    def commit(self, txn: Transaction) -> None:
        self._check_conflicts(txn)
        commit_order = self._txns.commit(txn)
        self._wal.append(WALRecord(txn.txn_id, "COMMIT", None, None))
        self._store.mark_committed(txn.txn_id, commit_order)

    def abort(self, txn: Transaction) -> None:
        self._wal.append(WALRecord(txn.txn_id, "ABORT", None, None))
        self._txns.abort(txn)
        self._store.discard_txn(txn.txn_id)

    # -- reads and writes ---------------------------------------------------

    def get(self, txn: Transaction, key: str) -> str | None:
        """Value of the most recent version of ``key`` visible to ``txn``.

        Returns ``None`` if no version is visible, or if the most recent
        visible version is a tombstone (a delete).
        """
        visible = [
            v for v in self._store.get_versions(key) if is_visible(v, txn)
        ]
        if not visible:
            return None
        return visible[-1].value

    def put(self, txn: Transaction, key: str, value: str) -> None:
        # Write-ahead: durably log first, then apply to storage.
        self._wal.append(WALRecord(txn.txn_id, "PUT", key, value))
        self._store.add_version(key, value, txn.txn_id)
        txn.written_keys.add(key)

    def delete(self, txn: Transaction, key: str) -> None:
        self._wal.append(WALRecord(txn.txn_id, "DELETE", key, None))
        self._store.add_version(key, None, txn.txn_id)
        txn.written_keys.add(key)

    # -- maintenance ------------------------------------------------------

    def vacuum(self) -> int:
        """Drop committed versions that no active transaction can ever see.

        Computes the earliest snapshot point among all currently active
        transactions. Any committed version at or before that point that has
        been superseded by a newer committed version (also at or before that
        point) is invisible to every active transaction and to every future
        one, so it is removed. Returns the number of versions dropped.
        """
        active = list(self._txns.active.values())
        if active:
            cutoff = min(max(t.snapshot, default=0) for t in active)
        else:
            # No active readers: everything committed so far is fair game.
            cutoff = self._txns.next_commit_order - 1

        removed = 0
        for key in self._store.all_keys():
            versions = self._store.get_versions(key)
            superseded = [
                v
                for v in versions
                if v.committed
                and v.commit_order is not None
                and v.commit_order <= cutoff
            ]
            if len(superseded) <= 1:
                continue
            keep = max(superseded, key=lambda v: v.commit_order)
            drop = {id(v) for v in superseded if v is not keep}
            kept = [v for v in versions if id(v) not in drop]
            removed += len(versions) - len(kept)
            self._store.replace_versions(key, kept)
        return removed

    # -- introspection (used by the CLI) --------------------------------

    def active_transactions(self) -> list[Transaction]:
        return list(self._txns.active.values())

    def versions(self, key: str) -> list[Version]:
        return self._store.get_versions(key)

    def close(self) -> None:
        self._wal.close()

    # -- internals --------------------------------------------------------

    def _check_conflicts(self, txn: Transaction) -> None:
        for key in txn.written_keys:
            for v in self._store.get_versions(key):
                if (
                    v.committed
                    and v.commit_order is not None
                    and v.commit_order not in txn.snapshot
                ):
                    raise ConflictError(
                        f"key {key!r} was modified by a concurrent "
                        f"transaction after txn {txn.txn_id} began"
                    )
