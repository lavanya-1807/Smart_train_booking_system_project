
from algorithms.seat_allocation import (
    find_continuous_seat,
    find_gap_seat,
    find_multileg_seat,
    count_available_seats,
)

# Demo route:
# 0 Chennai Central
# 1 Katpadi Junction
# 2 Salem Junction
# 3 Erode Junction
# 4 Coimbatore Junction

bookings = [
    {
        "seat_no": 1,
        "source_idx": 0,
        "destination_idx": 2,
        "status": "CONFIRMED",
    }
]

# Test 1: Salem -> Coimbatore.
# Seat 1 should be reusable because the journeys do not overlap.
seat = find_continuous_seat(bookings, 2, 4, 24)
print("Normal booking seat:", seat)

# Test 2: Katpadi -> Coimbatore.
# Seat 1 is occupied until Salem, so a gap option may be offered.
gap_seat, release_idx = find_gap_seat(bookings, 1, 4, 24)
print("Gap booking:", gap_seat, release_idx)

# Test 3: Multi-leg function.
multi_seat, multi_release = find_multileg_seat(
    bookings, 1, 4, 24
)
print("Multi-leg booking:", multi_seat, multi_release)

# Test 4: Number of seats available for the full journey.
available = count_available_seats(bookings, 1, 4, 24)
print("Fully available seats:", available)
