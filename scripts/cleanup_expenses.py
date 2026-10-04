"""Script to safely clean up individual expense records older than 60 days.

Ensures that weekly summaries are created before expenses are purged,
guaranteeing no loss of financial historical data.

Usage:
    python scripts/cleanup_expenses.py
    python scripts/cleanup_expenses.py --dry-run
"""

import sys
import argparse
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from database.connection import get_db, check_connection
from services.expenses import delete_expenses_older_than_60_days


def main():
    parser = argparse.ArgumentParser(description="Clean up expenses older than 60 days.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate cleanup without deleting any records",
    )
    args = parser.parse_args()

    ok, msg = check_connection()
    if not ok:
        print(f"Error connecting to database: {msg}")
        sys.exit(1)

    with get_db() as session:
        result = delete_expenses_older_than_60_days(session, dry_run=args.dry_run)

    mode = "[DRY-RUN] " if result["dry_run"] else ""
    print(f"{mode}Cleanup Results:")
    print(f"  - Cutoff Date: {result['cutoff_date']}")
    print(f"  - Archived Weeks: {result['archived_weeks']}")
    print(f"  - Expenses Deleted: {result['deleted_count']}")


if __name__ == "__main__":
    main()
