"""The Raft node state machine: election, heartbeats, and log replication.

A ``RaftNode`` is deliberately transport-free. It never sleeps, never spawns
a thread and never reads a real clock. Time arrives as an argument to
:meth:`tick`, and outbound RPCs are *returned* for someone else (the
:class:`~raftsim.cluster.Cluster`) to deliver. That makes the whole
algorithm executable as a plain, deterministic function of its inputs.
"""

from __future__ import annotations

import random
from enum import Enum

from .log_entry import LogEntry
from .messages import (
    AppendEntries,
    AppendEntriesResult,
    RequestVote,
    RequestVoteResult,
)

# Randomized election timeout range, in simulated time units. The spread is
# what breaks symmetry between followers so they don't all become candidates
# on the same tick forever.
ELECTION_TIMEOUT_MIN = 150.0
ELECTION_TIMEOUT_MAX = 300.0


class NodeState(Enum):
    FOLLOWER = "follower"
    CANDIDATE = "candidate"
    LEADER = "leader"
    DEAD = "dead"


class RaftNode:
    def __init__(self, node_id, election_deadline: float = 0.0):
        self.node_id = node_id
        self.state = NodeState.FOLLOWER
        self.current_term = 0
        self.voted_for = None
        self.log: list[LogEntry] = []

        # Highest log entry known to be committed, as a COUNT (0 = nothing
        # committed, 3 = entries log[0:3] are committed).
        self.commit_index = 0

        self.election_deadline = election_deadline

        # Last simulated time this node has seen. tick() keeps it current;
        # it lets the RPC handlers re-arm their election timer without every
        # caller threading the clock through every RPC.
        self.last_known_time = 0.0

        # Election bookkeeping (meaningful only while CANDIDATE).
        self.votes_granted_by: set = set()

        # Leader bookkeeping (populated on becoming LEADER). Both are keyed
        # by peer id and measured as COUNTS, matching commit_index above.
        self.next_index: dict = {}
        self.match_index: dict = {}

    # ------------------------------------------------------------------
    # internal helpers
    # ------------------------------------------------------------------

    def _random_timeout(self) -> float:
        return random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)

    def _reset_election_deadline(self, base_time: float) -> None:
        self.election_deadline = base_time + self._random_timeout()

    def _peers(self, peer_ids):
        return [p for p in peer_ids if p != self.node_id]

    def _cluster_size(self, peer_ids) -> int:
        return len(set(peer_ids) | {self.node_id})

    def _majority(self, peer_ids) -> int:
        return self._cluster_size(peer_ids) // 2 + 1

    def _last_log_index(self) -> int:
        return len(self.log) - 1

    def _last_log_term(self) -> int:
        return self.log[-1].term if self.log else 0

    def _step_down(self, new_term: int) -> None:
        self.current_term = new_term
        self.state = NodeState.FOLLOWER
        self.voted_for = None
        self.votes_granted_by = set()
        self.next_index = {}
        self.match_index = {}

    def _become_leader(self, peer_ids) -> None:
        self.state = NodeState.LEADER
        self.next_index = {p: len(self.log) for p in self._peers(peer_ids)}
        self.match_index = {p: 0 for p in self._peers(peer_ids)}

    # ------------------------------------------------------------------
    # driven by the cluster loop
    # ------------------------------------------------------------------

    def tick(self, current_sim_time: float, peer_ids):
        """Advance simulated time and return any RPCs to send.

        * DEAD -> nothing.
        * LEADER -> an AppendEntries (heartbeat / replication) for every peer,
          every tick, regardless of the election timer.
        * FOLLOWER / CANDIDATE -> start an election if the deadline passed,
          returning a RequestVote for every peer; otherwise nothing.
        """
        self.last_known_time = current_sim_time

        if self.state is NodeState.DEAD:
            return []
        if self.state is NodeState.LEADER:
            return self._build_append_entries(peer_ids)
        if current_sim_time >= self.election_deadline:
            return self._start_election(current_sim_time, peer_ids)
        return []

    def _start_election(self, current_sim_time: float, peer_ids):
        self.current_term += 1
        self.state = NodeState.CANDIDATE
        self.voted_for = self.node_id
        self.votes_granted_by = {self.node_id}
        self._reset_election_deadline(current_sim_time)
        return [
            RequestVote(
                term=self.current_term,
                candidate_id=self.node_id,
                last_log_index=self._last_log_index(),
                last_log_term=self._last_log_term(),
            )
            for _ in self._peers(peer_ids)
        ]

    def _build_append_entries(self, peer_ids):
        msgs = []
        for peer_id in self._peers(peer_ids):
            next_i = self.next_index.get(peer_id, len(self.log))
            prev_index = next_i - 1
            prev_term = self.log[prev_index].term if prev_index >= 0 else 0
            msgs.append(
                AppendEntries(
                    term=self.current_term,
                    leader_id=self.node_id,
                    prev_log_index=prev_index,
                    prev_log_term=prev_term,
                    entries=list(self.log[next_i:]),
                    leader_commit=self.commit_index,
                )
            )
        return msgs

    # ------------------------------------------------------------------
    # RPC handlers
    # ------------------------------------------------------------------

    def handle_request_vote(self, msg: RequestVote) -> RequestVoteResult:
        if msg.term > self.current_term:
            self._step_down(msg.term)

        # Raft safety (paper section 5.4.1): only vote for a candidate whose
        # log is at least as up to date as ours.
        log_ok = msg.last_log_term > self._last_log_term() or (
            msg.last_log_term == self._last_log_term()
            and msg.last_log_index >= self._last_log_index()
        )
        granted = (
            msg.term >= self.current_term
            and (self.voted_for is None or self.voted_for == msg.candidate_id)
            and log_ok
        )
        if granted:
            self.voted_for = msg.candidate_id
            self._reset_election_deadline(self.last_known_time)

        return RequestVoteResult(
            term=self.current_term,
            vote_granted=granted,
            responder_id=self.node_id,
        )

    def handle_request_vote_result(self, result: RequestVoteResult, peer_ids) -> None:
        if result.term > self.current_term:
            self._step_down(result.term)
            return
        if self.state is not NodeState.CANDIDATE or result.term != self.current_term:
            return
        if result.vote_granted:
            self.votes_granted_by.add(result.responder_id)
            if len(self.votes_granted_by) >= self._majority(peer_ids):
                self._become_leader(peer_ids)

    def handle_append_entries(self, msg: AppendEntries) -> AppendEntriesResult:
        # Stale leader: reject and tell it our term.
        if msg.term < self.current_term:
            return AppendEntriesResult(self.current_term, False, self.node_id)

        # Valid leader for our term (or a newer one). Accept its authority:
        # adopt its term, drop any candidacy / leadership, re-arm the timer.
        if msg.term > self.current_term:
            self.current_term = msg.term
            self.voted_for = None
        self.state = NodeState.FOLLOWER
        self.votes_granted_by = set()
        self.next_index = {}
        self.match_index = {}
        self._reset_election_deadline(self.last_known_time)

        # Log consistency check (paper section 5.3): our entry at
        # prev_log_index must exist and match prev_log_term.
        prev = msg.prev_log_index
        if prev >= 0 and (prev >= len(self.log) or self.log[prev].term != msg.prev_log_term):
            return AppendEntriesResult(
                self.current_term, False, self.node_id, match_len=len(self.log)
            )

        # Splice in the new entries, deleting only where they actually
        # conflict so a delayed/duplicate heartbeat can't truncate good tail.
        start = prev + 1
        for i, entry in enumerate(msg.entries):
            pos = start + i
            if pos < len(self.log):
                if self.log[pos].term != entry.term:
                    self.log = self.log[:pos]
                    self.log.extend(msg.entries[i:])
                    break
            else:
                self.log.extend(msg.entries[i:])
                break

        if msg.leader_commit > self.commit_index:
            self.commit_index = min(msg.leader_commit, len(self.log))

        return AppendEntriesResult(
            self.current_term, True, self.node_id, match_len=len(self.log)
        )

    def handle_append_entries_result(self, result: AppendEntriesResult, peer_ids) -> None:
        if result.term > self.current_term:
            self._step_down(result.term)
            return
        if self.state is not NodeState.LEADER:
            return

        peer_id = result.responder_id
        if result.success:
            # Trust the follower's own report of how much it has stored, not
            # our current log length (which may have grown since we sent the
            # RPC). match_index is kept monotonic against reordered replies.
            self.match_index[peer_id] = max(
                self.match_index.get(peer_id, 0), result.match_len
            )
            self.next_index[peer_id] = result.match_len
            self._advance_commit(peer_ids)
        else:
            # Walk back and try an earlier prefix next time. The follower's
            # match_len is a lower bound on where we'll find agreement.
            self.next_index[peer_id] = max(
                0, min(self.next_index.get(peer_id, 1) - 1, result.match_len)
            )

    def _advance_commit(self, peer_ids) -> None:
        cluster_size = self._cluster_size(peer_ids)
        for n in range(len(self.log), self.commit_index, -1):
            # Raft only lets a leader commit entries from its *own* term by
            # counting replicas (paper section 5.4.2).
            if self.log[n - 1].term != self.current_term:
                continue
            replicas = 1 + sum(1 for m in self.match_index.values() if m >= n)
            if replicas > cluster_size // 2:
                self.commit_index = n
                break
