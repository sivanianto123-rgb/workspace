# txnkv

A small transactional key-value store, built from two ideas that every real
database relies on: a **write-ahead log** for durability and **MVCC** for
isolation. It is deliberately tiny and single-process — the point is that the
mechanisms are readable, not that it scales.

---

## What is a write-ahead log?

A write-ahead log (WAL) is an append-only file that a database writes to
*before* it changes anything else. The rule is: **log the intent to disk, then
apply the change.** Never the other way around.

Why bother? Because a process can die at any instant — power loss, `kill -9`, a
kernel panic. If the database updated its main data structures first and
crashed before recording what it did, it would wake up with half-applied,
corrupted state and no way to tell what happened. With a WAL, recovery is
simple: replay the log from the start, redo every change that was fully
committed, and ignore the rest.

The durability guarantee hinges on one system call: `fsync`. Writing to a file
usually just moves bytes into an OS buffer; they can sit there for seconds
before actually reaching the disk. `fsync` forces them down and doesn't return
until they're persisted. txnkv calls `flush()` + `os.fsync()` on **every**
`append` to the log — that call is the entire reason the WAL works.

Real systems do exactly this:

- **PostgreSQL** writes all changes to its WAL (in `pg_wal/`) and fsyncs it at
  commit. On restart after a crash it replays the WAL to recover. This is also
  the foundation of streaming replication and point-in-time recovery.
- **SQLite** has a WAL mode (`PRAGMA journal_mode=WAL`) where writers append new
  pages to a `-wal` file instead of overwriting the main database file.
  Readers keep reading the old pages, so readers don't block writers — the same
  benefit MVCC gives you.

---

## What is MVCC?

MVCC — multi-version concurrency control — means the store keeps **many
versions of each key at once** instead of overwriting in place. Every write
creates a new version tagged with the transaction that made it; old versions
stick around as long as someone might still need to see them.

This buys you concurrency without locking reads. A reader never waits for a
writer and never sees a half-finished write, because it's reading from a
consistent *snapshot* of the past, not from live mutating state.

### The snapshot isolation guarantee, in plain language

When a transaction begins, it takes a snapshot: "here is the exact set of
commits that exist right now." For its entire lifetime, that transaction sees
**that** set of commits and no others. Writes committed after it began are
invisible to it — not stale, just simply not part of its world.

The classic example, which is also the most important test in this repo
(`tests/test_visibility.py`):

1. Transaction **A** begins and writes `x = 1`, but does not commit.
2. Transaction **B** begins. Its snapshot is taken **now**, before A commits.
3. B reads `x`: it does **not** see A's write — A hasn't committed.
4. A commits.
5. Transaction **C** begins, *after* A's commit. C reads `x` and sees `1`.
6. B reads `x` **again**. B *still* does not see `1` — even though A has
   definitely committed by now, and C can see it. B's snapshot was taken
   before A's commit, so A's commit is forever outside B's view.

That last step is the whole idea. B's view of the database is frozen at the
moment it began. Consistency comes from B never seeing a moving target.

### Conflict detection

Two transactions that started from the same snapshot can both write to the same
key — neither sees the other's change. If both were allowed to commit, one
would silently clobber the other. So at commit time txnkv checks: has anyone
committed a write to a key I also wrote, since my snapshot was taken? If so it
raises `ConflictError` and refuses to commit. The caller catches it, aborts,
and can retry from a fresh snapshot. This is "first committer wins".

---

## Install

Requires Python 3.10+.

```sh
git clone <this repo>
cd txnkv
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
```

Run the tests:

```sh
pytest
```

All 11 tests cover: WAL durability across a restart, raw version bookkeeping,
snapshot-isolation visibility, the engine end to end, write-write conflict
detection, crash recovery from the log alone, and vacuum.

---

## CLI usage

`pip install -e .` puts a `txnkv` command on your path. It takes an optional
WAL file path (default `txnkv.wal`):

```sh
txnkv demo.wal
```

Then type commands, one per line:

