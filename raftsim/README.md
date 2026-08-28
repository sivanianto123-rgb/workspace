# raftsim

A small, dependency-free simulation of the [Raft consensus
algorithm](https://raft.github.io/raft.pdf), built to be *read*. Leader
election, heartbeats, log replication, and crash / network-partition fault
injection all run on a single-threaded simulated clock, so the whole
protocol executes as a deterministic function of its inputs.

## What is Raft, and why does it matter?

A distributed system that stores data on several machines needs them to
**agree** on the order of operations even when machines crash, restart, or
get cut off from each other on the network. That agreement problem is
*consensus*.

Raft is a consensus algorithm designed to be understandable. It works by
electing a single **leader** for a numbered *term*; the leader accepts all
client commands, appends them to a replicated **log**, and copies that log
to the **followers**. An entry is **committed** — safe, permanent, and
never lost — once a *majority* of the cluster has stored it. If the leader
crashes, the remaining nodes notice the missing heartbeats, hold an
election, and a new leader with an up-to-date log takes over. Because every
decision needs a majority, a minority partition can never elect a competing
leader or commit conflicting data — there is no split brain.

Raft is not academic. It is the replication core of:

- **etcd** — the key-value store that holds the entire state of a
  Kubernetes cluster.
- **CockroachDB** — which runs a Raft group per data range to give a
  distributed SQL database serializable transactions.
- **Consul**, **TiKV**, **MongoDB** (its protocol is Raft-derived), and
  many others.

Understanding Raft means understanding how those systems stay correct
through failures.

## Install

Requires Python 3.10+.

```sh
git clone <this repo> && cd raftsim
python -m venv .venv && source .venv/bin/activate
pip install -e '.[dev]'
```

## Run

`raftsim` starts a 5-node cluster and drops into a REPL (pass a number for a
different size, e.g. `raftsim 4`):

```
raftsim> help

    status                  show every node's state
    run <n>                 advance the simulation n steps, narrating changes
    submit <command text>   hand a command to the current leader
    kill <id>               crash a node
    revive <id>             restart a crashed node
    partition <ids> | <ids> split the network into two groups
    heal                    remove the partition
    help                    list commands
    quit / exit             leave
```

Simulated time only moves when you `run`. Set `RAFTSIM_SEED` to make a
session reproducible.

Run the test suite with `pytest`.

## Example session: killing the leader

```
$ RAFTSIM_SEED=1 raftsim
raftsim - 5-node cluster. Type 'help' for commands.

raftsim> run 30
[t=   180] Node 1 became CANDIDATE for term 1
[t=   200] Node 1 won the election, is now LEADER for term 1

raftsim> submit cmd-before-crash
submitted 'cmd-before-crash' to Node 1
raftsim> run 10
[t=   310] commit_index advanced to 1 (latest committed: 'cmd-before-crash')

raftsim> status
ID  STATE     TERM  COMMIT  LOG
-------------------------------
1   LEADER    1     1       [1] cmd-before-crash
2   FOLLOWER  1     1       [1] cmd-before-crash
3   FOLLOWER  1     1       [1] cmd-before-crash
4   FOLLOWER  1     1       [1] cmd-before-crash
5   FOLLOWER  1     1       [1] cmd-before-crash

raftsim> kill 1
Node 1 is now DEAD (it was the leader)

raftsim> run 60
[t=   610] Node 4 became CANDIDATE for term 2
[t=   630] Node 4 won the election, is now LEADER for term 2

raftsim> submit cmd-after-failover
submitted 'cmd-after-failover' to Node 4
raftsim> run 15
[t=  1010] commit_index advanced to 2 (latest committed: 'cmd-after-failover')

raftsim> status
ID  STATE     TERM  COMMIT  LOG
-------------------------------
1   DEAD      1     1       [1] cmd-before-crash
2   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
3   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
4   LEADER    2     2       [2] cmd-before-crash cmd-after-failover
5   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover

raftsim> revive 1
Node 1 revived as FOLLOWER (term 1, 1 log entries kept)
raftsim> run 40

raftsim> status
ID  STATE     TERM  COMMIT  LOG
-------------------------------
1   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
2   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
3   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
4   LEADER    2     2       [2] cmd-before-crash cmd-after-failover
5   FOLLOWER  2     2       [2] cmd-before-crash cmd-after-failover
```

The cluster kept serving writes across the loss of its leader, and the
stale node that came back was force-caught-up to the winning log — exactly
what etcd does when a Kubernetes control-plane node reboots.

## Split brain

With a partition that leaves **no** side holding a majority, nothing can be
committed on either side, and the isolated group cannot elect a rival
leader — it just burns through election terms. After `heal`, the node with
the most up-to-date log wins the next election. Note that an entry stranded
from an earlier term only becomes committed once a *new* entry from the
current leader's term commits on top of it (Raft paper, §5.4.2) — so submit
one more command after healing to see the backlog commit.

```
raftsim> partition 1,2 | 3,4          # 4-node cluster: neither side has 3
raftsim> submit during-partition       # accepted by the leader, never commits
raftsim> run 120                       # side {3,4} cycles terms, elects no one
raftsim> heal
raftsim> submit after-heal
raftsim> run 40                        # commit_index jumps, carrying both entries
```

## Design decisions

### A simulated clock instead of real timers and threads

Every node method takes the current time as a parameter
(`tick(current_sim_time, ...)`), and outbound RPCs are *returned* to the
caller rather than sent. `Cluster.advance()` is the only loop: it moves
`sim_time` forward by a fixed step, ticks each node, and moves messages
through `SimNetwork`, which holds them until a simulated `delivery_time`.
No `threading`, no `asyncio`, no `time.sleep`.

Why:

- **Determinism.** A given seed replays exactly. A bug found in a 2000-tick
  run reproduces every time, which is close to impossible with wall-clock
  timers and real thread scheduling.
- **Fast, controllable failure testing.** Elections use 150–300ms timeouts
  in the paper; here they are 150–300 unitless ticks that pass as fast as
  the loop runs. A test can advance 600 steps through dozens of elections
  in a millisecond, `kill` a node between two exact ticks, and assert on
  the state in between.
- **The algorithm is the point.** Raft's correctness is about *ordering* —
  which message is processed relative to which timeout — not about
  real-time deadlines. Making time an explicit, ordered parameter puts the
  part that matters in the foreground and deletes the accidental complexity
  (locks, races, flakes) that a threaded version would spend most of its
  code on.

The trade-off is that this is a model, not a server: there is no real I/O,
no persistence, and `SimNetwork` reorders and partitions but does not (yet)
duplicate or corrupt messages.

## Layout

```
raftsim/
  log_entry.py   LogEntry(term, command)
  messages.py    RequestVote / AppendEntries and their results
  node.py        RaftNode: the state machine (election + replication)
  network.py     SimNetwork: delayed, partitionable message queue
  cluster.py     Cluster: the advance() step loop, submit(), kill/revive/partition
  cli.py         the REPL
tests/
  test_election.py     one-leader-per-term; failover after a crash
  test_replication.py  logs converge; a revived follower catches up
```
