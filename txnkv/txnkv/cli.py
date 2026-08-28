"""Interactive shell for txnkv.

Its reason to exist: snapshot isolation and crash recovery are invisible from
the outside. This shell lets you drive several transactions by hand and watch
one fail to see another's uncommitted (then committed-too-late) write, and
watch committed data survive a simulated crash while an uncommitted write does
not.

Commands::

    begin                     start a transaction, make it current
    use <txn_id>              switch the current transaction to an open one
    get <key>                 read <key> in the current transaction
    put <key> <value>         write <key> in the current transaction
    delete <key>              tombstone <key> in the current transaction
    commit                    commit the current transaction
    abort                     abort the current transaction
    status [key]              show active transactions; with a key, every
                              stored version of it (value / committed / creator)
    vacuum                    drop versions no active transaction can see
    crash                     discard the in-memory engine and rebuild it
                              from the WAL file (Engine.recover)
    exit | quit               leave
"""

from __future__ import annotations

import sys

from txnkv.engine import ConflictError, Engine


class Repl:
    def __init__(self, wal_path: str) -> None:
        self.wal_path = wal_path
        self.engine = Engine(wal_path)
        self.current = None  # the "current" transaction, or None

    # -- command loop ---------------------------------------------------

    def run(self, stream, *, prompt: bool = False) -> None:
        for raw in stream:
            line = raw.strip()
            if prompt:
                print(f"txnkv> {line}")
            if not line or line.startswith("#"):
                continue
            if line in ("exit", "quit"):
                break
            parts = line.split()
            handler = getattr(self, f"do_{parts[0]}", None)
            if handler is None:
                print(f"  unknown command: {parts[0]}")
                continue
            try:
                handler(*parts[1:])
            except ConflictError as e:
                print(f"  CONFLICT: {e}")
                print("  (call `abort`, then retry in a fresh transaction)")
            except TypeError:
                print(f"  bad arguments for: {parts[0]}")
            except Exception as e:  # keep the shell alive on any error
                print(f"  error: {e}")
        self.engine.close()

    # -- individual commands ------------------------------------------

    def _require_current(self):
        if self.current is None:
            raise RuntimeError("no current transaction; run `begin` first")
        return self.current

    def do_begin(self) -> None:
        self.current = self.engine.begin()
        print(f"  began txn {self.current.txn_id} "
              f"(snapshot: {sorted(self.current.snapshot)})")

    def do_use(self, txn_id: str) -> None:
        wanted = int(txn_id)
        for t in self.engine.active_transactions():
            if t.txn_id == wanted:
                self.current = t
                print(f"  current transaction is now txn {wanted}")
                return
        raise RuntimeError(f"no active transaction with id {wanted}")

    def do_get(self, key: str) -> None:
        txn = self._require_current()
        value = self.engine.get(txn, key)
        print(f"  txn {txn.txn_id}: {key} = {value!r}")

    def do_put(self, key: str, value: str) -> None:
        txn = self._require_current()
        self.engine.put(txn, key, value)
        print(f"  txn {txn.txn_id}: put {key} = {value!r}")

    def do_delete(self, key: str) -> None:
        txn = self._require_current()
        self.engine.delete(txn, key)
        print(f"  txn {txn.txn_id}: deleted {key}")

    def do_commit(self) -> None:
        txn = self._require_current()
        self.engine.commit(txn)
        print(f"  committed txn {txn.txn_id}")
        self.current = None

    def do_abort(self) -> None:
        txn = self._require_current()
        self.engine.abort(txn)
        print(f"  aborted txn {txn.txn_id}")
        self.current = None

    def do_status(self, key: str | None = None) -> None:
        active = self.engine.active_transactions()
        if active:
            print("  active transactions:")
            for t in active:
                marker = " (current)" if t is self.current else ""
                print(f"    txn {t.txn_id}  snapshot={sorted(t.snapshot)}"
                      f"  wrote={sorted(t.written_keys)}{marker}")
        else:
            print("  active transactions: none")
        if key is not None:
            versions = self.engine.versions(key)
            if not versions:
                print(f"  no stored versions for {key!r}")
                return
            print(f"  versions of {key!r} (oldest first):")
            for v in versions:
                state = (f"committed@{v.commit_order}" if v.committed
                         else "uncommitted")
                print(f"    value={v.value!r}  {state}  "
                      f"by txn {v.created_by_txn}")

    def do_vacuum(self) -> None:
        removed = self.engine.vacuum()
        print(f"  vacuum removed {removed} version(s)")

    def do_crash(self) -> None:
        print("  *** simulating crash: discarding in-memory engine ***")
        try:
            self.engine.close()
        except Exception:
            pass
        self.engine = Engine.recover(self.wal_path)
        self.current = None
        print("  recovered from WAL. surviving committed state:")
        seen = False
        for key in sorted(self.engine._store.all_keys()):
            versions = self.engine.versions(key)
            committed = [v for v in versions if v.committed]
            if not committed:
                continue
            seen = True
            latest = max(committed, key=lambda v: v.commit_order)
            shown = "<deleted>" if latest.value is None else repr(latest.value)
            print(f"    {key} = {shown}  (committed@{latest.commit_order})")
        if not seen:
            print("    (nothing committed)")


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    wal_path = argv[0] if argv else "txnkv.wal"
    repl = Repl(wal_path)
    repl.run(sys.stdin, prompt=not sys.stdin.isatty())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
