"""SQLite setup and basic data access."""
import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).with_name("train_booking.db")

def get_connection():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con

def init_db():
    with get_connection() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS bookings (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            pnr TEXT UNIQUE NOT NULL,
            passenger_name TEXT NOT NULL,
            train_id TEXT NOT NULL,
            train_name TEXT NOT NULL,
            journey_date TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            source_idx INTEGER NOT NULL,
            destination_idx INTEGER NOT NULL,
            coach TEXT NOT NULL DEFAULT 'S1',
            seat_no INTEGER NOT NULL,
            booking_type TEXT NOT NULL DEFAULT 'Normal',
            status TEXT NOT NULL DEFAULT 'CONFIRMED',
            gap_start TEXT,
            gap_hours REAL NOT NULL DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """)

        
        # Separate Reserved and Tatkal quotas for each train and journey date.
        con.execute("""
        CREATE TABLE IF NOT EXISTS train_quotas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            train_id TEXT NOT NULL,
            journey_date TEXT NOT NULL,
            reserved_quota INTEGER NOT NULL DEFAULT 18,
            tatkal_quota INTEGER NOT NULL DEFAULT 6,
            created_at TEXT NOT NULL,
            UNIQUE(train_id, journey_date),
            CHECK(reserved_quota >= 0),
            CHECK(tatkal_quota >= 0)
        )
        """)

        con.execute("""
        CREATE TABLE IF NOT EXISTS tatkal_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            passenger_name TEXT NOT NULL,
            train_id TEXT NOT NULL,
            journey_date TEXT NOT NULL,
            source TEXT NOT NULL,
            destination TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'WAITING',
            created_at TEXT NOT NULL
        )
        """)
        
        con.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT NOT NULL DEFAULT 'user',
            created_at TEXT NOT NULL
        )
        """)

                # Safely add user ownership to existing bookings.
        booking_columns = {
            row["name"]
            for row in con.execute("PRAGMA table_info(bookings)").fetchall()
        }

        if "user_id" not in booking_columns:
            con.execute(
                "ALTER TABLE bookings ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )

        # Safely add user ownership to existing Tatkal requests.
        tatkal_columns = {
            row["name"]
            for row in con.execute("PRAGMA table_info(tatkal_requests)").fetchall()
        }

        if "user_id" not in tatkal_columns:
            con.execute(
                "ALTER TABLE tatkal_requests ADD COLUMN user_id INTEGER REFERENCES users(id)"
            )



