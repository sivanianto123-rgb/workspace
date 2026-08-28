"""The simulation driver: nodes + network + a single-threaded step loop.

:meth:`Cluster.advance` is the whole runtime. It nudges the simulated clock
forward, ticks every live node, and shuttles the RPCs they emit through the
:class:`~raftsim.network.SimNetwork`. Everything the first test in this repo
did by hand now happens here automatically.
"""

from __future__ import annotations

import random

from .log_entry import LogEntry
from .messages import (
    AppendEntries,
    AppendEntriesResult,
    RequestVote,
    RequestVoteResult,
)
from .network import SimNetwork
from .node import ELECTION_TIMEOUT_MAX, ELECTION_TIMEOUT_MIN, NodeState, RaftNode


class Cluster:
    def __init__(self, node_count=5, *, time_step=10, msg_delay=10, seed=None):
        if seed is not None:
            random.seed(seed)

        self.time_step = time_step
        self.msg_delay = msg_delay
        self.sim_time = 0.0

        self.peer_ids = list(range(1, node_count + 1))
        self.nodes = []
        for nid in self.peer_ids:
            node = RaftNode(nid)
            # Stagger the first election so one node reliably gets there first.
            node.election_deadline = random.uniform(
                ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX
            )
            self.nodes.append(node)
        self.node_by_id = {n.node_id: n for n in self.nodes}

        self.network = SimNetwork()

    # ------------------------------------------------------------------
    # the step loop
    # ------------------------------------------------------------------

    def advance(self, time_step=None):
        """Run one simulation step."""
        self.sim_time += self.time_step if time_step is None else time_step

        # 1. Tick every live node; route whatever RPCs it wants to send.
        for node in self.nodes:
            if node.state is NodeState.DEAD:
                continue
            outgoing = node.tick(self.sim_time, self.peer_ids)
            self._route(node, outgoing)

        # 2. Deliver what's due and let receivers reply...
        for to_id, message in self.network.deliver_due_messages(self.sim_time):
            self._handle(to_id, message)
        # 3. ...then flush anything that just came due (multi-hop within a step
        #    when msg_delay < time_step).
        for to_id, message in self.network.deliver_due_messages(self.sim_time):
            self._handle(to_id, message)

    def _route(self, sender, outgoing):
        """Pair each broadcast RPC with a peer and hand it to the network."""
        peers = [p for p in self.peer_ids if p != sender.node_id]
        for peer_id, message in zip(peers, outgoing):
            self.network.send(
                sender.node_id, peer_id, message, self.sim_time, delay=self.msg_delay
            )

    def _handle(self, to_id, message):
        node = self.node_by_id[to_id]
        if node.state is NodeState.DEAD:
            return

        if isinstance(message, RequestVote):
            reply = node.handle_request_vote(message)
            self.network.send(
                to_id, message.candidate_id, reply, self.sim_time, delay=self.msg_delay
            )
        elif isinstance(message, AppendEntries):
            reply = node.handle_append_entries(message)
            self.network.send(
                to_id, message.leader_id, reply, self.sim_time, delay=self.msg_delay
            )
        elif isinstance(message, RequestVoteResult):
            node.handle_request_vote_result(message, self.peer_ids)
        elif isinstance(message, AppendEntriesResult):
            node.handle_append_entries_result(message, self.peer_ids)

    # ------------------------------------------------------------------
    # client-facing operations
    # ------------------------------------------------------------------

    def current_leader(self):
        """The live node most plausibly acting as leader, or ``None``.

        Picks the highest-term LEADER so a not-yet-deposed old leader never
        shadows the real one.
        """
        leaders = [
            n for n in self.nodes
            if n.state is NodeState.LEADER  # DEAD nodes never match
        ]
        if not leaders:
            return None
        return max(leaders, key=lambda n: n.current_term)

    def submit(self, command: str) -> bool:
        """Append ``command`` to the current leader's log. False if leaderless."""
        leader = self.current_leader()
        if leader is None:
            return False
        leader.log.append(LogEntry(term=leader.current_term, command=command))
        return True

    def live_nodes(self):
        return [n for n in self.nodes if n.state is not NodeState.DEAD]

    # ------------------------------------------------------------------
    # fault injection
    # ------------------------------------------------------------------

    def kill(self, node_id):
        """Crash a node: it stops ticking and stops handling messages."""
        self.node_by_id[node_id].state = NodeState.DEAD

    def revive(self, node_id):
        """Restart a crashed node: fresh timer, but its log and term persist."""
        node = self.node_by_id[node_id]
        node.state = NodeState.FOLLOWER
        node.voted_for = None
        node.votes_granted_by = set()
        node.next_index = {}
        node.match_index = {}
        node.last_known_time = self.sim_time
        node.election_deadline = self.sim_time + random.uniform(
            ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX
        )

    def partition(self, group_a, group_b):
        self.network.partition(group_a, group_b)

    def heal(self):
        self.network.heal()
