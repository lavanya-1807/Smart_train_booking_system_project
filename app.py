from datetime import datetime
from railway_data import load_railway_data
from flask import Flask, render_template, request, redirect, url_for, flash
from database import get_connection, init_db
from algorithms.seat_allocation import (
    find_continuous_seat,
    find_gap_seat,
    count_available_seats
)
from algorithms.tatkal_queue import can_process_request
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "development-only-change-me"

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = "login"
login_manager.login_message = "Please log in to access this page."


class User(UserMixin):
    def __init__(self, user_id, username, role):
        self.id = str(user_id)
        self.username = username
        self.role = role


@login_manager.user_loader
def load_user(user_id):
    with get_connection() as con:
        row = con.execute(
            "SELECT id, username, role FROM users WHERE id = ?",
            (user_id,)
        ).fetchone()

    if row is None:
        return None

    return User(row["id"], row["username"], row["role"])

@app.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        if len(username) < 3:
            flash("Username must contain at least 3 characters.", "error")
            return redirect(url_for("register"))

        if len(password) < 8:
            flash("Password must contain at least 8 characters.", "error")
            return redirect(url_for("register"))

        password_hash = generate_password_hash(password)

        try:
            with get_connection() as con:
                con.execute(
                    """
                    INSERT INTO users (username, password_hash, role, created_at)
                    VALUES (?, ?, 'user', ?)
                    """,
                    (
                        username,
                        password_hash,
                        datetime.now().isoformat(timespec="seconds")
                    )
                )
        except Exception:
            flash("Username may already exist. Please try another.", "error")
            return redirect(url_for("register"))

        flash("Account created successfully. Please log in.", "success")
        return redirect(url_for("login"))

    return render_template("register.html")



@app.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("index"))

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        selected_role = request.form.get("role", "user")

        with get_connection() as con:
            user_row = con.execute(
                """
                SELECT id, username, password_hash, role
                FROM users
                WHERE username = ?
                """,
                (username,)
            ).fetchone()

        if (
            user_row
            and check_password_hash(user_row["password_hash"], password)
            and user_row["role"] == selected_role
        ):
            user = User(
                user_row["id"],
                user_row["username"],
                user_row["role"]
            )
            login_user(user)

            flash("Login successful!", "success")

            if user.role == "admin":
                return redirect(url_for("dashboard"))

            return redirect(url_for("index"))

        flash("Invalid username, password, or login type.", "error")

    return render_template("login.html")




@app.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    flash("You have logged out successfully.", "success")
    return redirect(url_for("login"))


STATIONS, TRAINS = load_railway_data()

SEAT_COUNT = 24

RESERVED_SEAT_COUNT = 18
TATKAL_SEAT_COUNT = 6

