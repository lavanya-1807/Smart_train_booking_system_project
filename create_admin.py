from getpass import getpass
from datetime import datetime
from database import init_db, get_connection
from werkzeug.security import generate_password_hash


def create_admin():
    init_db()

    username = input("Enter admin username: ").strip()
    password = getpass("Enter admin password (minimum 8 characters): ")

    if len(username) < 3:
        print("Username must contain at least 3 characters.")
        return

    if len(password) < 8:
        print("Password must contain at least 8 characters.")
        return

    password_hash = generate_password_hash(password)

    try:
        with get_connection() as con:
            con.execute(
                """
                INSERT INTO users (username, password_hash, role, created_at)
                VALUES (?, ?, 'admin', ?)
                """,
                (
                    username,
                    password_hash,
                    datetime.now().isoformat(timespec="seconds")
                )
            )

        print("Admin account created successfully!")

    except Exception:
        print("Could not create admin. The username may already exist.")


if __name__ == "__main__":
    create_admin()