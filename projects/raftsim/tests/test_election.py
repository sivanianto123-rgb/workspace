"""Election correctness.

The very first version of this file wired three nodes together by hand; that
test is kept below as ``test_election_by_hand`` because it's a nice minimal
check. Everything else drives the real Cluster/SimNetwork loop.
"""

import random

from raftsim.cluster import Cluster
from raftsim.messages import RequestVote, RequestVoteResult
from raftsim.node import NodeState, RaftNode

from _util import advance_until


# ---------------------------------------------------------------------------
# hand-wired unit check (no cluster / no network)
# ---------------------------------------------------------------------------

def test_election_by_hand():
    random.seed(0)
    node_ids = ["n1", "n2", "n3"]
    nodes = {nid: RaftNode(nid) for nid in node_ids}
    candidate = nodes["n1"]

    messages = candidate.tick(1000.0, node_ids)
    assert candidate.state is NodeState.CANDIDATE
    assert candidate.current_term == 1
    assert len(messages) == 2

    followers = [nodes[nid] for nid in node_ids if nid != "n1"]
    results = [f.handle_request_vote(m) for f, m in zip(followers, messages)]
    assert all(r.vote_granted for r in results)

    for r in results:
        candidate.handle_request_vote_result(r, node_ids)

    assert candidate.state is NodeState.LEADER
    assert candidate.current_term == 1


# ---------------------------------------------------------------------------
# cluster-level properties
# ---------------------------------------------------------------------------

def test_at_most_one_leader_per_term_under_no_failures():
    cluster = Cluster(5, seed=1)
    leader_for_term = {}

    for _ in range(600):
        cluster.advance()
        for node in cluster.nodes:
            if node.state is NodeState.LEADER:
                claimed = leader_for_term.get(node.current_term)
                assert claimed in (None, node.node_id), (
                    f"term {node.current_term}: Node {claimed} and Node "
                    f"{node.node_id} both claim leadership"
                )
                leader_for_term[node.current_term] = node.node_id

    assert leader_for_term, "expected a leader to be elected at some point"


def test_new_leader_elected_within_bounded_time_after_crash():
    cluster = Cluster(5, seed=1)

    assert advance_until(cluster, lambda: cluster.current_leader() is not None, 400), (
        "no initial leader"
    )
    old_leader = cluster.current_leader()
    old_term = old_leader.current_term
    cluster.kill(old_leader.node_id)

    def new_leader_up():
        leader = cluster.current_leader()
        return leader is not None and leader.node_id != old_leader.node_id

    assert advance_until(cluster, new_leader_up, 400), (
        "no replacement leader within 400 ticks of the crash"
    )
    assert cluster.current_leader().current_term > old_term
