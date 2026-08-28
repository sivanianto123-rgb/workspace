"""Flag oversized files that are not already ignored by .gitignore."""

from __future__ import annotations

import os

from repodoc.checks.gitignore import is_ignored, load_patterns
from repodoc.finding import Finding

SIZE_LIMIT_BYTES = 5 * 1024 * 1024  # 5 MB


def _human_size(num_bytes: int) -> str:
    size = float(num_bytes)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if size < 1024 or unit == "TB":
            return f"{size:.1f} {unit}" if unit != "B" else f"{int(size)} B"
        size /= 1024
    return f"{size:.1f} TB"


def scan_for_large_files(
    repo_path: str,
    *,
    warnings: list[str] | None = None,
) -> list[Finding]:
    """Flag files larger than 5 MB that .gitignore does not already exclude.

    Non-fatal problems (unreadable files or directories) are appended to
    ``warnings`` if it is provided, rather than raising.
    """
    findings: list[Finding] = []
    rules = load_patterns(repo_path)

    def on_walk_error(err: OSError) -> None:
        if warnings is not None:
            warnings.append(f"skipped directory (cannot read): {err.filename}")

    for root, dirs, files in os.walk(repo_path, onerror=on_walk_error):
        if ".git" in dirs:
            dirs.remove(".git")
        for name in files:
            full = os.path.join(root, name)
            try:
                size = os.path.getsize(full)
            except OSError:
                if warnings is not None:
                    rel = os.path.relpath(full, repo_path)
                    warnings.append(f"skipped file (cannot stat): {rel}")
                continue
            if size <= SIZE_LIMIT_BYTES:
                continue
            rel_path = os.path.relpath(full, repo_path).replace(os.sep, "/")
            if is_ignored(rel_path, is_dir=False, rules=rules):
                continue
            findings.append(
                Finding(
                    file_path=rel_path,
                    severity="medium",
                    message=(
                        f"File is {_human_size(size)}, over the 5 MB limit "
                        f"and not in .gitignore"
                    ),
                )
            )
    return findings
