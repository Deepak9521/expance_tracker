"""Unit tests for the settlement algorithm.

Verifies:
- Minimum practical settlement transactions.
- Exact debtor-to-creditor matching.
- Section 18 example (Person 1: +1000, Person 2: -500, Person 3: -500).
- Section 24 acceptance test (Person 1: +500, Person 2: -100, Person 3: -400).
- Two creditors and one debtor.
- Zero balances (settled).
- Rounding tolerance.
"""

from decimal import Decimal
import pytest
from services.settlement import calculate_settlement, SettlementInstruction


def test_settlement_section_18_example():
    """Balances:

    Person 1 = +1000
    Person 2 = -500
    Person 3 = -500
    Expected:
    Person 2 -> Person 1 = 500
    Person 3 -> Person 1 = 500
    """
    balances = [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("1000.00")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("-500.00")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("-500.00")},
    ]

    instructions = calculate_settlement(balances)
    assert len(instructions) == 2

    # Verify both transactions pay Person 1 500 each
    trans_map = {(tx.from_user_name, tx.to_user_name): tx.amount for tx in instructions}
    assert trans_map[("Person 2", "Person 1")] == Decimal("500.00")
    assert trans_map[("Person 3", "Person 1")] == Decimal("500.00")

    total_debtor_paid = sum(tx.amount for tx in instructions)
    assert total_debtor_paid == Decimal("1000.00")


def test_final_acceptance_test_scenario():
    """Section 24 Acceptance Test Scenario:

    Person 1 pays ₹900 + ₹300 = ₹1,200
    Person 2 pays ₹600
    Person 3 pays ₹300
    Total: ₹2,100
    Fair share: ₹700 per person
    Balances:
    Person 1: Paid ₹1,200, Share ₹700, Balance +₹500
    Person 2: Paid ₹600, Share ₹700, Balance -₹100
    Person 3: Paid ₹300, Share ₹700, Balance -₹400
    Expected settlement:
    Person 2 -> Person 1 ₹100
    Person 3 -> Person 1 ₹400
    """
    balances = [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("500.00")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("-100.00")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("-400.00")},
    ]

    instructions = calculate_settlement(balances)
    assert len(instructions) == 2

    trans_map = {(tx.from_user_name, tx.to_user_name): tx.amount for tx in instructions}
    assert trans_map[("Person 2", "Person 1")] == Decimal("100.00")
    assert trans_map[("Person 3", "Person 1")] == Decimal("400.00")

    total_paid = sum(tx.amount for tx in instructions)
    assert total_paid == Decimal("500.00")


def test_two_creditors_one_debtor():
    """Balances:

    Person 1 = +400
    Person 2 = +100
    Person 3 = -500
    Expected:
    Person 3 -> Person 1 ₹400
    Person 3 -> Person 2 ₹100
    """
    balances = [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("400.00")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("100.00")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("-500.00")},
    ]

    instructions = calculate_settlement(balances)
    assert len(instructions) == 2

    trans_map = {(tx.from_user_name, tx.to_user_name): tx.amount for tx in instructions}
    assert trans_map[("Person 3", "Person 1")] == Decimal("400.00")
    assert trans_map[("Person 3", "Person 2")] == Decimal("100.00")

    total_paid = sum(tx.amount for tx in instructions)
    assert total_paid == Decimal("500.00")


def test_all_balances_zero_no_transactions():
    """When everyone has balance 0, no transactions should be recommended."""
    balances = [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("0.00")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("0.00")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("0.00")},
    ]
    instructions = calculate_settlement(balances)
    assert len(instructions) == 0


def test_settlement_with_penny_rounding_difference():
    """Test when sum of balances has slight 1-cent difference due to 3-way split:

    e.g. Total = 100
    Fair share = 33.33 each
    Person 1 paid 100 -> balance +66.67
    Person 2 paid 0 -> balance -33.33
    Person 3 paid 0 -> balance -33.33
    Sum debtors = 66.66, Creditor = 66.67.
    """
    balances = [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("66.67")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("-33.33")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("-33.33")},
    ]
    instructions = calculate_settlement(balances)
    assert len(instructions) == 2
    total_paid = sum(tx.amount for tx in instructions)
    assert total_paid == Decimal("66.67")
