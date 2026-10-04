"""Add Expense page: form to record new shared expenses."""

from datetime import date
from decimal import Decimal
import streamlit as st
from auth.auth import is_authenticated, get_all_users, get_current_user
from database.connection import get_db
from services.expenses import create_expense, VALID_CATEGORIES, is_week_closed
from services.calculations import format_inr


def render_add_expense():
    """Render Add Expense form and process submission."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    current_user = get_current_user()

    st.title("➕ Add New Expense")
    st.caption("Every expense is automatically divided equally among all three people.")

    # Fetch users from database
    try:
        with get_db() as session:
            users = get_all_users(session)
            if len(users) < 3:
                st.error("System configuration error: 3 users must be initialized first.")
                return
            user_options = {u.id: f"{u.name} ({u.username})" for u in users}
    except Exception as e:
        st.error(f"Database error loading users: {e}")
        return
    default_user_id = current_user.get("id") if current_user else users[0].id

    # Find index of current user for selectbox default
    user_ids = list(user_options.keys())
    default_index = user_ids.index(default_user_id) if default_user_id in user_ids else 0

    with st.form("add_expense_form", clear_on_submit=True):
        col1, col2 = st.columns(2)

        with col1:
            description = st.text_input(
                "Description *",
                placeholder="e.g. Weekly grocery run, WiFi recharge",
                help="Briefly describe what was purchased.",
            )
            amount = st.number_input(
                "Amount (₹) *",
                min_value=0.01,
                max_value=10000000.00,
                step=10.00,
                value=None,
                placeholder="0.00",
                format="%.2f",
                help="Enter total cost in Indian Rupees.",
            )
            category = st.selectbox(
                "Category *",
                options=VALID_CATEGORIES,
                index=0,
            )

        with col2:
            expense_date = st.date_input(
                "Expense Date *",
                value=date.today(),
                max_value=date.today(),
                help="Date when the payment occurred.",
            )
            paid_by_id = st.selectbox(
                "Paid By *",
                options=user_ids,
                format_func=lambda uid: user_options[uid],
                index=default_index,
                help="Select which of the three housemates paid the bill.",
            )

            # Live preview of fair share
            if amount and amount > 0:
                share_preview = Decimal(str(amount)) / Decimal("3")
                st.info(f"Fair share per person will be **{format_inr(share_preview)}**")

        submitted = st.form_submit_button("Record Expense", use_container_width=True, type="primary")

    if submitted:
        # Check validation
        if not description or not description.strip():
            st.error("Description cannot be empty.")
            return

        if not amount or amount <= 0:
            st.error("Amount must be greater than 0.")
            return

        if not expense_date:
            st.error("Please select a valid expense date.")
            return

        if paid_by_id not in user_options:
            st.error("Paid By must be one of the three users.")
            return

        # Attempt database insertion
        try:
            with get_db() as session:
                # Check closed week
                closed, summary = is_week_closed(expense_date, session)
                if closed and summary:
                    st.error(
                        f"Cannot add expense: The week from {summary.week_start.strftime('%d %b %Y')} "
                        f"to {summary.week_end.strftime('%d %b %Y')} has already been closed and saved."
                    )
                    return

                new_expense = create_expense(
                    description=description,
                    amount=amount,
                    category=category,
                    paid_by=paid_by_id,
                    expense_date=expense_date,
                    session=session,
                )

            st.success("Expense added successfully.")
            st.balloons()
        except Exception as e:
            st.error(f"Failed to record expense: {e}")


if __name__ == "__main__":
    render_add_expense()
