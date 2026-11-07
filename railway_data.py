
import csv
import os
from collections import defaultdict

# This file is in the same folder as trains.csv and stops.csv.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))


DATA_DIR = os.path.join(BASE_DIR, "data", "railway")

TRAINS_FILE = os.path.join(DATA_DIR, "trains.csv")
STOPS_FILE = os.path.join(DATA_DIR, "stops.csv")


def load_railway_data():
    """
    Load train and stop information from CSV files.

    Returns:
        stations: list of station names
        trains: list of trains with ordered station routes
    """

    if not os.path.exists(TRAINS_FILE):
        raise FileNotFoundError(
            f"Missing file: {TRAINS_FILE}"
        )

    if not os.path.exists(STOPS_FILE):
        raise FileNotFoundError(
            f"Missing file: {STOPS_FILE}"
        )

    # Read station stops for each train.
    stops_by_train = defaultdict(list)

    with open(
        STOPS_FILE, "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required_columns = {
            "train_number",
            "seq",
            "station_name",
        }

        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"stops.csv missing columns: {sorted(missing)}"
            )

        for row in reader:
            number = row["train_number"].strip()
            digits = "".join(ch for ch in number if ch.isdigit())
            number = str(int(digits)) if digits else ""

            try:
                sequence = int(row["seq"])
            except (ValueError, TypeError):
                continue

            station_name = row["station_name"].strip()
            if not number or not station_name:
                continue

            stops_by_train[number].append({
                "seq": sequence,
                "name": station_name,
                "code": row.get("station_code", "").strip(),
                "arrival": row.get("arrival", "").strip(),
                "departure": row.get("departure", "").strip(),
                "day": row.get("day", "").strip(),
            })

    # Read train details and build the route in stop order.
    trains = []
    stations_seen = set()

    with open(
        TRAINS_FILE, "r", encoding="utf-8-sig", newline=""
    ) as file:
        reader = csv.DictReader(file)

        required_columns = {
            "number",
            "name",
            "source",
            "destination",
        }

        missing = required_columns - set(reader.fieldnames or [])
        if missing:
            raise ValueError(
                f"trains.csv missing columns: {sorted(missing)}"
            )

        for row in reader:
            number = row["number"].strip()
            name = row["name"].strip()

            # Stops file may contain numbers such as 81,
            # while the train file may use 00081.
            digits = "".join(ch for ch in number if ch.isdigit())
            if not digits:
                continue

            normalized_number = str(int(digits))
            stop_rows = stops_by_train.get(normalized_number, [])

            if not stop_rows:
                stop_rows = stops_by_train.get(
                    digits.lstrip("0") or "0", []
                )

            stop_rows = sorted(
                stop_rows, key=lambda stop: stop["seq"]
            )

            route = []
            seen_in_route = set()

            for stop in stop_rows:
                station = stop["name"]

                # Avoid duplicate consecutive/repeated station entries.
                if station not in seen_in_route:
                    route.append(station)
                    seen_in_route.add(station)
                    stations_seen.add(station)

            # Ensure source and destination are available in the route.
            source = row["source"].strip()
            destination = row["destination"].strip()

            if source and source not in seen_in_route:
                route.insert(0, source)
                stations_seen.add(source)

            if destination and destination not in seen_in_route:
                route.append(destination)
                stations_seen.add(destination)

            if len(route) < 2:
                continue

            trains.append({
                "id": number,
                "number": number,
                "name": name,
                "source": source,
                "destination": destination,
                "route": route,
                "runs_days": row.get("runs_days", "").strip(),
                "type": row.get("type_label", row.get("type", "")).strip(),
                "distance_km": row.get("distance_km", "").strip(),
                "travel_time": row.get("travel_time", "").strip(),
                "num_stops": row.get("num_stops", "").strip(),
            })

    stations = sorted(stations_seen)
    return stations, trains




if __name__ == "__main__":
    import csv
    from collections import Counter

    stops_file = os.path.join(DATA_DIR, "stops.csv")

    with open(
        TRAINS_FILE, "r", encoding="utf-8-sig", newline=""
    ) as f:
        train_rows = list(csv.DictReader(f))

    with open(
        stops_file, "r", encoding="utf-8-sig", newline=""
    ) as f:
        stop_rows = list(csv.DictReader(f))

    print("Train CSV rows:", len(train_rows))
    print("Stops CSV rows:", len(stop_rows))
    print("Stops CSV columns:", list(stop_rows[0].keys()) if stop_rows else [])

    stop_counts = Counter(
        row.get("train_number", "").strip().lstrip("0") or "0"
        for row in stop_rows
    )

    print("\nSample train number matches:")
    for row in train_rows[:10]:
        number = row.get("number", "").strip()
        normalized = number.lstrip("0") or "0"
        print(
            number,
            row.get("name", ""),
            "-> stop records:",
            stop_counts.get(normalized, 0)
        )

    print("\nSample stop rows for train 81:")
    for row in stop_rows:
        number = row.get("train_number", "").strip().lstrip("0") or "0"
        if number == "81":
            print(row)
            if row.get("seq", "").strip() == "5":
                break



