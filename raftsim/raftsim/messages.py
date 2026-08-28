"""RPC message types exchanged between nodes.

These mirror the RPCs in the Raft paper (Ongaro & Ousterhout, 2014):

* RequestVote / RequestVoteResult - leader election
* AppendEntries / AppendEntriesResult - log replication *and* heartbeats
  (a heartbeat is just an AppendEntries with ``entries == []``)

The paper assumes an RPC transport where the caller inherently knows which
peer answered. Our SimNetwork only hands back ``(to_id, message)``, so the
two ``*Result`` messages carry an explicit ``responder_id`` to say who
replied.
"""

from dataclasses import dataclass, field


@dataclass
class RequestVote:
    """Sent by a candidate to gather votes for a term."""

    term: int
    candidate_id: str
    last_log_index: int
    last_log_term: int


@dataclass
class RequestVoteResult:
    """A peer's reply to a RequestVote."""

    term: int
    vote_granted: bool
    responder_id: str


@dataclass
class AppendEntries:
    """Sent by a leader. With ``entries == []`` it is purely a heartbeat."""

    term: int
    leader_id: str
    prev_log_index: int
    prev_log_term: int
    entries: list = field(default_factory=list)
    leader_commit: int = 0


@dataclass
class AppendEntriesResult:
    """A peer's reply to an AppendEntries.

    ``match_len`` is the responder's log length after applying the RPC. The
    leader needs it because, by the time this reply arrives, its own log may
    have grown past what it actually sent - so ``len(leader.log)`` is not a
    safe stand-in for "how much the follower has".
    """

    term: int
    success: bool
    responder_id: str
    match_len: int = 0
