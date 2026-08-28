"""A tiny in-process message bus with simulated delivery latency.

No sockets, no threads. Messages sit in a list tagged with the simulated
time they become deliverable; the cluster loop pulls the due ones out on
each step. A partition simply refuses to deliver messages that cross the
split.
"""


class SimNetwork:
    def __init__(self):
        # each item: {"from_id", "to_id", "message", "delivery_time"}
        self._queue: list[dict] = []
        # None, or a pair of frozensets naming the two sides of a split.
        self._partition = None

    def send(self, from_id, to_id, message, current_sim_time, delay=10):
        """Queue ``message`` for delivery at ``current_sim_time + delay``."""
        self._queue.append(
            {
                "from_id": from_id,
                "to_id": to_id,
                "message": message,
                "delivery_time": current_sim_time + delay,
            }
        )

    def deliver_due_messages(self, current_sim_time):
        """Pop and return every message whose delivery time has arrived.

        Returns a list of ``(to_id, message)`` tuples. Messages that would
        have to cross an active partition are dropped here rather than
        returned.
        """
        due, pending, delivered = [], [], []
        for item in self._queue:
            if item["delivery_time"] <= current_sim_time:
                due.append(item)
            else:
                pending.append(item)
        self._queue = pending

        for item in due:
            if self._blocked(item["from_id"], item["to_id"]):
                continue
            delivered.append((item["to_id"], item["message"]))
        return delivered

    # -- partitions ---------------------------------------------------

    def partition(self, group_a, group_b):
        """Split the cluster: nothing flows between the two groups."""
        self._partition = (frozenset(group_a), frozenset(group_b))

    def heal(self):
        """Remove any active partition."""
        self._partition = None

    def _blocked(self, from_id, to_id) -> bool:
        if self._partition is None:
            return False
        side_a, side_b = self._partition
        return (from_id in side_a and to_id in side_b) or (
            from_id in side_b and to_id in side_a
        )
