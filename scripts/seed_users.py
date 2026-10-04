"""Database initialization and fixed 3-user seeding script.

Creates database tables and ensures the 3 fixed users exist with bcrypt hashed passwords.
Names and credentials can be customized via .env environment variables:
- PERSON_1_NAME, PERSON_1_USERNAME, PERSON_1_PASSWORD
- PERSON_2_NAME, PERSON_2_USERNAME, PERSON_2_PASSWORD
- PERSON_3_NAME, PERSON_3_USERNAME, PERSON_3_PASSWORD

Usage:
    python scripts/seed_users.py
    python scripts/seed_users.py --reset-passwords
"""

import os
import sys
import argparse
from pathlib import Path

# Add project root to sys.path so imports work seamlessly
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from database.connection import init_db, get_db, check_connection
from database.models import User
from auth.auth import hash_password
from sqlalchemy import select


def get_configured_users():
    """Retrieve 3 user configurations from environment or sensible defaults."""
    return [
        {
            "id": 1,
            "name": os.getenv("PERSON_1_NAME", "Person 1").strip(),
            "username": os.getenv("PERSON_1_USERNAME", "person1").strip().lower(),
            "password": os.getenv("PERSON_1_PASSWORD", "password123"),
        },
        {
            "id": 2,
            "name": os.getenv("PERSON_2_NAME", "Person 2").strip(),
            "username": os.getenv("PERSON_2_USERNAME", "person2").strip().lower(),
            "password": os.getenv("PERSON_2_PASSWORD", "password123"),
        },
        {
            "id": 3,
            "name": os.getenv("PERSON_3_NAME", "Person 3").strip(),
            "username": os.getenv("PERSON_3_USERNAME", "person3").strip().lower(),
            "password": os.getenv("PERSON_3_PASSWORD", "password123"),
        },
    ]


def seed_database(reset_passwords: bool = False):
    """Create tables and ensure the 3 fixed users are seeded properly."""
    print("Checking database connection...")
    ok, msg = check_connection()
    if not ok:
        print(f"Error connecting to database: {msg}")
        print("Please check your DATABASE_URL in .env and ensure PostgreSQL is running.")
        sys.exit(1)

    print("Database reachable. Initializing tables...")
    init_db()

    configured_users = get_configured_users()

    with get_db() as session:
        existing_users = list(session.execute(select(User).order_by(User.id)).scalars().all())

        if not existing_users:
            print("No users found. Creating the 3 fixed users...")
            for u_data in configured_users:
                hashed = hash_password(u_data["password"])
                user = User(
                    name=u_data["name"],
                    username=u_data["username"],
                    password_hash=hashed,
                )
                session.add(user)
            session.commit()
            print("Successfully created 3 users:")
            for u in configured_users:
                print(f"  - {u['name']} (username: '{u['username']}')")
        else:
            print(f"Found {len(existing_users)} existing user(s). Syncing names...")
            for i, user in enumerate(existing_users[:3]):
                target_cfg = configured_users[i]
                if user.name != target_cfg["name"]:
                    print(f"  Updating user {user.id} name: '{user.name}' -> '{target_cfg['name']}'")
                    user.name = target_cfg["name"]
                if user.username != target_cfg["username"]:
                    print(f"  Updating user {user.id} username: '{user.username}' -> '{target_cfg['username']}'")
                    user.username = target_cfg["username"]
                if reset_passwords:
                    print(f"  Resetting password for user {user.username}...")
                    user.password_hash = hash_password(target_cfg["password"])

            session.commit()
            print("User synchronization complete.")

    print("\nDatabase initialization complete! You can now launch the application.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Seed database and fixed users.")
    parser.add_argument(
        "--reset-passwords",
        action="store_true",
        help="Update existing users' passwords from environment variables",
    )
    args = parser.parse_args()
    seed_database(reset_passwords=args.reset_passwords)
