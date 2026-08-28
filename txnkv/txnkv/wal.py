"""Write-ahead log backed by a plain append-only file.

Every :meth:`WriteAheadLog.append` call flushes and ``fsync``s the underlying
file descriptor before returning. That fsync is the entire point of a WAL: it is
what lets a caller treat a returned ``append`` as a durable fact, even if the
process is killed the instant afterwards.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass

_OPS = ("PUT", "DELETE", "COMMIT", "ABORT")


@dataclass
class WALRecord:
    """A single logical entry in the write-ahead log."""

    txn_id: int
    op: str  # one of "PUT", "DELETE", "COMMIT", "ABORT"
    key: str | None = None
    value: str | None = None

    def to_json(self) -> str:
        """Serialize to a single line of JSON (no embedded newlines)."""
        return json.dumps(
            {
                "txn_id": self.txn_id,
                "op": self.op,
                "key": self.key,
                "value": self.value,
            },
            separators=(",", ":"),
        )

    @classmethod
    def from_json(cls, line: str) -> "WALRecord":
        data = json.loads(line)
        return cls(
            txn_id=data["txn_id"],
            op=data["op"],
            key=data.get("key"),
            value=data.get("value"),
        )


class WriteAheadLog:
    """Append-only WAL. One JSON record per line."""

    def __init__(self, path: str) -> None:
        self.path = path
        # "a" creates the file if missing and positions all writes at EOF.
        self._file = open(path, "a", encoding="utf-8")

    def append(self, record: WALRecord) -> None:
        """Write ``record`` as one line, then flush + fsync.

        The fsync is what guarantees the record survives a crash that happens
        immediately after this method returns.
        """
        if record.op not in _OPS:
            raise ValueError(f"unknown op: {record.op!r}")
        self._file.write(record.to_json() + "\n")
        self._file.flush()
        os.fsync(self._file.fileno())

    def read_all(self) -> list[WALRecord]:
        """Read the whole log from the start and return every record in order."""
        with open(self.path, "r", encoding="utf-8") as f:
            return [
                WALRecord.from_json(line)
                for line in f
                if line.strip()
            ]

    def close(self) -> None:
        self._file.close()
