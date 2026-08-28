"""Log replication correctness, driven through the Cluster/SimNetwork loop."""

from raftsim.cluster import Cluster
from raftsim.node import NodeState

from _util import advance, advance_until, log_of


def _elect_leader(cluster):
    assert advance_until(cluster, lambda: cluster.current_leader() is not None, 400)
    return cluster.current_leader()


def test_committed_commands_replicate_to_every_live_node():
    cluster = Cluster(5, seed=1)
    _elect_leader(cluster)

    for command in ("set x=1", "set y=2", "set z=3"):
        assert cluster.submit(command)
        advance(cluster, 5)

    assert advance_until(
        cluster,
        lambda: cluster.current_leader() and cluster.current_leader().commit_index >= 3,
        200,
    ), "leader never committed the 3 commands"

    leader = cluster.current_leader()
    expected = log_of(leader)
    assert expected == [(leader.current_term, c) for c in ("set x=1", "set y=2", "set z=3")]

    for node in cluster.live_nodes():
        assert log_of(node) == expected, f"Node {node.node_id} log diverged"


def test_commit_index_never_outruns_a_majority():
    """Safety: an entry must not be reported committed until a majority holds it."""
    cluster = Cluster(5, seed=1)
    _elect_leader(cluster)
    advance(cluster, 20)  # let the leader idle, sending empty heartbeats

    for command in ("p", "q", "r", "s"):
        assert cluster.submit(command)

    for _ in range(60):
        cluster.advance()
        for node in cluster.nodes:
            k = node.commit_index
            if not k:
                continue
            holders = sum(1 for other in cluster.nodes if len(other.log) >= k)
            assert holders > len(cluster.nodes) // 2, (
                f"Node {node.node_id} committed {k} entries but only {holders} "
                f"node(s) actually store that many"
            )


def test_revived_follower_catches_up_to_the_leader():
    cluster = Cluster(5, seed=1)
    _elect_leader(cluster)

    assert cluster.submit("a=1")
    advance(cluster, 10)

    victim = next(n for n in cluster.live_nodes() if n.state is not NodeState.LEADER)
    cluster.kill(victim.node_id)

    for command in ("b=2", "c=3", "d=4"):
        assert cluster.submit(command)
        advance(cluster, 8)

    assert advance_until(
        cluster,
        lambda: cluster.current_leader() and cluster.current_leader().commit_index >= 4,
        200,
    ), "remaining majority never committed while the follower was down"

    cluster.revive(victim.node_id)

    assert advance_until(
        cluster,
        lambda: log_of(cluster.node_by_id[victim.node_id]) == log_of(cluster.current_leader()),
        400,
    ), "revived follower never caught up to the leader's log"

    leader = cluster.current_leader()
    assert log_of(cluster.node_by_id[victim.node_id]) == log_of(leader)
    assert cluster.node_by_id[victim.node_id].commit_index >= 4
