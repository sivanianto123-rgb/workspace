"""raftsim - a small, deterministic simulation of the Raft consensus algorithm.

Leader election, heartbeats, log replication, and crash / partition fault
injection, all driven by a single-threaded simulated clock.
"""

from .cluster import Cluster
from .log_entry import LogEntry
from .messages import (
    AppendEntries,
    AppendEntriesResult,
    RequestVote,
    RequestVoteResult,
)
from .network import SimNetwork
from .node import NodeState, RaftNode

__all__ = [
    "Cluster",
    "SimNetwork",
    "RaftNode",
    "NodeState",
    "LogEntry",
    "RequestVote",
    "RequestVoteResult",
    "AppendEntries",
    "AppendEntriesResult",
]
