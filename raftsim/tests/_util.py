"""Shared helpers for the cluster-level tests."""


def advance(cluster, steps):
    for _ in range(steps):
        cluster.advance()


def advance_until(cluster, predicate, max_steps):
    """Advance up to ``max_steps`` times; return True as soon as predicate holds."""
    if predicate():
        return True
    for _ in range(max_steps):
        cluster.advance()
        if predicate():
            return True
    return False


def log_of(node):
    return [(e.term, e.command) for e in node.log]
