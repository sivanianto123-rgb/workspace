"""Audit .gitignore for missing entries covering common generated folders.

This module also exposes a small, dependency-free .gitignore matcher
(:func:`load_patterns` / :func:`is_ignored`) that the large-files check reuses.
It implements the common subset of gitignore syntax: comments, blank lines,
negation (!), anchored patterns (a leading or embedded slash), directory-only
patterns (trailing slash), and the ``*``, ``**``, ``?`` and ``[...]`` globs.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass

from repodoc.finding import Finding

# Folders / files that should almost always be ignored once they appear.
COMMON_GENERATED = ["node_modules", "__pycache__", ".env", "dist", "build", ".venv"]


@dataclass
class _Rule:
    regex: "re.Pattern[str]"
    negated: bool
    dir_only: bool


def _translate(pattern: str) -> str:
    """Translate the glob body of a gitignore line into a regex fragment."""
    i, n = 0, len(pattern)
    out: list[str] = []
    while i < n:
        c = pattern[i]
        i += 1
        if c == "*":
            if i < n and pattern[i] == "*":
                i += 1
                if i < n and pattern[i] == "/":
                    i += 1
                    out.append("(?:.*/)?")
                else:
                    out.append(".*")
            else:
                out.append("[^/]*")
        elif c == "?":
            out.append("[^/]")
        elif c == "/":
            out.append("/")
        elif c == "[":
            j = i
            if j < n and pattern[j] == "!":
                j += 1
            if j < n and pattern[j] == "]":
                j += 1
            while j < n and pattern[j] != "]":
                j += 1
            if j >= n:
                out.append(r"\[")
            else:
                body = pattern[i:j]
                i = j + 1
                if body.startswith("!"):
                    body = "^" + body[1:]
                out.append("[" + body + "]")
        else:
            out.append(re.escape(c))
    return "".join(out)


def _compile_line(line: str) -> _Rule | None:
    # Trailing whitespace is not significant unless backslash-escaped; we keep it
    # simple and just strip it.
    line = line.rstrip("\n").rstrip()
    if not line or line.startswith("#"):
        return None

    negated = line.startswith("!")
    if negated:
        line = line[1:]

    dir_only = line.endswith("/")
    if dir_only:
        line = line[:-1]

    anchored = line.startswith("/") or "/" in line
    if line.startswith("/"):
        line = line[1:]

    body = _translate(line)
    prefix = "^" if anchored else r"(?:^|.*/)"
    regex = re.compile(prefix + body + r"(?:/.*)?$")
    return _Rule(regex=regex, negated=negated, dir_only=dir_only)


def load_patterns(repo_path: str) -> list[_Rule]:
    """Read the repo-root .gitignore and return compiled rules (empty if none)."""
    path = os.path.join(repo_path, ".gitignore")
    rules: list[_Rule] = []
    try:
        with open(path, "r", encoding="utf-8", errors="ignore") as handle:
            for line in handle:
                rule = _compile_line(line)
                if rule is not None:
                    rules.append(rule)
    except OSError:
        pass
    return rules


def is_ignored(rel_path: str, is_dir: bool, rules: list[_Rule]) -> bool:
    """Return True if rel_path (or any parent directory) is ignored by rules."""
    rel_path = rel_path.replace(os.sep, "/").strip("/")
    if not rel_path:
        return False

    segments = rel_path.split("/")
    candidates: list[tuple[str, bool]] = []
    for k in range(1, len(segments) + 1):
        sub = "/".join(segments[:k])
        sub_is_dir = is_dir if k == len(segments) else True
        candidates.append((sub, sub_is_dir))

    ignored = False
    for rule in rules:
        for sub, sub_is_dir in candidates:
            if rule.dir_only and not sub_is_dir:
                continue
            if rule.regex.match(sub):
                ignored = not rule.negated
                break
    return ignored


def _find_generated_paths(repo_path: str, warnings: list[str] | None = None):
    """Yield (name, rel_path, is_dir) for the shallowest hit of each generated name."""
    wanted = set(COMMON_GENERATED)
    seen: set[str] = set()

    def on_walk_error(err: OSError) -> None:
        if warnings is not None:
            warnings.append(f"skipped directory (cannot read): {err.filename}")

    for root, dirs, files in os.walk(repo_path, onerror=on_walk_error):
        dirs.sort()
        # Never descend into .git, but do descend into node_modules etc. so a
        # nested occurrence is still found if there is no shallower one.
        if ".git" in dirs:
            dirs.remove(".git")
        for name in list(dirs) + files:
            if name in wanted and name not in seen:
                rel = os.path.relpath(os.path.join(root, name), repo_path)
                seen.add(name)
                yield name, rel.replace(os.sep, "/"), name in dirs
        if seen == wanted:
            return


def audit_gitignore(
    repo_path: str,
    *,
    warnings: list[str] | None = None,
) -> list[Finding]:
    """Flag common generated folders that exist in the repo but aren't ignored.

    Non-fatal problems (unreadable directories) are appended to ``warnings`` if
    it is provided, rather than raising.
    """
    findings: list[Finding] = []
    rules = load_patterns(repo_path)

    has_gitignore = os.path.isfile(os.path.join(repo_path, ".gitignore"))
    generated = list(_find_generated_paths(repo_path, warnings))

    if not has_gitignore and generated:
        findings.append(
            Finding(
                file_path=".gitignore",
                severity="medium",
                message="No .gitignore file found, but generated folders are present",
            )
        )

    for name, rel_path, is_dir in generated:
        if not is_ignored(rel_path, is_dir, rules):
            suffix = "/" if is_dir else ""
            findings.append(
                Finding(
                    file_path=rel_path,
                    severity="medium",
                    message=(
                        f"'{name}{suffix}' is present but not covered by .gitignore"
                    ),
                )
            )
    return findings
