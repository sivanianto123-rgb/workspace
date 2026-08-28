"""The Finding dataclass, the common currency passed between checks and the formatter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Optional

Severity = Literal["high", "medium", "low"]


@dataclass
class Finding:
    """A single problem discovered by a check.

    Attributes:
        file_path: Path to the offending file, relative to the scanned repo.
        line_number: 1-based line the problem was found on, or None if it is a
            file- or repo-level problem with no meaningful line.
        severity: One of "high", "medium", "low".
        message: Human-readable description of the problem.
    """

    file_path: str
    severity: Severity
    message: str
    line_number: Optional[int] = None