| command | effect |
| --- | --- |
| `begin` | start a transaction, make it the current one, print its id |
| `use <txn_id>` | switch the current transaction to another open one |
| `get <key>` | read `<key>` in the current transaction |
| `put <key> <value>` | write `<key>` in the current transaction |
| `delete <key>` | tombstone `<key>` in the current transaction |
| `commit` / `abort` | finish the current transaction, clear it |
| `status [key]` | list active transactions; with a key, show every stored version of it (value, committed state, creator txn) |
| `vacuum` | drop versions no active transaction can still see |
| `crash` | discard the in-memory engine and rebuild it from the WAL file |
| `exit` / `quit` | leave |

`status <key>` is what makes MVCC visible — you can watch two versions of one
key coexist, one committed and one not.

---

## Example session: isolation and crash recovery, live

Piping this script into `txnkv demo.wal`:

```
# ===== snapshot isolation =====
begin
put balance 100
commit
# T2 opens now and stays open for the whole session. Snapshot = [1].
begin
get balance
# A concurrent writer T3 changes balance and commits.
begin
put balance 500
commit
# A brand-new T4, begun AFTER T3's commit, sees 500:
begin
get balance
# ...but T2 is still open, and its snapshot predates T3's commit -- it STILL sees 100:
use 2
get balance
# ===== crash recovery =====
use 4
put note this-write-is-not-durable
status note
crash
# Rebuilt from the WAL alone: committed balance=500 survived, the uncommitted note did not.
begin
get balance
get note
```

produces:

```
txnkv> begin
  began txn 1 (snapshot: [])
txnkv> put balance 100
  txn 1: put balance = '100'
txnkv> commit
  committed txn 1
txnkv> begin
  began txn 2 (snapshot: [1])
txnkv> get balance
  txn 2: balance = '100'
txnkv> begin
  began txn 3 (snapshot: [1])
txnkv> put balance 500
  txn 3: put balance = '500'
txnkv> commit
  committed txn 3
txnkv> begin
  began txn 4 (snapshot: [1, 2])
txnkv> get balance
  txn 4: balance = '500'
txnkv> use 2
  current transaction is now txn 2
txnkv> get balance
  txn 2: balance = '100'
txnkv> use 4
  current transaction is now txn 4
txnkv> put note this-write-is-not-durable
  txn 4: put note = 'this-write-is-not-durable'
txnkv> status note
  active transactions:
    txn 2  snapshot=[1]  wrote=[]
    txn 4  snapshot=[1, 2]  wrote=['note'] (current)
  versions of 'note' (oldest first):
    value='this-write-is-not-durable'  uncommitted  by txn 4
txnkv> crash
  *** simulating crash: discarding in-memory engine ***
  recovered from WAL. surviving committed state:
    balance = '500'  (committed@2)
txnkv> begin
  began txn 5 (snapshot: [1, 2])
txnkv> get balance
  txn 5: balance = '500'
txnkv> get note
  txn 5: note = None
```

Two things to see here:

- **`use 2` then `get balance` returns `100`**, while T4 sees `500`. Same key,
  same instant, two answers — each transaction reads from its own snapshot.
- **After `crash`**, the engine is thrown away and rebuilt from `demo.wal`
  alone. `balance = 500` (committed) is back; `note` (never committed) is gone
  completely, exactly as if it had never been written.

---

## Layout

```
txnkv/
├── txnkv/
│   ├── wal.py           append-only log; fsync on every append
│   ├── storage.py       VersionedStore: dict[key -> list[Version]]
│   ├── transaction.py   Transaction, TransactionManager, is_visible()  <- MVCC core
│   ├── engine.py        public API tying it together + conflict check + vacuum
│   ├── recovery.py      replay(): rebuild state from the WAL after a crash
│   └── cli.py           interactive shell
└── tests/
    ├── test_wal.py         durability across a fresh instance
    ├── test_storage.py     raw version bookkeeping
    ├── test_visibility.py  snapshot isolation, the B-can't-see-A's-commit case
    ├── test_engine.py      put/get/delete/commit end to end
    ├── test_conflicts.py   write-write conflict is raised, not lost
    ├── test_recovery.py    committed writes survive a crash, uncommitted don't
    └── test_vacuum.py      version count drops, visible values don't change
```
