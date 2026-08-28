"""MVCC core: transactions, their snapshots, and version visibility.

A transaction's ``snapshot`` is the set of ``commit_order`` values that were
already committed the moment it began. That set *is* the transaction's
consistent view of the database for its whole lifetime — commits that land
afterwards are invisible to it, which is exactly what snapshot isolation
promises.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from txnkv.storage import Version


@dataclass
class Transaction:
    txn_id: int
    snapshot: set[int] = field(default_factory=set)
    status: str = "active"  # "active" / "committed" / "aborted"
    written_keys: set[str] = field(default_factory=set)


class TransactionManager:
    def __init__(self) -> None:
        self.next_txn_id = 1
        self.next_commit_order = 1
        self.committed_order: list[int] = []
        self.active: dict[int, Transaction] = {}

    def begin(self) -> Transaction:
        txn = Transaction(
            txn_id=self.next_txn_id,
            snapshot=set(self.committed_order),
            status="active",
        )
        self.next_txn_id += 1
        self.active[txn.txn_id] = txn
        return txn

    def commit(self, txn: Transaction) -> int:
        """Assign this txn a commit_order, record it, mark it committed.

        Returns the assigned commit_order so the caller can hand it to
        :meth:`VersionedStore.mark_committed`.
        """
        commit_order = self.next_commit_order
        self.next_commit_order += 1
        self.committed_order.append(commit_order)
        txn.status = "committed"
        self.active.pop(txn.txn_id, None)
        return commit_order

    def abort(self, txn: Transaction) -> None:
        txn.status = "aborted"
        self.active.pop(txn.txn_id, None)


def is_visible(version: Version, txn: Transaction) -> bool:
    """Whether ``txn`` is allowed to see ``version``.

    Visible iff either:

    * the version was committed *before* ``txn`` began — it is committed and its
      ``commit_order`` is in ``txn.snapshot``; or
    * ``txn`` created the version itself — a transaction always sees its own
      writes, even uncommitted ones.

    Never visible: another transaction's uncommitted writes, or writes committed
    after ``txn``'s snapshot was taken.
    """
    if version.created_by_txn == txn.txn_id:
        return True
    return version.committed and version.commit_order in txn.snapshot
