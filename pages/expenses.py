"""Expenses history page: filtering, viewing, editing, and deleting expenses."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
import pandas as pd
from auth.auth import is_authenticated, get_all_users, get_current_user
from database.connection import get_db
from sqlalchemy import select
from database.models import WeeklySummary
from services.expenses import (
    get_expenses,
    update_expense,
    delete_expense,
    get_week_bounds,
    VALID_CATEGORIES,
)
from services.calculations import format_inr, to_decimal


def render_expenses():
    """Render Expense History view with filtering, editing, and deleting capabilities."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    current_user = get_current_user()
    current_user_id = current_user.get("id") if current_user else None

    st.title("📜 Expense History")
    st.caption("Browse, filter, edit, or delete expenses.")

    try:
        with get_db() as session:
            users = get_all_users(session)
            user_map = {u.id: u.name for u in users}
    except Exception as e:
        st.error(f"Error loading users: {e}")
        return

    # 1. Filters Section
    with st.expander("🔍 Filter Expenses", expanded=True):
        f_col1, f_col2, f_col3 = st.columns(3)

        with f_col1:
            date_filter = st.selectbox(
                "Date Range",
                ["This Week", "Today", "Last Week", "This Month", "Custom Date Range", "All Time"],
                index=0,
            )

        with f_col2:
            person_filter_options = ["All"] + [u.name for u in users]
            person_filter = st.selectbox("Paid By", person_filter_options, index=0)

        with f_col3:
            category_filter_options = ["All"] + VALID_CATEGORIES
            category_filter = st.selectbox("Category", category_filter_options, index=0)

        # Date calculations
        today = date.today()
        start_date = None
        end_date = None

        if date_filter == "Today":
            start_date = today
            end_date = today
        elif date_filter == "This Week":
            start_date, end_date = get_week_bounds(today)
        elif date_filter == "Last Week":
            last_week_day = today - timedelta(days=7)
            start_date, end_date = get_week_bounds(last_week_day)
        elif date_filter == "This Month":
            start_date = today.replace(day=1)
            next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
            end_date = next_month - timedelta(days=1)
        elif date_filter == "Custom Date Range":
            custom_range = st.date_input(
                "Select Range",
                value=(today - timedelta(days=14), today),
                key="exp_custom_range",
            )
            if isinstance(custom_range, tuple) and len(custom_range) == 2:
                start_date, end_date = custom_range
            else:
                start_date, end_date = today - timedelta(days=14), today

        # Person filter calculation
        filter_user_id = None
        if person_filter != "All":
            for u in users:
                if u.name == person_filter:
                    filter_user_id = u.id
                    break

        cat_filter_val = category_filter if category_filter != "All" else None

    # Fetch expenses
    try:
        with get_db() as session:
            expenses = get_expenses(
                start_date=start_date,
                end_date=end_date,
                user_id=filter_user_id,
                category=cat_filter_val,
                session=session,
            )
            summaries = session.execute(select(WeeklySummary.week_start, WeeklySummary.week_end)).all()
            closed_ranges = [(s[0], s[1]) for s in summaries]
    except Exception as e:
        st.error(f"Error loading expenses: {e}")
        return

    # Total of filtered items
    total_amount = sum((to_decimal(e.amount) for e in expenses), Decimal("0.00"))
    st.markdown(
        f"**Found {len(expenses)} expenses totaling {format_inr(total_amount)}**"
    )

    if not expenses:
        st.info("No expenses found matching the selected filters.")
        return

    st.markdown("---")

    # Display list of expenses with Edit/Delete controls for owner
    for exp in expenses:
        is_owner = (exp.paid_by == current_user_id)
        payer_name = user_map.get(exp.paid_by, f"User {exp.paid_by}")
        week_closed = any(start <= exp.expense_date <= end for start, end in closed_ranges)

        with st.container():
            c1, c2, c3, c4, c5 = st.columns([2, 3, 2, 2, 3])

            with c1:
                st.write(f"📅 **{exp.expense_date.strftime('%d %b %Y')}**")
            with c2:
                st.write(f"**{exp.description}**")
                st.caption(f"🏷️ {exp.category}")
            with c3:
                st.write(f"👤 {payer_name}")
            with c4:
                st.write(f"💰 **{format_inr(exp.amount)}**")
            with c5:
                if week_closed:
                    st.caption("🔒 *Week Closed*")
                elif is_owner:
                    # Show action buttons for expense owner
                    edit_key = f"edit_btn_{exp.id}"
                    del_key = f"del_btn_{exp.id}"

                    act_col1, act_col2 = st.columns(2)
                    with act_col1:
                        if st.button("✏️ Edit", key=edit_key, use_container_width=True):
                            st.session_state[f"editing_{exp.id}"] = not st.session_state.get(f"editing_{exp.id}", False)
                    with act_col2:
                        if st.button("🗑️ Delete", key=del_key, type="secondary", use_container_width=True):
                            st.session_state[f"confirm_delete_{exp.id}"] = True
                else:
                    st.caption("👁️ *View only*")

            # Inline Edit Form
            if st.session_state.get(f"editing_{exp.id}", False):
                with st.expander(f"Editing: {exp.description}", expanded=True):
                    with st.form(f"edit_form_{exp.id}"):
                        e_desc = st.text_input("Description", value=exp.description)
                        e_amt = st.number_input("Amount (₹)", min_value=0.01, step=10.0, value=float(exp.amount))
                        e_cat = st.selectbox(
                            "Category",
                            options=VALID_CATEGORIES,
                            index=VALID_CATEGORIES.index(exp.category) if exp.category in VALID_CATEGORIES else 0,
                        )
                        e_date = st.date_input("Date", value=exp.expense_date)

                        user_opts = {u.id: u.name for u in users}
                        e_payer = st.selectbox(
                            "Paid By",
                            options=list(user_opts.keys()),
                            format_func=lambda uid: user_opts[uid],
                            index=list(user_opts.keys()).index(exp.paid_by),
                        )

                        save_btn = st.form_submit_button("Save Changes", type="primary")

                    if save_btn:
                        try:
                            with get_db() as session:
                                update_expense(
                                    expense_id=exp.id,
                                    acting_user_id=current_user_id,
                                    description=e_desc,
                                    amount=e_amt,
                                    category=e_cat,
                                    paid_by=e_payer,
                                    expense_date=e_date,
                                    session=session,
                                )
                            st.success("Expense updated successfully.")
                            del st.session_state[f"editing_{exp.id}"]
                            st.rerun()
                        except Exception as err:
                            st.error(f"Failed to update expense: {err}")

            # Delete Confirmation Dialog
            if st.session_state.get(f"confirm_delete_{exp.id}", False):
                st.warning(f"⚠️ Are you sure you want to delete '{exp.description}' ({format_inr(exp.amount)})?")
                conf_c1, conf_c2 = st.columns(2)
                with conf_c1:
                    if st.button("Yes, Delete Expense", key=f"do_del_{exp.id}", type="primary"):
                        try:
                            with get_db() as session:
                                delete_expense(
                                    expense_id=exp.id,
                                    acting_user_id=current_user_id,
                                    session=session,
                                )
                            st.success("Expense deleted.")
                            del st.session_state[f"confirm_delete_{exp.id}"]
                            st.rerun()
                        except Exception as del_err:
                            st.error(f"Failed to delete: {del_err}")
                with conf_c2:
                    if st.button("Cancel", key=f"cancel_del_{exp.id}"):
                        del st.session_state[f"confirm_delete_{exp.id}"]
                        st.rerun()

            st.markdown("<hr style='margin: 8px 0; border: none; border-top: 1px solid #F1F5F9;' />", unsafe_allow_html=True)


if __name__ == "__main__":
    render_expenses()
