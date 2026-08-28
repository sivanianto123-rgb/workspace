# Issues & bugs encountered while building raftsim

A running log of the problems hit during development, why they happened, and
how they were resolved. Ordered roughly by when they surfaced.

---

## 1. `pytest` not available in the environment

**Symptom.** `python3 -m pytest` → `No module named pytest`.

**Cause.** System Python had no test runner installed, and installing into it
directly is undesirable.

**Fix.** Created a project virtualenv (`.venv/`) and `pip install -e '.[dev]'`,
which pulls `pytest` from the `dev` optional-dependency group in
`pyproject.toml`. `.venv/` is git-ignored.

---

## 2. `RequestVoteResult` / `AppendEntriesResult` had no "who replied" field

**Symptom.** The leader/candidate receiving a result RPC could not tell which
peer it came from, so it could not update `next_index` / `match_index` for the
right peer or de-duplicate votes.

**Cause.** The Raft paper assumes an RPC transport where the caller inherently
knows which peer answered. `SimNetwork.deliver_due_messages()` only returns
`(to_id, message)` — the sender identity is dropped.

**Fix.** Added `responder_id` to both `*Result` dataclasses. This is a
deliberate, documented deviation from the paper's field list: it restores
information a real RPC framework would provide for free. Vote counting then
uses a `set` of responder ids (`votes_granted_by`) instead of a bare counter,
which is also idempotent against duplicate delivery.

---

## 3. All nodes start with `election_deadline = 0` → lock-step elections

**Symptom.** In an early version every node became a candidate for term 1 on
the very first `tick`, split the vote 5 ways, and repeated — no leader ever
emerged in a deterministic run.

**Cause.** Identical initial deadlines + identical simulated time on every
node = perfectly symmetric behaviour. Randomised *timeouts* only de-sync nodes
*after* the first round.

**Fix.** `Cluster.__init__` seeds each node with a randomised initial
`election_deadline = uniform(150, 300)` so one node reliably reaches its
timeout first and wins cleanly. This also matches how a real cluster behaves
on cold start.

---

## 4. **Safety bug: `commit_index` advanced before a majority had the entry**

**Severity.** High — this violated Raft's core guarantee (a committed entry is
durable on a majority and can never be lost).

**Symptom.** Regression test `test_commit_index_never_outruns_a_majority`
failed:

```
Node 1 committed 4 entries but only 1 node(s) actually store that many
```

The leader reported entries committed while **zero** followers held them.

**Cause.** `handle_append_entries_result` did, on every successful reply:

```python
self.match_index[peer_id] = len(self.log)   # WRONG
```

`len(self.log)` is the leader's log length *now*. But a reply can arrive one
or more hops after it was sent, and the leader's log may have grown in that
window (e.g. a client `submit` landed while old empty heartbeats were still in
flight). Those stale `success` replies were then credited against the *new,
longer* log, inflating `match_index`, and `_advance_commit` counted a
non-existent majority.

Trigger in practice: let the leader idle (emitting empty heartbeats), then
`submit` several commands at once. The empty-heartbeat replies come back
`success=True` and immediately push `commit_index` to the new log length.

**Fix.**
- Added `match_len` to `AppendEntriesResult`: the follower reports its *own*
  log length after applying the RPC.
- The leader now uses `result.match_len`, not `len(self.log)`:
  ```python
  self.match_index[peer_id] = max(self.match_index.get(peer_id, 0), result.match_len)
  self.next_index[peer_id]  = result.match_len
  ```
- `match_index` is kept monotonic with `max(...)` so a reordered/late reply
  can never walk an acknowledgement backwards.
- On failure, `next_index` is walked back by 1 but also clamped to
  `result.match_len` as a lower bound, so back-tracking converges faster.

**Observable effect of the fix.** `commit_index` now *lags* real replication
by one message hop instead of racing ahead of it. In the crash demo the first
commit prints at `t=330` instead of `t=310`. All final states are unchanged.

**Why the original tests missed it.** They only asserted the *final,
converged* state, which was always correct — followers caught up a tick or two
after the premature commit. The new test checks the invariant on *every*
`advance()`.

---

## 5. Entry stranded from an earlier term won't commit after a partition heals

**Not a bug — correct Raft behaviour, but surprising.**

**Symptom.** In the partition demo, after `heal` and a new leader is elected,
the command submitted during the partition is present in every node's log but
`commit_index` stays put. It only commits after one *more* command is
submitted.

**Cause.** Raft (paper §5.4.2, "Figure 8") forbids a leader from committing an
entry from a *previous* term by replica-counting alone. A stranded entry only
becomes committed once an entry from the *current* leader's term is committed
on top of it.

**Resolution.** Documented in `README.md`; the demo submits one command after
healing to show the backlog commit. (A real deployment usually has the new
leader commit a no-op entry on election to close this gap immediately; not
implemented here to keep `commit_index` values in the tests predictable.)

---

## 6. A 5-node cluster cannot be split so that *neither* side has a majority

**Symptom.** The split-brain demo asks for a partition where neither side can
commit, but any 2-way split of 5 nodes leaves one side with 3 (a majority).

**Resolution.** The split-brain demo uses a **4-node** cluster (`raftsim 4`),
split `2 | 2`, where a majority is 3 and neither side qualifies. The
`partition` command itself works on any cluster size.

---

## 7. Fragility: broadcast RPCs are matched to peers by `zip` order

**Not currently a bug, but a latent trap.**

`Cluster._route` pairs the list of RPCs returned by `tick()` with peers using
`zip(peers, outgoing)`. This is only correct because `RaftNode` builds that
list by iterating `[p for p in peer_ids if p != self.node_id]` and the cluster
iterates the identical filter. If either side's iteration order changes, RPCs
would be silently misrouted with no error.

**Mitigation.** Both call sites are commented. A more robust design would have
`tick()` return `(peer_id, message)` pairs directly.

---

## 8. `deliver_due_messages` double-call per `advance()`

**Design note, not a bug.** `Cluster.advance()` calls
`network.deliver_due_messages()` twice. With the default `msg_delay == time_step`
the second call is almost always a no-op. It exists so that when
`msg_delay < time_step`, a multi-hop exchange (RPC + reply) can complete
inside a single step instead of stalling for a whole extra step.
