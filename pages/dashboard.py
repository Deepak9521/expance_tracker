"""Dashboard page: overview of spending, fair share, balances, and daily trends."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
import plotly.express as px
import pandas as pd
from auth.auth import get_all_users, is_authenticated, get_current_user
from database.connection import get_db
from services.expenses import get_expenses, get_week_bounds
from services.calculations import calculate_period_summary, format_inr


def render_dashboard():
    """Render main Dashboard view."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    current_user = get_current_user()

    st.title("📊 Expense Dashboard")
    st.caption("Shared expenses split equally among the 3 housemates.")

    # 1. Period Selector (Defaults to This Week)
    col_filter, col_dates = st.columns([1, 2])
    with col_filter:
        period_choice = st.selectbox(
            "Selected Period",
            ["This Week", "Last Week", "This Month", "Last 30 Days", "Custom Date Range"],
            index=0,
            key="dash_period",
        )

    today = date.today()
    if period_choice == "This Week":
        start_date, end_date = get_week_bounds(today)
    elif period_choice == "Last Week":
        last_week_any_day = today - timedelta(days=7)
        start_date, end_date = get_week_bounds(last_week_any_day)
    elif period_choice == "This Month":
        start_date = today.replace(day=1)
        # End of current month
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
    elif period_choice == "Last 30 Days":
        start_date = today - timedelta(days=30)
        end_date = today
    else:  # Custom Date Range
        with col_dates:
            date_range = st.date_input(
                "Custom Date Range",
                value=(today - timedelta(days=7), today),
                key="dash_custom_range",
            )
            if isinstance(date_range, tuple) and len(date_range) == 2:
                start_date, end_date = date_range
            else:
                start_date, end_date = today - timedelta(days=7), today

    with col_dates:
        if period_choice != "Custom Date Range":
            st.info(f"Showing data from **{start_date.strftime('%d %b %Y')}** to **{end_date.strftime('%d %b %Y')}**")

    try:
        with get_db() as session:
            users = get_all_users(session)
            expenses = get_expenses(start_date=start_date, end_date=end_date, session=session)
            summary = calculate_period_summary(expenses, users)
    except Exception as e:
        st.error(f"Could not load data from database: {e}")
        return

    total_spent = summary["total_expenses"]
    fair_share = summary["fair_share_per_person"]

    # 2. Main Metrics Summary
    st.markdown("---")
    m1, m2, m3 = st.columns(3)
    with m1:
        st.metric("Total Spending", format_inr(total_spent))
    with m2:
        st.metric("Fair Share Each", format_inr(fair_share))
    with m3:
        st.metric("Total Expenses Logged", f"{len(expenses)} items")

    st.markdown("### 👥 Balances & Shares")

    # 3. Three User Cards
    user_cols = st.columns(3)
    for i, u_summary in enumerate(summary["user_summaries"]):
        col = user_cols[i]
        is_me = current_user and current_user.get("id") == u_summary["user_id"]
        bal = u_summary["balance"]

        if bal > Decimal("0.00"):
            status_text = "Receives"
            status_color = "#16A34A"  # Green
            badge_icon = "🟢"
            sign_prefix = "+"
        elif bal < Decimal("0.00"):
            status_text = "Owes"
            status_color = "#DC2626"  # Red
            badge_icon = "🔴"
            sign_prefix = ""
        else:
            status_text = "Settled"
            status_color = "#475569"  # Slate
            badge_icon = "⚪"
            sign_prefix = ""

        formatted_balance = f"{sign_prefix}{format_inr(bal)}"

        with col:
            title_suffix = " (You)" if is_me else ""
            st.markdown(
                f"""
                <div style="background-color: {'#EFF6FF' if is_me else '#FFFFFF'};
                            border: 2px solid {'#2563EB' if is_me else '#E2E8F0'};
                            border-radius: 12px;
                            padding: 16px;
                            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
                            margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <h4 style="margin: 0; color: #0F172A;">{u_summary['name']}{title_suffix}</h4>
                        <span style="font-size: 13px; font-weight: 600; color: {status_color}; background-color: {status_color}1A; padding: 2px 8px; border-radius: 9999px;">
                            {badge_icon} {status_text}
                        </span>
                    </div>
                    <hr style="margin: 10px 0; border: none; border-top: 1px solid #E2E8F0;" />
                    <p style="margin: 4px 0; color: #64748B; font-size: 14px;">Total Paid: <b style="color: #0F172A;">{format_inr(u_summary['paid'])}</b></p>
                    <p style="margin: 4px 0; color: #64748B; font-size: 14px;">Fair Share: <b style="color: #0F172A;">{format_inr(u_summary['fair_share'])}</b></p>
                    <div style="margin-top: 12px; padding: 8px; background-color: {status_color}10; border-radius: 8px;">
                        <span style="font-size: 13px; color: {status_color}; font-weight: 500;">Net Balance:</span>
                        <div style="font-size: 18px; font-weight: 700; color: {status_color};">
                            {formatted_balance}
                        </div>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

    st.markdown("---")

    # 4. Daily Spending Chart (Plotly)
    st.markdown("### 📈 Daily Spending Trend")
    daily_breakdown = summary["daily_breakdown"]

    if daily_breakdown:
        # Build DataFrame for Plotly
        records = []
        for d, d_data in sorted(daily_breakdown.items()):
            records.append({
                "Date": d.strftime("%d %b"),
                "Amount": float(d_data["total"]),
                "Formatted": format_inr(d_data["total"]),
            })
        df_daily = pd.DataFrame(records)

        fig = px.bar(
            df_daily,
            x="Date",
            y="Amount",
            text="Formatted",
            title=f"Total Spending per Day ({period_choice})",
            color_discrete_sequence=["#2563EB"],
        )
        fig.update_traces(textposition="outside")
        fig.update_layout(
            yaxis_title="Amount (₹)",
            xaxis_title="Date",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis=dict(gridcolor="#E2E8F0"),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No expenses recorded for the selected period.")

    # 5. Recent Expenses Table
    st.markdown("### 🕒 Recent Expenses")
    if expenses:
        recent_list = []
        for exp in expenses[:8]:  # Show recent 8
            recent_list.append({
                "Date": exp.expense_date.strftime("%d %b %Y"),
                "Description": exp.description,
                "Category": exp.category,
                "Paid By": exp.payer.name if exp.payer else f"User {exp.paid_by}",
                "Amount": format_inr(exp.amount),
            })
        st.dataframe(pd.DataFrame(recent_list), use_container_width=True, hide_index=True)
    else:
        st.caption("No recent expenses to display.")


if __name__ == "__main__":
    render_dashboard()
