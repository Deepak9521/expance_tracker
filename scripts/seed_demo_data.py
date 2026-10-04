"""Seed acceptance test demo data (Section 24 Scenario).

Scenario:
- Person 1: pays ₹900 (Groceries) + ₹300 (Electricity) = ₹1,200
- Person 2: pays ₹600 (Food)
- Person 3: pays ₹300 (Transport)

Total: ₹2,100 | Fair Share: ₹700 each
Balances:
- Person 1: +₹500 (Receives)
- Person 2: -₹100 (Owes)
- Person 3: -₹400 (Owes)

Expected Settlement:
- Person 2 → Person 1 ₹100
- Person 3 → Person 1 ₹400
"""

import sys
from datetime import date, timedelta
from pathlib import Path
from decimal import Decimal

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from dotenv import load_dotenv
load_dotenv(PROJECT_ROOT / ".env")

from database.connection import get_db, check_connection
from database.models import User, Expense
from auth.auth import get_all_users
from services.expenses import create_expense, get_week_bounds, get_expenses
from services.calculations import calculate_period_summary, format_inr
from services.settlement import calculate_settlement
from scripts.seed_users import seed_database


def seed_demo():
    print("Checking database connection...")
    ok, msg = check_connection()
    if not ok:
        print(f"Error connecting: {msg}")
        sys.exit(1)

    # Ensure users and tables are created
    seed_database()

    today = date.today()
    w_start, w_end = get_week_bounds(today)

    with get_db() as session:
        users = get_all_users(session)
        if len(users) < 3:
            print("Error: 3 users required.")
            sys.exit(1)

        p1, p2, p3 = users[0], users[1], users[2]

        # Check existing expenses in this week
        existing = get_expenses(start_date=w_start, end_date=w_end, session=session)
        if existing:
            print(f"Notice: Found {len(existing)} existing expenses in current week ({w_start} to {w_end}).")
            print("Clearing existing expenses for clean acceptance test demo...")
            for e in existing:
                session.delete(e)
            session.commit()

        # Insert Section 24 Acceptance Scenario
        # 1. Person 1: ₹900 Groceries
        create_expense(
            description="Weekly Groceries",
            amount=Decimal("900.00"),
            category="Groceries",
            paid_by=p1.id,
            expense_date=w_start,
            session=session,
        )

        # 2. Person 1: ₹300 Electricity
        create_expense(
            description="Electricity Bill",
            amount=Decimal("300.00"),
            category="Electricity",
            paid_by=p1.id,
            expense_date=w_start + timedelta(days=1),
            session=session,
        )

        # 3. Person 2: ₹600 Food
        create_expense(
            description="Dinner with roommates",
            amount=Decimal("600.00"),
            category="Food",
            paid_by=p2.id,
            expense_date=w_start + timedelta(days=2),
            session=session,
        )

        # 4. Person 3: ₹300 Transport
        create_expense(
            description="Shared Cab Ride",
            amount=Decimal("300.00"),
            category="Transport",
            paid_by=p3.id,
            expense_date=w_start + timedelta(days=3),
            session=session,
        )

        session.commit()

        # Recalculate and display verification
        refreshed_expenses = get_expenses(start_date=w_start, end_date=w_end, session=session)
        summary = calculate_period_summary(refreshed_expenses, users)

        print("\n==================================================")
        print("DEMO DATA LOADED - ACCEPTANCE TEST VERIFICATION")
        print("==================================================")
        print(f"Week: {w_start} to {w_end}")
        print(f"Total Spending: {format_inr(summary['total_expenses'])}")
        print(f"Fair Share Per Person: {format_inr(summary['fair_share_per_person'])}")
        print("\nBalances:")
        bal_list = []
        for u_sum in summary["user_summaries"]:
            bal = u_sum["balance"]
            sign = "+" if bal > 0 else ""
            print(f"  {u_sum['name']}: Paid {format_inr(u_sum['paid'])}, Share {format_inr(u_sum['fair_share'])}, Balance {sign}{format_inr(bal)}")
            bal_list.append({"user_id": u_sum["user_id"], "name": u_sum["name"], "balance": bal})

        instructions = calculate_settlement(bal_list)
        print("\nCalculated Settlement Instructions:")
        for inst in instructions:
            print(f"  {inst.display_text}")
        print("==================================================\n")


if __name__ == "__main__":
    seed_demo()
