"""Settlement page: calculates minimal practical settlement transfers and manages week closure."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
from auth.auth import is_authenticated, get_all_users, get_current_user
from database.connection import get_db
from services.expenses import (
    get_expenses,
    get_week_bounds,
    is_week_closed,
    close_and_save_week,
)
from services.calculations import calculate_period_summary, format_inr
from services.settlement import calculate_settlement


def render_settlement():
    """Render Weekly Settlement calculation and week closing controls."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    current_user = get_current_user()

    st.title("🤝 Weekly Settlement")
    st.caption("Calculate exact balances and minimum settlement transactions for the week.")

    # 1. Week Selector (defaults to Current Week)
    today = date.today()
    curr_start, curr_end = get_week_bounds(today)

    week_options = {
        "Current Week": (curr_start, curr_end),
        "Last Week": get_week_bounds(today - timedelta(days=7)),
        "2 Weeks Ago": get_week_bounds(today - timedelta(days=14)),
        "3 Weeks Ago": get_week_bounds(today - timedelta(days=21)),
    }

    w_choice = st.selectbox(
        "Select Week to Settle",
        list(week_options.keys()),
        index=0,
        key="settlement_week_choice",
    )
    week_start, week_end = week_options[w_choice]

    st.info(
        f"📅 Week Period: **{week_start.strftime('%d %b %Y')}** to **{week_end.strftime('%d %b %Y')}**"
    )

    try:
        with get_db() as session:
            users = get_all_users(session)
            week_is_closed, closed_summary = is_week_closed(week_start, session)
            expenses = get_expenses(start_date=week_start, end_date=week_end, session=session)
            summary = calculate_period_summary(expenses, users)
    except Exception as e:
        st.error(f"Database error: {e}")
        return

    total_spent = summary["total_expenses"]
    fair_share = summary["fair_share_per_person"]

    # Status Banner
    if week_is_closed and closed_summary:
        st.warning(
            f"🔒 **This week is officially CLOSED & ARCHIVED.**\n\n"
            f"Closed at: {closed_summary.created_at.strftime('%d %b %Y, %H:%M UTC')}. "
            f"All expenses in this week are permanently locked from modifications."
        )
    else:
        st.success("🟢 **This week is currently OPEN.** Expenses can be recorded, edited, or deleted until closed.")

    st.markdown("---")

    # 2. Key Metrics
    col1, col2 = st.columns(2)
    with col1:
        st.metric("Total Weekly Expenses", format_inr(total_spent))
    with col2:
        st.metric("Fair Share Per Person", format_inr(fair_share))

    # 3. Three User Balances
    st.markdown("### 👤 User Balances")
    u_cols = st.columns(3)

    user_balance_list = []
    for i, u_summary in enumerate(summary["user_summaries"]):
        bal = u_summary["balance"]
        user_balance_list.append({
            "user_id": u_summary["user_id"],
            "name": u_summary["name"],
            "balance": bal,
        })

        if bal > Decimal("0.00"):
            direction = "Receives"
            color = "#16A34A"
            sign = "+"
        elif bal < Decimal("0.00"):
            direction = "Owes"
            color = "#DC2626"
            sign = ""
        else:
            direction = "Settled"
            color = "#64748B"
            sign = ""

        with u_cols[i]:
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px;">
                    <h4 style="margin: 0 0 8px 0; color: #0F172A;">{u_summary['name']}</h4>
                    <p style="margin: 3px 0; font-size: 13px; color: #64748B;">Total Paid: <b>{format_inr(u_summary['paid'])}</b></p>
                    <p style="margin: 3px 0; font-size: 13px; color: #64748B;">Fair Share: <b>{format_inr(u_summary['fair_share'])}</b></p>
                    <div style="margin-top: 10px; padding: 8px; background-color: {color}12; border-radius: 6px;">
                        <span style="font-size: 12px; font-weight: 600; color: {color};">{direction}</span>
                        <div style="font-size: 16px; font-weight: 700; color: {color};">
                            {sign}{format_inr(bal)}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # 4. Settlement Algorithm Results
    st.markdown("### 💸 Settlement Instructions")

    instructions = calculate_settlement(user_balance_list)

    if instructions:
        st.write("To settle all balances with the minimum number of transfers:")
        for idx, inst in enumerate(instructions, 1):
            st.markdown(
                f"""
                <div style="background-color: #F8FAFC; border-left: 4px solid #2563EB; padding: 12px 16px; border-radius: 6px; margin-bottom: 8px;">
                    <span style="font-size: 16px; font-weight: 600; color: #1E293B;">
                        {idx}. {inst.from_user_name} ➔ {inst.to_user_name} : <span style="color: #2563EB;">{format_inr(inst.amount)}</span>
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )
    else:
        st.info("✅ All balances are settled! No payments are required for this period.")

    # Prominent Settlement Notice
    st.markdown(
        """
        <div style="background-color: #FEF3C7; border: 1px solid #F59E0B; border-radius: 8px; padding: 12px; margin-top: 16px;">
            <p style="margin: 0; color: #92400E; font-size: 14px; font-weight: 500;">
                ℹ️ <b>Settlement is handled personally.</b> Actual payments are NOT processed inside this application.
                Use your personal UPI, bank transfer, or cash to complete these transfers.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("---")

    # 5. Close & Save Week Section
    st.markdown("### 🗄️ Week Status & Closure")
    st.write(
        "A week is considered closed only when explicitly saved. Once closed, the totals "
        "are archived permanently and expense records belonging to this week cannot be edited or deleted."
    )

    if week_is_closed:
        st.button("Week Already Closed & Saved", disabled=True, use_container_width=True)
    else:
        with st.expander("⚠️ Confirm & Close This Week", expanded=False):
            st.write(
                f"Are you sure you want to close the week of **{week_start.strftime('%d %b')} - {week_end.strftime('%d %b %Y')}**?"
            )
            st.write("This will:")
            st.write("1. Calculate and lock final weekly totals.")
            st.write("2. Save the permanent weekly summary.")
            st.write("3. Prevent any further modifications to expenses in this date range.")

            confirm_check = st.checkbox("I confirm all expenses for this week have been accurately entered.")

            if st.button("Close & Save Week", type="primary", disabled=not confirm_check):
                try:
                    with get_db() as session:
                        summary_obj = close_and_save_week(week_start, week_end, session=session)
                    st.success(
                        f"Week ({week_start.strftime('%d %b')} to {week_end.strftime('%d %b')}) "
                        "has been successfully closed and saved!"
                    )
                    st.rerun()
                except Exception as close_err:
                    st.error(f"Failed to close week: {close_err}")


if __name__ == "__main__":
    render_settlement()
