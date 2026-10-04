"""Expense operations, validation, weekly summary archiving, and retention management."""

from datetime import date, timedelta
from decimal import Decimal
from typing import List, Optional, Tuple, Dict, Any
from sqlalchemy import select, and_, delete as sa_delete
from sqlalchemy.orm import Session, joinedload
from database.models import Expense, WeeklySummary, User
from services.calculations import (
    to_decimal,
    calculate_total_expenses,
    calculate_fair_share,
    calculate_user_paid,
)

VALID_CATEGORIES = [
    "Food",
    "Groceries",
    "Electricity",
    "Internet",
    "Rent",
    "Transport",
    "Household",
    "Entertainment",
    "Other",
]


def get_week_bounds(target_date: date) -> Tuple[date, date]:
    """Return (Monday, Sunday) bounds for the week containing target_date."""
    start = target_date - timedelta(days=target_date.weekday())
    end = start + timedelta(days=6)
    return start, end


def is_week_closed(check_date: date, session: Session) -> Tuple[bool, Optional[WeeklySummary]]:
    """Check if the week covering check_date has already been closed and saved.

    Returns (True, WeeklySummary) if closed, (False, None) otherwise.
    """
    stmt = select(WeeklySummary).where(
        and_(
            WeeklySummary.week_start <= check_date,
            WeeklySummary.week_end >= check_date,
        )
    )
    summary = session.execute(stmt).scalar_one_or_none()
    return (summary is not None, summary)


def create_expense(
    description: str,
    amount: Any,
    category: str,
    paid_by: int,
    expense_date: date,
    session: Session,
) -> Expense:
    """Validate and insert a new shared expense."""
    # Validation 1: Description
    clean_desc = (description or "").strip()
    if not clean_desc:
        raise ValueError("Description cannot be empty.")

    # Validation 2: Amount
    dec_amount = to_decimal(amount)
    if dec_amount <= Decimal("0.00"):
        raise ValueError("Amount must be greater than 0.")

    # Validation 3: Category
    if category not in VALID_CATEGORIES:
        raise ValueError(f"Category '{category}' is invalid. Allowed: {', '.join(VALID_CATEGORIES)}")

    # Validation 4: Date
    if not isinstance(expense_date, date):
        raise ValueError("Invalid date provided.")

    # Validation 5: Week must not be closed
    closed, summary = is_week_closed(expense_date, session)
    if closed and summary:
        raise ValueError(
            f"Cannot add expense: The week from {summary.week_start} to {summary.week_end} is already closed."
        )

    # Validation 6: Paid By must exist
    payer = session.get(User, paid_by)
    if not payer:
        raise ValueError(f"User with ID {paid_by} does not exist.")

    expense = Expense(
        description=clean_desc,
        amount=dec_amount,
        category=category,
        paid_by=paid_by,
        expense_date=expense_date,
    )
    session.add(expense)
    session.flush()
    return expense


def get_expenses(
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
    user_id: Optional[int] = None,
    category: Optional[str] = None,
    session: Optional[Session] = None,
) -> List[Expense]:
    """Retrieve filtered expenses ordered by date descending, then ID descending."""
    if session is None:
        raise ValueError("Active database session required.")

    query = select(Expense).options(joinedload(Expense.payer))
    conditions = []

    if start_date:
        conditions.append(Expense.expense_date >= start_date)
    if end_date:
        conditions.append(Expense.expense_date <= end_date)
    if user_id:
        conditions.append(Expense.paid_by == user_id)
    if category and category != "All":
        conditions.append(Expense.category == category)

    if conditions:
        query = query.where(and_(*conditions))

    query = query.order_by(Expense.expense_date.desc(), Expense.id.desc())
    return list(session.execute(query).scalars().all())


def get_expense_by_id(expense_id: int, session: Session) -> Optional[Expense]:
    """Fetch single expense by ID."""
    return session.get(Expense, expense_id)


def update_expense(
    expense_id: int,
    acting_user_id: int,
    description: str,
    amount: Any,
    category: str,
    paid_by: int,
    expense_date: date,
    session: Session,
) -> Expense:
    """Update an existing expense.

    Rule: Only the user who paid for the expense can edit it.
    Rule: Cannot edit if expense belongs to an already closed week.
    """
    expense = get_expense_by_id(expense_id, session)
    if not expense:
        raise ValueError(f"Expense with ID {expense_id} not found.")

    # Authorization check
    if expense.paid_by != acting_user_id:
        raise PermissionError("You can only edit expenses that you personally paid for.")

    # Closed week check on original date
    closed, summary = is_week_closed(expense.expense_date, session)
    if closed and summary:
        raise ValueError(
            f"Cannot modify expense: The original week ({summary.week_start} to {summary.week_end}) is closed."
        )

    # Closed week check on new date
    closed_new, summary_new = is_week_closed(expense_date, session)
    if closed_new and summary_new:
        raise ValueError(
            f"Cannot move expense: The target week ({summary_new.week_start} to {summary_new.week_end}) is closed."
        )

    # Validate inputs
    clean_desc = (description or "").strip()
    if not clean_desc:
        raise ValueError("Description cannot be empty.")

    dec_amount = to_decimal(amount)
    if dec_amount <= Decimal("0.00"):
        raise ValueError("Amount must be greater than 0.")

    if category not in VALID_CATEGORIES:
        raise ValueError(f"Category '{category}' is invalid.")

    # Payer check
    payer = session.get(User, paid_by)
    if not payer:
        raise ValueError(f"User with ID {paid_by} does not exist.")

    expense.description = clean_desc
    expense.amount = dec_amount
    expense.category = category
    expense.paid_by = paid_by
    expense.expense_date = expense_date

    session.flush()
    return expense


