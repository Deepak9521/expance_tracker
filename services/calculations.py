"""Financial calculation engine for the 3-person shared expense tracker.

All calculations use Python's Decimal class to avoid floating-point inaccuracy.
Formulae:
- total_expenses = sum(all expenses)
- fair_share = total_expenses / 3 (rounded to 2 decimal places)
- user_balance = user_paid - fair_share
"""

from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any, Iterable, List, Dict, Optional, Tuple
from datetime import date


def to_decimal(val: Any) -> Decimal:
    """Convert an int, float, str, or Decimal to a Decimal instance safely."""
    if val is None:
        return Decimal("0.00")
    if isinstance(val, Decimal):
        return val
    try:
        # String conversion preserves exact representation without float binary noise
        return Decimal(str(val))
    except (InvalidOperation, TypeError, ValueError):
        return Decimal("0.00")


def format_inr(amount: Any) -> str:
    """Format an amount as Indian Rupee string (e.g. ₹1,250.00, -₹500.00).

    Uses the Indian numbering system grouping:
    Last 3 digits, then pairs of 2 digits (e.g. 1,00,000.00).
    """
    dec = to_decimal(amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    is_negative = dec < 0
    abs_dec = abs(dec)
    int_part, dec_part = f"{abs_dec:.2f}".split(".")

    if len(int_part) <= 3:
        formatted_int = int_part
    else:
        last3 = int_part[-3:]
        rest = int_part[:-3]
        groups = []
        while len(rest) > 2:
            groups.insert(0, rest[-2:])
            rest = rest[:-2]
        if rest:
            groups.insert(0, rest)
        formatted_int = ",".join(groups) + "," + last3

    formatted_str = f"₹{formatted_int}.{dec_part}"
    return f"-{formatted_str}" if is_negative else formatted_str


def calculate_total_expenses(amounts: Iterable[Any]) -> Decimal:
    """Calculate the total sum of all expense amounts."""
    total = sum((to_decimal(a) for a in amounts), Decimal("0.00"))
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_fair_share(total: Any, num_people: int = 3) -> Decimal:
    """Calculate equal fair share per person, rounded to 2 decimal places."""
    if num_people <= 0:
        return Decimal("0.00")
    total_dec = to_decimal(total)
    share = total_dec / Decimal(num_people)
    return share.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_user_paid(expenses: Iterable[Any], user_id: int) -> Decimal:
    """Calculate the total amount paid by a specific user from an iterable of expenses."""
    total = Decimal("0.00")
    for exp in expenses:
        # Support both SQLAlchemy model objects and dicts
        exp_paid_by = getattr(exp, "paid_by", None) if not isinstance(exp, dict) else exp.get("paid_by")
        exp_amount = getattr(exp, "amount", 0) if not isinstance(exp, dict) else exp.get("amount", 0)
        if exp_paid_by == user_id:
            total += to_decimal(exp_amount)
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_user_balance(paid: Any, fair_share: Any) -> Decimal:
    """Calculate a user's balance: user_balance = user_paid - fair_share.

    Positive balance = user should receive money.
    Negative balance = user owes money.
    Zero = settled.
    """
    paid_dec = to_decimal(paid)
    share_dec = to_decimal(fair_share)
    return (paid_dec - share_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def calculate_period_summary(expenses: List[Any], users: List[Any]) -> Dict[str, Any]:
    """Calculate complete summary for a period including per-person paid, share, balance,

    daily spending, and category totals.
    """
    total = calculate_total_expenses(
        getattr(exp, "amount", 0) if not isinstance(exp, dict) else exp.get("amount", 0)
        for exp in expenses
    )
    num_users = len(users) if users else 3
    fair_share = calculate_fair_share(total, num_people=num_users)

    user_summaries = []
    for user in users:
        u_id = getattr(user, "id", None) if not isinstance(user, dict) else user.get("id")
        u_name = getattr(user, "name", "User") if not isinstance(user, dict) else user.get("name", "User")
        u_username = getattr(user, "username", "") if not isinstance(user, dict) else user.get("username", "")

        paid = calculate_user_paid(expenses, u_id)
        balance = calculate_user_balance(paid, fair_share)

        user_summaries.append({
            "user_id": u_id,
            "name": u_name,
            "username": u_username,
            "paid": paid,
            "fair_share": fair_share,
            "balance": balance,
        })

    # Group daily spending
    daily_map: Dict[date, Dict[str, Any]] = {}
    for exp in expenses:
        exp_date = getattr(exp, "expense_date", None) if not isinstance(exp, dict) else exp.get("expense_date")
        exp_amount = getattr(exp, "amount", 0) if not isinstance(exp, dict) else exp.get("amount", 0)
        exp_paid_by = getattr(exp, "paid_by", None) if not isinstance(exp, dict) else exp.get("paid_by")

        if exp_date:
            if exp_date not in daily_map:
                daily_map[exp_date] = {
                    "total": Decimal("0.00"),
                    "by_user": {getattr(u, "id", None) if not isinstance(u, dict) else u.get("id"): Decimal("0.00") for u in users},
                }
            amt_dec = to_decimal(exp_amount)
            daily_map[exp_date]["total"] += amt_dec
            if exp_paid_by in daily_map[exp_date]["by_user"]:
                daily_map[exp_date]["by_user"][exp_paid_by] += amt_dec

    # Group category spending
    category_map: Dict[str, Decimal] = {}
    for exp in expenses:
        cat = getattr(exp, "category", "Other") if not isinstance(exp, dict) else exp.get("category", "Other")
        amt = getattr(exp, "amount", 0) if not isinstance(exp, dict) else exp.get("amount", 0)
        category_map[cat] = category_map.get(cat, Decimal("0.00")) + to_decimal(amt)

    return {
        "total_expenses": total,
        "fair_share_per_person": fair_share,
        "user_summaries": user_summaries,
        "daily_breakdown": daily_map,
        "category_breakdown": category_map,
    }

