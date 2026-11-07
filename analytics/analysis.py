"""Export bookings to CSV and create a small analytics summary/chart."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import csv
from pathlib import Path
from database import get_connection

OUT = Path(__file__).with_name("bookings_export.csv")

def export_bookings():
    with get_connection() as con:
        rows = con.execute("""
            SELECT pnr, passenger_name, train_id, train_name, journey_date,
                   source, destination, coach, seat_no, booking_type, status,
                   created_at
            FROM bookings ORDER BY id
        """).fetchall()
    with OUT.open("w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(rows[0].keys() if rows else [
            "pnr", "passenger_name", "train_id", "train_name", "journey_date",
            "source", "destination", "coach", "seat_no", "booking_type", "status", "created_at"
        ])
        writer.writerows([tuple(row) for row in rows])
    return OUT

def main():
    path = export_bookings()
    print(f"CSV exported to: {path}")
    try:
        import pandas as pd
        import matplotlib.pyplot as plt
        df = pd.read_csv(path)
        if df.empty:
            print("No booking data yet. Create bookings in the website first.")
            return
        print("\nBookings by status:")
        print(df.groupby("status").size().to_string())
        print("\nBookings by type:")
        print(df.groupby("booking_type").size().to_string())
        df.groupby("booking_type").size().plot(kind="bar", title="Bookings by Type")
        plt.xlabel("Booking Type")
        plt.ylabel("Number of bookings")
        plt.tight_layout()
        chart_path = Path(__file__).with_name("booking_types_chart.png")
        plt.savefig(chart_path)
        print(f"Chart saved to: {chart_path}")
    except ImportError:
        print("Install pandas and matplotlib to generate analytics: pip install pandas matplotlib")

if __name__ == "__main__":
    main()
