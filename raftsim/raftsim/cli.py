"""A minimal REPL for driving a cluster by hand.

Commands::

    status                  show every node's state
    run <n>                 advance the simulation n steps, narrating changes
    submit <command text>   hand a command to the current leader
    kill <id>               crash a node
    revive <id>             restart a crashed node
    partition <ids> | <ids> split the network into two groups
    heal                    remove the partition
    help                    list commands
    quit / exit             leave

``python -m raftsim.cli`` and the installed ``raftsim`` entry point both
start a 5-node cluster and drop straight into this loop.
"""

from __future__ import annotations

import os
import random
import sys

from .cluster import Cluster
from .node import NodeState

BANNER = "raftsim - {n}-node cluster. Type 'help' for commands."


# ----------------------------------------------------------------------
# rendering
# ----------------------------------------------------------------------

def render_status(cluster: Cluster) -> str:
    rows = [("ID", "STATE", "TERM", "COMMIT", "LOG")]
    for node in cluster.nodes:
        commands = " ".join(e.command for e in node.log) or "-"
        rows.append(
            (
                str(node.node_id),
                node.state.name,
                str(node.current_term),
                str(node.commit_index),
                f"[{len(node.log)}] {commands}",
            )
        )
    widths = [max(len(r[i]) for r in rows) for i in range(4)]
    out = []
    for i, row in enumerate(rows):
        line = "  ".join(row[j].ljust(widths[j]) for j in range(4))
        line = f"{line}  {row[4]}"
        out.append(line)
        if i == 0:
            out.append("-" * len(line))
    return "\n".join(out)


def _leader_commit(cluster: Cluster) -> int:
    leader = cluster.current_leader()
    return leader.commit_index if leader else 0


def run(cluster: Cluster, steps: int, out=print) -> None:
    prev = {n.node_id: (n.state, n.current_term) for n in cluster.nodes}
    prev_commit = _leader_commit(cluster)

    for _ in range(steps):
        cluster.advance()
        stamp = f"[t={cluster.sim_time:>6.0f}]"

        for node in cluster.nodes:
            key = (node.state, node.current_term)
            was_state, _ = prev[node.node_id]
            if key == prev[node.node_id]:
                continue
            if node.state is NodeState.CANDIDATE:
                out(f"{stamp} Node {node.node_id} became CANDIDATE for term {node.current_term}")
            elif node.state is NodeState.LEADER:
                out(f"{stamp} Node {node.node_id} won the election, is now LEADER for term {node.current_term}")
            elif node.state is NodeState.FOLLOWER and was_state is NodeState.LEADER:
                out(f"{stamp} Node {node.node_id} stepped down to FOLLOWER (term {node.current_term})")
            prev[node.node_id] = key

        commit = _leader_commit(cluster)
        if commit > prev_commit:
            leader = cluster.current_leader()
            newest = leader.log[commit - 1].command if leader and commit else "?"
            out(f"{stamp} commit_index advanced to {commit} (latest committed: {newest!r})")
            prev_commit = commit


# ----------------------------------------------------------------------
# command dispatch
# ----------------------------------------------------------------------

def _parse_partition(arg: str):
    left, right = arg.split("|")
    to_ids = lambda s: [int(x) for x in s.replace(",", " ").split()]
    return to_ids(left), to_ids(right)


def dispatch(cluster: Cluster, line: str, out=print) -> bool:
    """Run one command. Returns False when the loop should exit."""
    line = line.strip()
    if not line:
        return True
    cmd, _, arg = line.partition(" ")
    cmd = cmd.lower()
    arg = arg.strip()

    if cmd in ("quit", "exit"):
        return False
    if cmd in ("help", "?"):
        out(__doc__.split("Commands::", 1)[1].split("``python", 1)[0].rstrip())
    elif cmd == "status":
        out(render_status(cluster))
    elif cmd == "run":
        run(cluster, int(arg) if arg else 1, out=out)
    elif cmd == "submit":
        if not arg:
            out("usage: submit <command text>")
        elif cluster.submit(arg):
            out(f"submitted {arg!r} to Node {cluster.current_leader().node_id}")
        else:
            out("no leader - command rejected")
    elif cmd == "kill":
        nid = int(arg)
        was_leader = cluster.current_leader() and cluster.current_leader().node_id == nid
        cluster.kill(nid)
        out(f"Node {nid} is now DEAD" + (" (it was the leader)" if was_leader else ""))
    elif cmd == "revive":
        nid = int(arg)
        cluster.revive(nid)
        out(f"Node {nid} revived as FOLLOWER (term {cluster.node_by_id[nid].current_term}, "
            f"{len(cluster.node_by_id[nid].log)} log entries kept)")
    elif cmd == "partition":
        a, b = _parse_partition(arg)
        cluster.partition(a, b)
        out(f"partitioned: {a} | {b}")
    elif cmd == "heal":
        cluster.heal()
        out("partition healed")
    else:
        out(f"unknown command: {cmd!r} (try 'help')")
    return True


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    node_count = int(argv[0]) if argv else 5

    seed = os.environ.get("RAFTSIM_SEED")
    cluster = Cluster(node_count, seed=int(seed) if seed is not None else None)

    print(BANNER.format(n=node_count))
    while True:
        try:
            line = input("raftsim> ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not dispatch(cluster, line):
            break
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