def get_or_create_train_quota(train_id, journey_date):
    from database import get_connection
    from datetime import datetime

    with get_connection() as con:
        con.execute("""
            INSERT OR IGNORE INTO train_quotas
            (train_id, journey_date, reserved_quota, tatkal_quota, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (
            str(train_id),
            journey_date,
            RESERVED_SEAT_COUNT,
            TATKAL_SEAT_COUNT,
            datetime.now().isoformat()
        ))

        row = con.execute("""
            SELECT reserved_quota, tatkal_quota
            FROM train_quotas
            WHERE train_id = ? AND journey_date = ?
        """, (str(train_id), journey_date)).fetchone()

        return row

def get_train(train_id):
    return next((t for t in TRAINS if t["id"] == train_id), None)

def get_bookings_for_date(train_id, journey_date):
    with get_connection() as con:
        return con.execute("""
            SELECT * FROM bookings
            WHERE train_id=? AND journey_date=? AND status='CONFIRMED'
            ORDER BY id
        """, (train_id, journey_date)).fetchall()

def create_booking(data, seat, booking_type, gap_start=None, gap_hours=0):
    pnr = "DEMO" + datetime.now().strftime("%y%m%d%H%M%S%f")[-10:]

    with get_connection() as con:
        con.execute("""
            INSERT INTO bookings
            (
                pnr, passenger_name, train_id, train_name,
                journey_date, source, destination,
                source_idx, destination_idx, coach, seat_no,
                booking_type, status, gap_start, gap_hours,
                created_at, user_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'S1', ?, ?, 'CONFIRMED', ?, ?, ?, ?)
        """, (
            pnr,
            data["passenger_name"],
            data["train_id"],
            data["train_name"],
            data["journey_date"],
            data["source"],
            data["destination"],
            data["source_idx"],
            data["destination_idx"],
            seat,
            booking_type,
            gap_start,
            gap_hours,
            datetime.now().isoformat(timespec="seconds"),
            current_user.id
        ))

    return pnr

@app.route("/")
def index():
    if not current_user.is_authenticated:
        return redirect(url_for("login"))

    today = datetime.now().strftime("%Y-%m-%d")

    return render_template(
        "index.html",
        stations=STATIONS,
        trains=TRAINS,
        today=today
)



@app.route("/search", methods=["POST"])
@login_required
def search():
    name = request.form.get("passenger_name", "").strip()
    journey_date = request.form.get("journey_date", "")
    source = request.form.get("source", "")
    destination = request.form.get("destination", "")

    if (
        not name
        or not journey_date
        or source not in STATIONS
        or destination not in STATIONS
    ):
        flash("Please enter all fields and choose valid stations.", "error")
        return redirect(url_for("index"))

    if source == destination:
        flash("Source and destination must be different.", "error")
        return redirect(url_for("index"))

    train_results = []

    for train in TRAINS:
        route = train.get("route", [])

        # Only show trains that serve both stations in the correct order.
        if source not in route or destination not in route:
            continue

        source_idx = route.index(source)
        destination_idx = route.index(destination)

        if source_idx >= destination_idx:
            continue

        train_id = str(train["id"])
        bookings = get_bookings_for_date(train_id, journey_date)

        normal_seat = find_continuous_seat(
        bookings,
        source_idx,
        destination_idx,
        RESERVED_SEAT_COUNT
        )

        available_seats = count_available_seats(
        bookings,
        source_idx,
        destination_idx,
        RESERVED_SEAT_COUNT
        )

        gap_seat, release_idx = find_gap_seat(
            bookings,
            source_idx,
            destination_idx,
            RESERVED_SEAT_COUNT
        )

        tatkal_available = count_available_seats(
    bookings,
    source_idx,
    destination_idx,
    TATKAL_SEAT_COUNT,
    first_seat=RESERVED_SEAT_COUNT + 1
)
        train_results.append({
            "train": train,
            "normal_seat": normal_seat,
            "available_seats": available_seats,
            "gap_seat": gap_seat,
            "release_station": (
                route[release_idx] if release_idx is not None else None
            ),
            "gap_hours": 1 if release_idx is not None else None,
            "source_idx": source_idx,
            "destination_idx": destination_idx,
            "tatkal_available": tatkal_available
        })

    return render_template(
        "options.html",
        passenger_name=name,
        journey_date=journey_date,
        source=source,
        destination=destination,
        train_results=train_results
    )


@app.route("/book", methods=["POST"])
@login_required
def book():
    data = {
        "passenger_name": request.form.get("passenger_name", "").strip(),
        "train_id": request.form.get("train_id", "").strip(),
        "journey_date": request.form.get("journey_date", "").strip(),
        "source": request.form.get("source", "").strip(),
        "destination": request.form.get("destination", "").strip(),
    }

    if not all(data.values()):
        flash("Please fill in all booking details.", "error")
        return redirect(url_for("index"))

    train = get_train(data["train_id"])

    if not train:
        flash("Invalid train selected.", "error")
        return redirect(url_for("index"))

    route = train.get("route", [])

    # Check that both stations belong to this train's route.
    if data["source"] not in route or data["destination"] not in route:
        flash("This train does not serve the selected stations.", "error")
        return redirect(url_for("index"))

    # Calculate station indexes on the selected train's route.
    source_idx = route.index(data["source"])
    destination_idx = route.index(data["destination"])

    if source_idx >= destination_idx:
        flash("Destination must come after source on this train's route.", "error")
        return redirect(url_for("index"))

    # Never rely on station indexes submitted by the browser.
    data["source_idx"] = source_idx
    data["destination_idx"] = destination_idx
    data["train_name"] = train["name"]

    bookings = get_bookings_for_date(
        data["train_id"],
        data["journey_date"]
    )

    mode = request.form.get("mode", "normal").strip()

    if mode == "normal":
        quota = get_or_create_train_quota(
        data["train_id"],
        data["journey_date"]
        )

        reserved_quota = quota["reserved_quota"]

        seat = find_continuous_seat(
        bookings,
        source_idx,
        destination_idx,
        reserved_quota
    )

        if seat is None:
            flash("No continuous seat is available for this journey.", "error")
            return redirect(url_for("index"))

        pnr = create_booking(
            data,
            seat,
            "Normal"
        )

    elif mode == "gap":
        quota = get_or_create_train_quota(
        data["train_id"],
         data["journey_date"]
        )

        reserved_quota = quota["reserved_quota"]
        if request.form.get("accept_gap") != "yes":
            flash("Please accept the gap booking option.", "error")
            return redirect(url_for("index"))

        seat, release_idx = find_gap_seat(
    bookings,
    source_idx,
    destination_idx,
    reserved_quota
)

        if seat is None or release_idx is None:
            flash("No suitable gap seat is available.", "error")
            return redirect(url_for("index"))

        if not (source_idx < release_idx < destination_idx):
            flash("The gap seat is not valid for this journey.", "error")
            return redirect(url_for("index"))

        pnr = create_booking(
            data,
            seat,
            "Multi-Leg Gap",
            gap_start=route[release_idx],
            gap_hours=1
        )

    else:
        flash("Invalid booking mode.", "error")
        return redirect(url_for("index"))

    flash("Booking successful!", "success")
    return redirect(url_for("confirmation", pnr=pnr))


@app.route("/confirmation/<pnr>")
@login_required
def confirmation(pnr):
    with get_connection() as con:
        if current_user.role == "admin":
            booking = con.execute(
                "SELECT * FROM bookings WHERE pnr = ?",
                (pnr,)
            ).fetchone()
        else:
            booking = con.execute(
                "SELECT * FROM bookings WHERE pnr = ? AND user_id = ?",
                (pnr, current_user.id)
            ).fetchone()

    if booking is None:
        flash("Booking not found or access denied.", "error")
        return redirect(url_for("bookings"))

    return render_template("confirmation.html", booking=booking)


@app.route("/bookings")
@login_required
def bookings():
    with get_connection() as con:
        if current_user.role == "admin":
            # Admin can view all bookings
            rows = con.execute(
                "SELECT * FROM bookings ORDER BY id DESC"
            ).fetchall()
        else:
            # Users can view only their own bookings
            rows = con.execute(
                """
                SELECT * FROM bookings
                WHERE user_id = ?
                ORDER BY id DESC
                """,
                (current_user.id,)
            ).fetchall()

    return render_template("bookings.html", bookings=rows)


@app.route("/cancel/<pnr>", methods=["POST"])
@login_required
def cancel(pnr):
    with get_connection() as con:
        if current_user.role == "admin":
            result = con.execute(
                """
                UPDATE bookings
                SET status = 'CANCELLED'
                WHERE pnr = ? AND status = 'CONFIRMED'
                """,
                (pnr,)
            )
        else:
            result = con.execute(
                """
                UPDATE bookings
                SET status = 'CANCELLED'
                WHERE pnr = ?
                  AND user_id = ?
                  AND status = 'CONFIRMED'
                """,
                (pnr, current_user.id)
            )

    if result.rowcount > 0:
        flash("Booking cancelled successfully.", "success")
    else:
        flash("Booking not found or you are not allowed to cancel it.", "error")

    return redirect(url_for("bookings"))

@app.route("/tatkal", methods=["GET", "POST"])
@login_required
def tatkal():
    if request.method == "POST":
        data = {
            key: request.form.get(key, "").strip()
            for key in [
                "passenger_name",
                "train_id",
                "journey_date",
                "source",
                "destination"
            ]
        }

        if not all(data.values()):
            flash("Please fill all request fields correctly.", "error")
            return redirect(url_for("tatkal"))

        train = get_train(data["train_id"])

        if not train:
            flash("Please choose a valid train.", "error")
            return redirect(url_for("tatkal"))

        route = train.get("route", [])

        if (
            data["source"] not in route
            or data["destination"] not in route
        ):
            flash("Selected stations are not on this train route.", "error")
            return redirect(url_for("tatkal"))

        source_idx = route.index(data["source"])
        destination_idx = route.index(data["destination"])

        if source_idx >= destination_idx:
            flash("Destination must be after source.", "error")
            return redirect(url_for("tatkal"))

        route = train.get("route", [])
        source_idx = route.index(data["source"])
        destination_idx = route.index(data["destination"])

        bookings = get_bookings_for_date(
            data["train_id"],
            data["journey_date"]
        )

        reserved_available = count_available_seats(
            bookings,
            source_idx,
            destination_idx,
            RESERVED_SEAT_COUNT
        )

        if reserved_available > 0:
            flash(
                "Tatkal is not open yet. Reserved seats are still available.",
                "error"
            )
            return redirect(url_for("tatkal"))

        tatkal_available = count_available_seats(
            bookings,
            source_idx,
            destination_idx,
            TATKAL_SEAT_COUNT,
            first_seat=RESERVED_SEAT_COUNT + 1
        )

        if tatkal_available == 0:
            flash("Tatkal quota is FULL for this journey.", "error")
            return redirect(url_for("tatkal"))

        with get_connection() as con:
            con.execute("""
                INSERT INTO tatkal_requests
                (
                    passenger_name, train_id, journey_date,
                    source, destination, status, created_at, user_id
                )
                VALUES (?, ?, ?, ?, ?, 'WAITING', ?, ?)
            """, (
                data["passenger_name"],
                data["train_id"],
                data["journey_date"],
                data["source"],
                data["destination"],
                datetime.now().isoformat(timespec="seconds"),
                current_user.id
            ))

        flash("Tatkal request added successfully.", "success")
        return redirect(url_for("tatkal"))

    with get_connection() as con:
        if current_user.role == "admin":
            rows = con.execute("""
                SELECT * FROM tatkal_requests ORDER BY id
            """).fetchall()
        else:
            rows = con.execute("""
                SELECT * FROM tatkal_requests
                WHERE user_id = ?
                ORDER BY id DESC
            """, (current_user.id,)).fetchall()

    request_items = []

    for r in rows:
        item = dict(r)

        train = get_train(r["train_id"])
        route = train.get("route", []) if train else []

        if (
            r["source"] not in route
            or r["destination"] not in route
        ):
            item["availability_status"] = "INVALID ROUTE"
            request_items.append(item)
            continue

        source_idx = route.index(r["source"])
        destination_idx = route.index(r["destination"])

        bookings = get_bookings_for_date(
        r["train_id"],
        r["journey_date"]
        )

        reserved_available = count_available_seats(
        bookings,
        source_idx,
        destination_idx,
        RESERVED_SEAT_COUNT
        )

        tatkal_available = count_available_seats(
        bookings,
        source_idx,
        destination_idx,
        TATKAL_SEAT_COUNT,
        first_seat=RESERVED_SEAT_COUNT + 1
        )

        if reserved_available > 0:
            item["availability_status"] = "CLOSED"
        elif tatkal_available > 0:
            item["availability_status"] = "AVAILABLE"
        else:
            item["availability_status"] = "FULL"

        item["reserved_available"] = reserved_available
        item["tatkal_available"] = tatkal_available

        request_items.append(item)

    return render_template(
    "tatkal.html",
    stations=STATIONS,
    trains=TRAINS,
    requests=request_items,
    prefill={
        "passenger_name": request.args.get("passenger_name", ""),
        "train_id": request.args.get("train_id", ""),
        "journey_date": request.args.get("journey_date", ""),
        "source": request.args.get("source", ""),
        "destination": request.args.get("destination", "")
    }
)
@app.route("/tatkal/process/<int:req_id>", methods=["POST"])
@login_required
def process_tatkal(req_id):

    # Only admin can process Tatkal requests
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("tatkal"))

    with get_connection() as con:

        # Get all waiting requests in FIFO order
        pending_rows = con.execute(
            """
            SELECT * FROM tatkal_requests
            WHERE status='WAITING'
            ORDER BY id
            """
        ).fetchall()

        # Reject old requests with invalid routes
        for pending in pending_rows:

            pending_train = get_train(pending["train_id"])

            if pending_train is None:
                con.execute(
                    """
                    UPDATE tatkal_requests
                    SET status='REJECTED'
                    WHERE id=?
                    """,
                    (pending["id"],)
                )
                continue

            pending_route = pending_train.get("route", [])

            if (
                pending["source"] not in pending_route
                or pending["destination"] not in pending_route
            ):
                con.execute(
                    """
                    UPDATE tatkal_requests
                    SET status='REJECTED'
                    WHERE id=?
                    """,
                    (pending["id"],)
                )
                continue

            pending_source_idx = pending_route.index(
                pending["source"]
            )
            pending_destination_idx = pending_route.index(
                pending["destination"]
            )

            if pending_source_idx >= pending_destination_idx:
                con.execute(
                    """
                    UPDATE tatkal_requests
                    SET status='REJECTED'
                    WHERE id=?
                    """,
                    (pending["id"],)
                )

        # Reload valid waiting requests
        rows = con.execute(
            """
            SELECT * FROM tatkal_requests
            WHERE status='WAITING'
            ORDER BY id
            """
        ).fetchall()

        # Enforce FIFO rule
        if not can_process_request(rows, req_id):
            flash(
                "FIFO rule: process the earliest waiting request first.",
                "error"
            )
            return redirect(url_for("tatkal"))

        # Get selected Tatkal request
        tatkal_request = con.execute(
            """
            SELECT * FROM tatkal_requests
            WHERE id=? AND status='WAITING'
            """,
            (req_id,)
        ).fetchone()

        if tatkal_request is None:
            flash("Tatkal request not found.", "error")
            return redirect(url_for("tatkal"))

        # Get train details
        train = get_train(tatkal_request["train_id"])

        if train is None:
            flash("Train not found.", "error")
            return redirect(url_for("tatkal"))

        route = train.get("route", [])

        # Validate journey route
        if (
            tatkal_request["source"] not in route
            or tatkal_request["destination"] not in route
        ):
            flash("Selected stations are not on this train route.", "error")
            return redirect(url_for("tatkal"))

        source_idx = route.index(tatkal_request["source"])
        destination_idx = route.index(tatkal_request["destination"])

        if source_idx >= destination_idx:
            flash("Invalid Tatkal journey route.", "error")
            return redirect(url_for("tatkal"))

        # Get confirmed bookings for this train and date
        bookings = con.execute(
            """
            SELECT * FROM bookings
            WHERE train_id=?
            AND journey_date=?
            AND status='CONFIRMED'
            ORDER BY id
            """,
            (
                tatkal_request["train_id"],
                tatkal_request["journey_date"]
            )
        ).fetchall()

        # Find an available Tatkal seat
        seat = find_continuous_seat(
            bookings,
            source_idx,
            destination_idx,
            TATKAL_SEAT_COUNT,
            first_seat=RESERVED_SEAT_COUNT + 1
        )

        if seat is None:
            flash(
                "No seat available. Request remains waiting.",
                "error"
            )
            return redirect(url_for("tatkal"))

        # Generate PNR
        pnr = "TATKAL" + str(req_id).zfill(6)

        # Create confirmed booking
        con.execute(
            """
            INSERT INTO bookings (
                pnr,
                passenger_name,
                train_id,
                train_name,
                journey_date,
                source,
                destination,
                source_idx,
                destination_idx,
                coach,
                seat_no,
                booking_type,
                status,
                gap_start,
                gap_hours,
                created_at,
                user_id
            )
            VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, 'S1', ?,
                'Tatkal', 'CONFIRMED', NULL, 0, ?, ?
            )
            """,
            (
                pnr,
                tatkal_request["passenger_name"],
                tatkal_request["train_id"],
                train["name"],
                tatkal_request["journey_date"],
                tatkal_request["source"],
                tatkal_request["destination"],
                source_idx,
                destination_idx,
                seat,
                datetime.now().isoformat(timespec="seconds"),
                tatkal_request["user_id"]
            )
        )

        # Update Tatkal request status
        con.execute(
            """
            UPDATE tatkal_requests
            SET status='PROCESSED'
            WHERE id=?
            """,
            (req_id,)
        )

        flash(
            f"Tatkal booking confirmed! PNR: {pnr}, Seat: S1-{seat}",
            "success"
        )

    return redirect(url_for("bookings"))


@app.route("/dashboard")
@login_required
def dashboard():
    if current_user.role != "admin":
        flash("Access denied. Admin only.", "error")
        return redirect(url_for("index"))
    with get_connection() as con:
        total = con.execute(
            "SELECT COUNT(*) FROM bookings"
        ).fetchone()[0]

        confirmed = con.execute(
            "SELECT COUNT(*) FROM bookings WHERE status='CONFIRMED'"
        ).fetchone()[0]

        cancelled = con.execute(
            "SELECT COUNT(*) FROM bookings WHERE status='CANCELLED'"
        ).fetchone()[0]

        gap_count = con.execute(
            """
            SELECT COUNT(*) FROM bookings
            WHERE booking_type='Multi-Leg Gap'
            AND status='CONFIRMED'
            """
        ).fetchone()[0]

        by_train = con.execute(
            """
            SELECT train_name, COUNT(*) AS total
            FROM bookings
            WHERE status='CONFIRMED'
            GROUP BY train_name
            """
        ).fetchall()

        booking_types = con.execute(
            """
            SELECT booking_type, COUNT(*) AS total
            FROM bookings
            WHERE status='CONFIRMED'
            GROUP BY booking_type
            """
        ).fetchall()

    chart_labels = [row["booking_type"] for row in booking_types]
    chart_counts = [row["total"] for row in booking_types]

    return render_template(
        "dashboard.html",
        total=total,
        confirmed=confirmed,
        cancelled=cancelled,
        gap_count=gap_count,
        by_train=by_train,
        chart_labels=chart_labels,
        chart_counts=chart_counts
    )
@app.route("/test-railway-data")
@login_required
def test_railway_data():
    stations, trains = load_railway_data()

    return {
        "total_stations": len(stations),
        "total_trains": len(trains),
        "sample_train": trains[0] if trains else None
    }

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
