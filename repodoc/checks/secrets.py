"""Scan text files for leaked secrets: cloud keys, API keys, passwords, private keys."""

from __future__ import annotations

import os
import re

from repodoc.finding import Finding

# Directories that hold dependencies or generated output — not worth scanning for
# secrets, and slow to walk. Skipped unless ``scan_all`` is set.
_SKIP_DIRS = {
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    ".tox",
    "dist",
    "build",
    ".idea",
    ".vscode",
}

# Only scan files up to this size; a real secret lives near the top of a config
# file, not buried in a multi-megabyte blob.
_MAX_SCAN_BYTES = 5 * 1024 * 1024

# Obvious non-secret values, to keep the password rule from crying wolf.
_PLACEHOLDERS = re.compile(
    r"^(?:\*+|x+|changeme|your[_-]?password|placeholder|example|none|null|"
    r"password|secret|todo|fixme|redacted)$",
    re.IGNORECASE,
)


def _warn(bucket: list[str] | None, message: str) -> None:
    if bucket is not None:
        bucket.append(message)


class _Pattern:
    __slots__ = ("name", "severity", "regex")

    def __init__(self, name: str, severity: str, regex: str) -> None:
        self.name = name
        self.severity = severity
        self.regex = re.compile(regex)


_PATTERNS = [
    _Pattern(
        "AWS access key ID",
        "high",
        r"\bAKIA[0-9A-Z]{16}\b",
    ),
    _Pattern(
        "AWS secret access key",
        "high",
        r"(?i)aws_secret_access_key\s*[:=]\s*['\"]?[A-Za-z0-9/+=]{40}['\"]?",
    ),
    _Pattern(
        "private key block",
        "high",
        r"-----BEGIN (?:RSA |EC |DSA |OPENSSH |PGP )?PRIVATE KEY-----",
    ),
    _Pattern(
        "generic API key",
        "medium",
        r"(?i)(?:api[_-]?key|api[_-]?token|access[_-]?token|secret[_-]?key)"
        r"\s*[:=]\s*['\"][A-Za-z0-9_\-\.]{16,}['\"]",
    ),
    _Pattern(
        "hardcoded password",
        "high",
        r"(?i)(?:password|passwd|pwd)\s*[:=]\s*['\"](?P<pw>[^'\"]{6,})['\"]",
    ),
]


def _is_probably_text(path: str) -> bool:
    """Cheap binary sniff: a NUL byte in the first 1 KiB means binary.

    OSError (e.g. permission denied) is allowed to propagate so the caller can
    warn and move on.
    """
    with open(path, "rb") as handle:
        chunk = handle.read(1024)
    return b"\x00" not in chunk


def _iter_scan_files(repo_path: str, scan_all: bool, warnings: list[str] | None):
    def on_walk_error(err: OSError) -> None:
        _warn(warnings, f"skipped directory (cannot read): {err.filename}")

    for root, dirs, files in os.walk(repo_path, onerror=on_walk_error):
        # .git is never committed and only produces noise; always skip it.
        dirs[:] = [d for d in dirs if d != ".git"]
        if not scan_all:
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]

        for name in files:
            full = os.path.join(root, name)
            rel = os.path.relpath(full, repo_path)
            try:
                size = os.path.getsize(full)
            except OSError:
                _warn(warnings, f"skipped file (cannot stat): {rel}")
                continue
            if not scan_all and size > _MAX_SCAN_BYTES:
                continue
            if not scan_all:
                try:
                    if not _is_probably_text(full):
                        continue
                except OSError:
                    _warn(warnings, f"skipped file (permission denied): {rel}")
                    continue
            yield full, rel


def _scan_file(full_path: str, rel_path: str, warnings: list[str] | None) -> list[Finding]:
    findings: list[Finding] = []
    try:
        with open(full_path, "r", encoding="utf-8", errors="ignore") as handle:
            lines = handle.readlines()
    except OSError:
        _warn(warnings, f"skipped file (permission denied): {rel_path}")
        return findings

    for lineno, line in enumerate(lines, start=1):
        for pattern in _PATTERNS:
            match = pattern.regex.search(line)
            if not match:
                continue
            if pattern.name == "hardcoded password":
                value = match.group("pw")
                if _PLACEHOLDERS.match(value.strip()):
                    continue
            findings.append(
                Finding(
                    file_path=rel_path.replace(os.sep, "/"),
                    line_number=lineno,
                    severity=pattern.severity,
                    message=f"Possible {pattern.name} found",
                )
            )
    return findings


def scan_directory(
    repo_path: str,
    *,
    scan_all: bool = False,
    warnings: list[str] | None = None,
) -> list[Finding]:
    """Walk every text file under repo_path and flag lines that look like secrets.

    Args:
        repo_path: Directory to scan.
        scan_all: If True, also scan binary files and dependency/build folders
            that are skipped by default.
        warnings: Optional list; non-fatal problems (unreadable files or
            directories) are appended to it instead of raising.
    """
    findings: list[Finding] = []
    for full_path, rel_path in _iter_scan_files(repo_path, scan_all, warnings):
        findings.extend(_scan_file(full_path, rel_path, warnings))
    return findings
