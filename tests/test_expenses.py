"""Unit and integration tests for expense operations, authorization, and closed week rules."""

from datetime import date, timedelta
from decimal import Decimal
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from database.models import Base, User, Expense, WeeklySummary
from services.expenses import (
    create_expense,
    get_expenses,
    update_expense,
    delete_expense,
    close_and_save_week,
    is_week_closed,
    get_week_bounds,
    delete_expenses_older_than_60_days,
)


@pytest.fixture
def db_session():
    """Create a fresh in-memory SQLite database session for testing."""
    test_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=test_engine)
    TestingSession = sessionmaker(bind=test_engine)
    session = TestingSession()

    # Seed 3 users
    u1 = User(id=1, name="Person 1", username="person1", password_hash="hash1")
    u2 = User(id=2, name="Person 2", username="person2", password_hash="hash2")
    u3 = User(id=3, name="Person 3", username="person3", password_hash="hash3")
    session.add_all([u1, u2, u3])
    session.commit()

    yield session
    session.close()


def test_create_expense_valid(db_session):
    """Test valid expense creation."""
    today = date(2026, 10, 4)
    exp = create_expense(
        description="Groceries",
        amount=Decimal("900.00"),
        category="Groceries",
        paid_by=1,
        expense_date=today,
        session=db_session,
    )
    db_session.commit()

    assert exp.id is not None
    assert exp.description == "Groceries"
    assert exp.amount == Decimal("900.00")
    assert exp.paid_by == 1


def test_create_expense_validation_errors(db_session):
    """Test validation fails on invalid inputs."""
    today = date(2026, 10, 4)

    # Empty description
    with pytest.raises(ValueError, match="Description cannot be empty"):
        create_expense("", 100, "Food", 1, today, db_session)

    # Negative / zero amount
    with pytest.raises(ValueError, match="Amount must be greater than 0"):
        create_expense("Lunch", 0, "Food", 1, today, db_session)

    with pytest.raises(ValueError, match="Amount must be greater than 0"):
        create_expense("Lunch", -50, "Food", 1, today, db_session)

    # Invalid category
    with pytest.raises(ValueError, match="Category 'InvalidCat' is invalid"):
        create_expense("Lunch", 100, "InvalidCat", 1, today, db_session)

    # Non-existent user
    with pytest.raises(ValueError, match="User with ID 999 does not exist"):
        create_expense("Lunch", 100, "Food", 999, today, db_session)


def test_edit_delete_authorization(db_session):
    """Test user can ONLY edit/delete expenses they personally paid for."""
    today = date(2026, 10, 4)
    exp = create_expense("Dinner", 600, "Food", paid_by=1, expense_date=today, session=db_session)
    db_session.commit()

    # User 2 tries to edit User 1's expense -> PermissionError
    with pytest.raises(PermissionError, match="personally paid for"):
        update_expense(
            expense_id=exp.id,
            acting_user_id=2,
            description="Modified Dinner",
            amount=600,
            category="Food",
            paid_by=1,
            expense_date=today,
            session=db_session,
        )

    # User 2 tries to delete User 1's expense -> PermissionError
    with pytest.raises(PermissionError, match="personally paid for"):
        delete_expense(expense_id=exp.id, acting_user_id=2, session=db_session)

    # User 1 successfully edits
    updated = update_expense(
        expense_id=exp.id,
        acting_user_id=1,
        description="Modified Dinner",
        amount=750,
        category="Food",
        paid_by=1,
        expense_date=today,
        session=db_session,
    )
    db_session.commit()
    assert updated.description == "Modified Dinner"
    assert updated.amount == Decimal("750.00")

    # User 1 successfully deletes
    deleted = delete_expense(expense_id=exp.id, acting_user_id=1, session=db_session)
    db_session.commit()
    assert deleted is True


def test_closed_week_prevents_modification_and_duplicates(db_session):
    """Test closing a week prevents additions, edits, deletions, and duplicate closures."""
    exp_date = date(2026, 9, 15)  # A Tuesday
    w_start, w_end = get_week_bounds(exp_date)

    exp = create_expense("Internet Bill", 1200, "Internet", paid_by=2, expense_date=exp_date, session=db_session)
    db_session.commit()

    # Close the week
    summary = close_and_save_week(w_start, w_end, session=db_session)
    db_session.commit()
    assert summary.id is not None
    assert summary.total_expenses == Decimal("1200.00")
    assert summary.person_2_paid == Decimal("1200.00")
    assert summary.person_2_share == Decimal("400.00")

    # Trying to close the same week again must fail
    with pytest.raises(ValueError, match="already closed"):
        close_and_save_week(w_start, w_end, session=db_session)

    # Trying to add an expense to this closed week must fail
    with pytest.raises(ValueError, match="already closed"):
        create_expense("Late Snack", 50, "Food", paid_by=1, expense_date=exp_date, session=db_session)

    # Trying to edit an existing expense in this closed week must fail
    with pytest.raises(ValueError, match="closed"):
        update_expense(
            expense_id=exp.id,
            acting_user_id=2,
            description="Changed Internet",
            amount=1500,
            category="Internet",
            paid_by=2,
            expense_date=exp_date,
            session=db_session,
        )

    # Trying to delete an existing expense in this closed week must fail
    with pytest.raises(ValueError, match="closed"):
        delete_expense(expense_id=exp.id, acting_user_id=2, session=db_session)


def test_60_day_retention_cleanup(db_session):
    """Test cleanup of expenses older than 60 days archives weeks before deleting."""
    old_date = date.today() - timedelta(days=70)
    w_start, w_end = get_week_bounds(old_date)

    create_expense("Old Expense", 300, "Food", paid_by=3, expense_date=old_date, session=db_session)
    db_session.commit()

    # Clean up
    res = delete_expenses_older_than_60_days(db_session, dry_run=False)
    db_session.commit()

    assert res["deleted_count"] == 1
    assert res["archived_weeks"] == 1

    # Verify expense is deleted
    remaining = get_expenses(session=db_session)
    assert len(remaining) == 0

    # Verify weekly summary was safely archived
    closed, summary = is_week_closed(old_date, db_session)
    assert closed is True
    assert summary.total_expenses == Decimal("300.00")