def delete_expense(expense_id: int, acting_user_id: int, session: Session) -> bool:
    """Delete an existing expense.

    Rule: Only the user who paid for the expense can delete it.
    Rule: Cannot delete if expense belongs to an already closed week.
    """
    expense = get_expense_by_id(expense_id, session)
    if not expense:
        raise ValueError(f"Expense with ID {expense_id} not found.")

    if expense.paid_by != acting_user_id:
        raise PermissionError("You can only delete expenses that you personally paid for.")

    closed, summary = is_week_closed(expense.expense_date, session)
    if closed and summary:
        raise ValueError(
            f"Cannot delete expense: The week ({summary.week_start} to {summary.week_end}) is closed."
        )

    session.delete(expense)
    session.flush()
    return True


def close_and_save_week(week_start: date, week_end: date, session: Session) -> WeeklySummary:
    """Explicitly close and save a weekly summary.

    1. Calculates final weekly totals.
    2. Saves weekly summary.
    3. Prevents duplicate summaries for the same week.
    4. Prevents further modifications to expenses in that week.
    """
    # Check if already closed
    stmt = select(WeeklySummary).where(
        and_(WeeklySummary.week_start == week_start, WeeklySummary.week_end == week_end)
    )
    existing = session.execute(stmt).scalar_one_or_none()
    if existing:
        raise ValueError(f"Week from {week_start} to {week_end} is already closed and saved.")

    # Fetch users
    users = list(session.execute(select(User).order_by(User.id)).scalars().all())
    if len(users) < 3:
        raise ValueError("Cannot close week: Exactly 3 users must be registered in the system.")

    # Fetch expenses for the week
    expenses = get_expenses(start_date=week_start, end_date=week_end, session=session)

    total = calculate_total_expenses(e.amount for e in expenses)
    fair_share = calculate_fair_share(total, num_people=3)

    p1_paid = calculate_user_paid(expenses, users[0].id)
    p2_paid = calculate_user_paid(expenses, users[1].id)
    p3_paid = calculate_user_paid(expenses, users[2].id)

    summary = WeeklySummary(
        week_start=week_start,
        week_end=week_end,
        total_expenses=total,
        person_1_paid=p1_paid,
        person_2_paid=p2_paid,
        person_3_paid=p3_paid,
        person_1_share=fair_share,
        person_2_share=fair_share,
        person_3_share=fair_share,
    )
    session.add(summary)
    session.flush()
    return summary


def get_weekly_summaries(session: Session) -> List[WeeklySummary]:
    """Retrieve all saved weekly summaries ordered by week_start descending."""
    stmt = select(WeeklySummary).order_by(WeeklySummary.week_start.desc())
    return list(session.execute(stmt).scalars().all())


def delete_expenses_older_than_60_days(session: Session, dry_run: bool = False) -> Dict[str, Any]:
    """Safe cleanup of expense records older than approximately 60 days.

    Before deleting, ensures weekly summaries exist for all weeks covering those expenses
    so historical spending and totals are permanently preserved in WEEKLY_SUMMARIES.
    """
    cutoff_date = date.today() - timedelta(days=60)

    # Find candidate expenses
    stmt = select(Expense).where(Expense.expense_date < cutoff_date)
    candidates = list(session.execute(stmt).scalars().all())

    if not candidates:
        return {
            "deleted_count": 0,
            "cutoff_date": cutoff_date,
            "archived_weeks": 0,
            "dry_run": dry_run,
        }

    # Group candidate expenses by week to ensure summaries exist
    weeks_to_check = set()
    for exp in candidates:
        w_start, w_end = get_week_bounds(exp.expense_date)
        weeks_to_check.add((w_start, w_end))

    archived_weeks_count = 0
    for w_start, w_end in sorted(list(weeks_to_check)):
        closed, _ = is_week_closed(w_start, session)
        if not closed:
            if not dry_run:
                close_and_save_week(w_start, w_end, session)
            archived_weeks_count += 1

    deleted_count = len(candidates)
    if not dry_run:
        del_stmt = sa_delete(Expense).where(Expense.expense_date < cutoff_date)
        session.execute(del_stmt)
        session.flush()

    return {
        "deleted_count": deleted_count,
        "cutoff_date": cutoff_date,
        "archived_weeks": archived_weeks_count,
        "dry_run": dry_run,
    }
