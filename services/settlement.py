"""Settlement calculation algorithm for the 3-person shared expense tracker.

Calculates the minimum practical settlement transactions among the 3 users.
Ensures:
- Total money paid by debtors equals total money received by creditors.
- No unnecessary transactions (for 3 people, at most 2 transactions).
- Balances are resolved within rounding tolerance.
"""

from decimal import Decimal, ROUND_HALF_UP
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from services.calculations import to_decimal, format_inr


@dataclass
class SettlementInstruction:
    """Represents a settlement payment recommendation between two users."""

    from_user_id: int
    from_user_name: str
    to_user_id: int
    to_user_name: str
    amount: Decimal

    @property
    def display_text(self) -> str:
        """Formatted human-readable instruction."""
        return f"{self.from_user_name} → {self.to_user_name} {format_inr(self.amount)}"

    def to_dict(self) -> Dict[str, Any]:
        """Convert instruction to a dictionary."""
        return {
            "from_user_id": self.from_user_id,
            "from_user_name": self.from_user_name,
            "to_user_id": self.to_user_id,
            "to_user_name": self.to_user_name,
            "amount": self.amount,
            "text": self.display_text,
        }


def calculate_settlement(user_balances: List[Dict[str, Any]]) -> List[SettlementInstruction]:
    """Calculate minimum settlement transactions from a list of user balance dicts.

    Input format:
    [
        {"user_id": 1, "name": "Person 1", "balance": Decimal("500.00")},
        {"user_id": 2, "name": "Person 2", "balance": Decimal("-100.00")},
        {"user_id": 3, "name": "Person 3", "balance": Decimal("-400.00")}
    ]

    Returns list of SettlementInstruction objects.
    """
    instructions: List[SettlementInstruction] = []

    # Separate creditors (positive balance) and debtors (negative balance)
    creditors = []
    debtors = []

    for ub in user_balances:
        bal = to_decimal(ub.get("balance", 0)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        uid = ub.get("user_id")
        name = ub.get("name", f"User {uid}")

        if bal > Decimal("0.005"):
            creditors.append({
                "user_id": uid,
                "name": name,
                "amount": bal,
            })
        elif bal < -Decimal("0.005"):
            debtors.append({
                "user_id": uid,
                "name": name,
                "amount": abs(bal),
            })

    if not creditors or not debtors:
        return instructions

    # Rounding tolerance check:
    # In a 3-way split, sum of rounded fair shares might differ from total by at most 0.02.
    sum_creditors = sum(c["amount"] for c in creditors)
    sum_debtors = sum(d["amount"] for d in debtors)
    diff = sum_creditors - sum_debtors

    if abs(diff) <= Decimal("0.02") and abs(diff) > Decimal("0.00"):
        # Adjust the largest debtor or creditor to ensure exact parity
        if diff > Decimal("0.00"):
            # Creditors have slightly more than debtors; add difference to primary debtor
            debtors[0]["amount"] += diff
        else:
            # Debtors have slightly more; add difference to primary creditor
            creditors[0]["amount"] += abs(diff)

    # Sort descending by amount to minimize number of transfers (greedy approach)
    creditors.sort(key=lambda x: x["amount"], reverse=True)
    debtors.sort(key=lambda x: x["amount"], reverse=True)

    c_idx = 0
    d_idx = 0

    while c_idx < len(creditors) and d_idx < len(debtors):
        creditor = creditors[c_idx]
        debtor = debtors[d_idx]

        settle_amt = min(creditor["amount"], debtor["amount"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )

        if settle_amt >= Decimal("0.01"):
            instructions.append(
                SettlementInstruction(
                    from_user_id=debtor["user_id"],
                    from_user_name=debtor["name"],
                    to_user_id=creditor["user_id"],
                    to_user_name=creditor["name"],
                    amount=settle_amt,
                )
            )

            creditor["amount"] -= settle_amt
            debtor["amount"] -= settle_amt

        if creditor["amount"] < Decimal("0.005"):
            c_idx += 1
        if debtor["amount"] < Decimal("0.005"):
            d_idx += 1

    return instructions
