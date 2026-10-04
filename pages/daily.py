"""Daily spending page: day-by-day expense breakdown and Plotly chart."""

from datetime import date, timedelta
from decimal import Decimal
import streamlit as st
import pandas as pd
import plotly.express as px
from auth.auth import is_authenticated, get_all_users
from database.connection import get_db
from services.expenses import get_expenses, get_week_bounds
from services.calculations import format_inr, to_decimal


def render_daily():
    """Render Daily Spending breakdown and charts."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    st.title("📅 Daily Spending Breakdown")
    st.caption("View day-by-day spending and see who paid for what on each day.")

    today = date.today()

    col1, col2 = st.columns([1, 2])
    with col1:
        range_choice = st.selectbox(
            "Select Timeframe",
            ["This Week", "Today", "Last 7 Days", "This Month", "Custom Range"],
            index=0,
            key="daily_range_choice",
        )

    if range_choice == "Today":
        start_date, end_date = today, today
    elif range_choice == "This Week":
        start_date, end_date = get_week_bounds(today)
    elif range_choice == "Last 7 Days":
        start_date, end_date = today - timedelta(days=6), today
    elif range_choice == "This Month":
        start_date = today.replace(day=1)
        next_month = (start_date.replace(day=28) + timedelta(days=4)).replace(day=1)
        end_date = next_month - timedelta(days=1)
    else:
        with col2:
            custom_range = st.date_input(
                "Custom Date Range",
                value=(today - timedelta(days=7), today),
                key="daily_custom_dates",
            )
            if isinstance(custom_range, tuple) and len(custom_range) == 2:
                start_date, end_date = custom_range
            else:
                start_date, end_date = today - timedelta(days=7), today

    with col2:
        if range_choice != "Custom Range":
            st.info(f"Showing days from **{start_date.strftime('%d %b %Y')}** to **{end_date.strftime('%d %b %Y')}**")

    try:
        with get_db() as session:
            users = get_all_users(session)
            expenses = get_expenses(start_date=start_date, end_date=end_date, session=session)
            user_map = {u.id: u.name for u in users}
    except Exception as e:
        st.error(f"Error loading daily data: {e}")
        return

    # Group expenses by date and user
    daily_data = {}
    for exp in expenses:
        d = exp.expense_date
        if d not in daily_data:
            daily_data[d] = {
                "total": Decimal("0.00"),
                "by_user": {u.id: Decimal("0.00") for u in users},
                "items": [],
            }
        amt = to_decimal(exp.amount)
        daily_data[d]["total"] += amt
        if exp.paid_by in daily_data[d]["by_user"]:
            daily_data[d]["by_user"][exp.paid_by] += amt
        daily_data[d]["items"].append(exp)

    # Total for selected range
    range_total = sum((data["total"] for data in daily_data.values()), Decimal("0.00"))
    st.markdown(f"### Total Period Spending: **{format_inr(range_total)}** across {len(daily_data)} active days")

    # Plotly Chart
    if daily_data:
        chart_rows = []
        for d in sorted(daily_data.keys()):
            for u in users:
                u_amt = daily_data[d]["by_user"][u.id]
                chart_rows.append({
                    "Date": d.strftime("%d %b"),
                    "Person": u.name,
                    "Amount": float(u_amt),
                    "Formatted": format_inr(u_amt),
                })
        df_chart = pd.DataFrame(chart_rows)

        fig = px.bar(
            df_chart,
            x="Date",
            y="Amount",
            color="Person",
            title=f"Daily Spending by Person ({range_choice})",
            barmode="stack",
            color_discrete_sequence=["#2563EB", "#10B981", "#F59E0B"],
        )
        fig.update_layout(
            yaxis_title="Amount (₹)",
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            margin=dict(l=20, r=20, t=40, b=20),
            yaxis=dict(gridcolor="#E2E8F0"),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("No expenses found for this date range.")

    st.markdown("---")
    st.markdown("### 📋 Day-by-Day Details")

    if not daily_data:
        st.caption("No daily records to show.")
        return

    # Sort descending by date
    for d in sorted(daily_data.keys(), reverse=True):
        d_info = daily_data[d]
        formatted_date = d.strftime("%B %d, %Y")

        with st.container():
            st.markdown(
                f"""
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 14px; margin-bottom: 12px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #F1F5F9; padding-bottom: 8px;">
                        <h4 style="margin: 0; color: #0F172A;">🗓️ {formatted_date}</h4>
                        <span style="font-size: 16px; font-weight: 700; color: #2563EB;">Total: {format_inr(d_info['total'])}</span>
                    </div>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Three user columns for this day
            cols = st.columns(3)
            for i, u in enumerate(users):
                with cols[i]:
                    u_paid = d_info["by_user"].get(u.id, Decimal("0.00"))
                    st.write(f"**{u.name}:** {format_inr(u_paid)}")

            # Expander for itemized list of this day
            with st.expander(f"View items for {formatted_date} ({len(d_info['items'])} items)"):
                day_items = [
                    {
                        "Description": item.description,
                        "Category": item.category,
                        "Paid By": user_map.get(item.paid_by, f"User {item.paid_by}"),
                        "Amount": format_inr(item.amount),
                    }
                    for item in d_info["items"]
                ]
                st.dataframe(pd.DataFrame(day_items), use_container_width=True, hide_index=True)


if __name__ == "__main__":
    render_daily()
