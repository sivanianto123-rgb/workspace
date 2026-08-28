"""Multi-version key-value storage.

Pure data structure: every key maps to its full list of :class:`Version`
objects, newest last. No transaction logic and no visibility filtering live
here — this module only does the bookkeeping of "which versions exist and what
is their commit state". Visibility is decided in :mod:`txnkv.transaction`.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Version:
    """One version of one key.

    ``value is None`` is a tombstone: the version records that the key was
    deleted, not that it holds the value ``None``.
    """

    value: str | None
    created_by_txn: int
    committed: bool = False
    commit_order: int | None = None  # visibility ordering, set on commit


class VersionedStore:
    def __init__(self) -> None:
        self._versions: dict[str, list[Version]] = {}

    def add_version(self, key: str, value: str | None, txn_id: int) -> Version:
        """Append a new uncommitted version for ``key``."""
        version = Version(value=value, created_by_txn=txn_id)
        self._versions.setdefault(key, []).append(version)
        return version

    def mark_committed(self, txn_id: int, commit_order: int) -> None:
        """Commit every version created by ``txn_id``, across all keys."""
        for versions in self._versions.values():
            for version in versions:
                if version.created_by_txn == txn_id:
                    version.committed = True
                    version.commit_order = commit_order

    def discard_txn(self, txn_id: int) -> None:
        """Remove every version created by ``txn_id`` (used on abort)."""
        for key, versions in self._versions.items():
            self._versions[key] = [
                v for v in versions if v.created_by_txn != txn_id
            ]

    def get_versions(self, key: str) -> list[Version]:
        """Return the raw version list for ``key`` (newest last)."""
        return self._versions.get(key, [])

    def all_keys(self) -> list[str]:
        return list(self._versions.keys())

    def replace_versions(self, key: str, versions: list[Version]) -> None:
        """Overwrite the version list for ``key`` (used by vacuum)."""
        self._versions[key] = versions
