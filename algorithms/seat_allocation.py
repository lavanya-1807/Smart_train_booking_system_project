"""Seat allocation helpers based on station-index intervals."""

def intervals_overlap(start_a, end_a, start_b, end_b):
    """True when [start_a, end_a) and [start_b, end_b) share a segment."""
    return start_a < end_b and start_b < end_a

def find_continuous_seat(
    bookings,
    source_idx,
    destination_idx,
    seat_count=24,
    first_seat=1
):
    """
    Find an available seat within the requested seat range.
    """
    last_seat = first_seat + seat_count - 1

    for seat in range(first_seat, last_seat + 1):
        conflict = any(
            int(row["seat_no"]) == seat
            and row["status"] == "CONFIRMED"
            and intervals_overlap(
                source_idx,
                destination_idx,
                int(row["source_idx"]),
                int(row["destination_idx"])
            )
            for row in bookings
        )

        if not conflict:
            return seat

    return None

def find_gap_seat(bookings, source_idx, destination_idx, seat_count=24):
    """
    Simplified project-specific model:
    find a seat with a current booking that ends after the new passenger's
    source but before their destination. The passenger may wait until release.
    Returns (seat_no, release_station_idx), or (None, None).

    Note: a real implementation must model each station segment, timetable,
    platform/coach access, seat availability and all existing bookings.
    """
    active = [b for b in bookings if b["status"] == "CONFIRMED"]
    for seat in range(1, seat_count + 1):
        seat_rows = [b for b in active if int(b["seat_no"]) == seat]
        for old in seat_rows:
            release_idx = int(old["destination_idx"])
            if int(old["source_idx"]) <= source_idx < release_idx < destination_idx:
                # Check no other booking conflicts with the proposed post-release segment.
                conflict_after_release = any(
                    intervals_overlap(release_idx, destination_idx,
                                      int(other["source_idx"]), int(other["destination_idx"]))
                    for other in seat_rows if other is not old
                )
                if not conflict_after_release:
                    return seat, release_idx
    return None, None


def count_available_seats(
    bookings,
    source_idx,
    destination_idx,
    seat_count=24,
    first_seat=1
):
    """Count available seats within a specific seat range."""
    available = 0
    last_seat = first_seat + seat_count - 1

    for seat in range(first_seat, last_seat + 1):
        conflict = any(
            int(row["seat_no"]) == seat
            and row["status"] == "CONFIRMED"
            and intervals_overlap(
                source_idx,
                destination_idx,
                int(row["source_idx"]),
                int(row["destination_idx"])
            )
            for row in bookings
        )

        if not conflict:
            available += 1

    return available


def find_multileg_seat(
    bookings,
    source_idx,
    destination_idx,
    seat_count=24
):
    """
    Find a seat that becomes available at an intermediate station
    after the passenger's requested source.

    Returns (seat_no, release_station_idx), or (None, None).
    """
    active = [
        booking for booking in bookings
        if booking["status"] == "CONFIRMED"
    ]

    for seat in range(1, seat_count + 1):
        seat_bookings = [
            booking for booking in active
            if int(booking["seat_no"]) == seat
        ]

        for old in seat_bookings:
            old_source = int(old["source_idx"])
            release_idx = int(old["destination_idx"])

            # Seat must be occupied at the requested source,
            # then released before the requested destination.
            if not (
                old_source <= source_idx
                < release_idx
                < destination_idx
            ):
                continue

            # Check whether another booking conflicts with the
            # proposed seat use after the release station.
            conflict = any(
                intervals_overlap(
                    release_idx,
                    destination_idx,
                    int(other["source_idx"]),
                    int(other["destination_idx"])
                )
                for other in seat_bookings
                if other is not old
            )

            if not conflict:
                return seat, release_idx

    return None, None
