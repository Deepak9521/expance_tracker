"""Unit tests for the financial calculation engine.

Covers:
- Equal three-way splitting (e.g. 900 / 3 = 300)
- Balance calculation
- Person who paid more receives money
- Person who paid less owes money
- All three paid equally means all balances are zero
- Rounding behavior
- Indian Rupee currency formatting
"""

from decimal import Decimal
import pytest
from services.calculations import (
    to_decimal,
    calculate_total_expenses,
    calculate_fair_share,
    calculate_user_paid,
    calculate_user_balance,
    calculate_period_summary,
    format_inr,
)


def test_equal_three_way_splitting():
    """Test standard 3-way split: 900 / 3 = 300."""
    total = Decimal("900.00")
    share = calculate_fair_share(total, num_people=3)
    assert share == Decimal("300.00")


def test_balance_calculation_creditor():
    """Test person who paid more receives money (positive balance)."""
    paid = Decimal("900.00")
    share = Decimal("300.00")
    balance = calculate_user_balance(paid, share)
    assert balance == Decimal("600.00")
    assert balance > 0


def test_balance_calculation_debtor():
    """Test person who paid less owes money (negative balance)."""
    paid = Decimal("0.00")
    share = Decimal("300.00")
    balance = calculate_user_balance(paid, share)
    assert balance == Decimal("-300.00")
    assert balance < 0


def test_all_three_paid_equally_all_zero_balances():
    """Test all three paid equally means all balances are zero."""
    expenses = [
        {"paid_by": 1, "amount": Decimal("500.00")},
        {"paid_by": 2, "amount": Decimal("500.00")},
        {"paid_by": 3, "amount": Decimal("500.00")},
    ]
    users = [
        {"id": 1, "name": "Person 1"},
        {"id": 2, "name": "Person 2"},
        {"id": 3, "name": "Person 3"},
    ]

    summary = calculate_period_summary(expenses, users)
    assert summary["total_expenses"] == Decimal("1500.00")
    assert summary["fair_share_per_person"] == Decimal("500.00")

    for u_summary in summary["user_summaries"]:
        assert u_summary["paid"] == Decimal("500.00")
        assert u_summary["fair_share"] == Decimal("500.00")
        assert u_summary["balance"] == Decimal("0.00")


def test_rounding_behavior_non_divisible_by_three():
    """Test rounding to 2 decimal places when not evenly divisible."""
    total = Decimal("100.00")
    share = calculate_fair_share(total, num_people=3)
    # 100 / 3 = 33.3333... rounded to 2 decimal places = 33.33
    assert share == Decimal("33.33")

    total_2 = Decimal("10.00")
    share_2 = calculate_fair_share(total_2, num_people=3)
    assert share_2 == Decimal("3.33")

    total_3 = Decimal("0.01")
    share_3 = calculate_fair_share(total_3, num_people=3)
    assert share_3 == Decimal("0.00")


def test_to_decimal_safety():
    """Verify to_decimal handles floats, ints, strings, None safely."""
    assert to_decimal(10) == Decimal("10")
    assert to_decimal("25.50") == Decimal("25.50")
    assert to_decimal(None) == Decimal("0.00")
    assert to_decimal("invalid") == Decimal("0.00")


def test_indian_rupee_formatting():
    """Verify format_inr formats correctly with INR symbols and grouping."""
    assert format_inr(Decimal("1250.00")) == "₹1,250.00"
    assert format_inr(Decimal("900")) == "₹900.00"
    assert format_inr(Decimal("6000.00")) == "₹6,000.00"
    assert format_inr(Decimal("-500.00")) == "-₹500.00"
    assert format_inr(Decimal("0.00")) == "₹0.00"
    assert format_inr(Decimal("100000.00")) == "₹1,00,000.00"
