"""A single entry in a node's replicated log."""

from dataclasses import dataclass


@dataclass
class LogEntry:
    """One command, tagged with the term in which the leader created it."""

    term: int
    command: str
