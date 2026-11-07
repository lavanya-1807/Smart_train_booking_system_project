"""FIFO queue helper. This is a project simulation, not official railway policy."""

def next_waiting_request(requests):
    """Return the lowest-ID waiting request, or None."""
    waiting = [
        r for r in requests
        if r["status"] == "WAITING"
    ]

    return min(
        waiting,
        key=lambda r: int(r["id"])
    ) if waiting else None


def can_process_request(requests, request_id):
    """Only the earliest waiting request can be processed."""
    first = next_waiting_request(requests)

    return (
        first is not None
        and int(first["id"]) == int(request_id)
    )