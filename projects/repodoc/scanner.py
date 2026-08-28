"""Orchestrator: run every check and combine their findings into one list."""

from __future__ import annotations

from repodoc.checks import gitignore, large_files, secrets
from repodoc.finding import Finding


def run_all_checks(
    repo_path: str,
    *,
    scan_all: bool = False,
    warnings: list[str] | None = None,
) -> list[Finding]:
    """Run the secrets, large-file and .gitignore checks and merge their findings.

    Args:
        repo_path: Directory to scan.
        scan_all: Passed to the secrets check to also include binary files and
            normally-skipped dependency/build folders.
        warnings: Optional list; each check appends non-fatal problems (such as
            permission-denied files) to it instead of raising.
    """
    findings: list[Finding] = []
    findings.extend(
        secrets.scan_directory(repo_path, scan_all=scan_all, warnings=warnings)
    )
    findings.extend(
        large_files.scan_for_large_files(repo_path, warnings=warnings)
    )
    findings.extend(
        gitignore.audit_gitignore(repo_path, warnings=warnings)
    )
    return findings
