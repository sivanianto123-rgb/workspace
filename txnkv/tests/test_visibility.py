"""The most important test in the project: snapshot isolation, by hand.

The crux: a transaction's view of the database is frozen at the moment it
begins. A commit that lands afterwards is invisible to it forever, even though
that commit is perfectly visible to transactions that start later.
"""

from txnkv.storage import Version
from txnkv.transaction import TransactionManager, is_visible


def test_transaction_b_never_sees_a_commit_that_postdates_its_snapshot():
    tm = TransactionManager()

    # Txn A begins and writes x = "1" (uncommitted).
    a = tm.begin()
    x_v1 = Version(value="1", created_by_txn=a.txn_id)

    # Txn B begins — its snapshot is taken BEFORE A commits.
    b = tm.begin()

    assert is_visible(x_v1, a) is True    # A sees its own uncommitted write
    assert is_visible(x_v1, b) is False   # B cannot: it isn't committed

    # A commits.
    commit_order = tm.commit(a)
    x_v1.committed = True
    x_v1.commit_order = commit_order

    # Txn C begins AFTER A's commit.
    c = tm.begin()

    assert is_visible(x_v1, c) is True    # committed before C's snapshot
    assert is_visible(x_v1, b) is False   # ...but still invisible to B,
    #                                       whose snapshot predates the commit
