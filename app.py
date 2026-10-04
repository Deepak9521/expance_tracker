"""Private 3-Person Shared Expense Tracker - Main Streamlit Application."""

import streamlit as st
from dotenv import load_dotenv

# Set page config as the very first Streamlit call
st.set_page_config(
    page_title="Shared Expense Tracker",
    page_icon="💰",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Load environment variables
load_dotenv()

from database.connection import check_connection, get_db
from database.models import User
from auth.auth import (
    authenticate_user,
    login_user,
    logout_user,
    get_current_user,
    is_authenticated,
    get_all_users,
)
from pages.dashboard import render_dashboard
from pages.add_expense import render_add_expense
from pages.expenses import render_expenses
from pages.daily import render_daily
from pages.settlement import render_settlement
from pages.weekly_history import render_weekly_history


def render_login():
    """Render clean, secure login interface for the 3 fixed users."""
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown(
            """
            <div style="text-align: center; margin-top: 40px; margin-bottom: 24px;">
                <h1 style="color: #1E3A8A; margin-bottom: 4px;">🏠 Shared Expense Tracker</h1>
                <p style="color: #64748B; font-size: 15px;">Private expense management for 3 housemates</p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        with st.container():
            st.markdown(
                """
                <div style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 12px; padding: 24px; box-shadow: 0 4px 6px -1px rgba(0,0,0,0.05);">
                    <h3 style="margin-top: 0; color: #0F172A;">Sign In</h3>
                    <p style="color: #64748B; font-size: 14px;">Please enter your credentials to access the tracker.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

            with st.form("login_form", clear_on_submit=False):
                username_input = st.text_input("Username", placeholder="e.g. person1")
                password_input = st.text_input("Password", type="password", placeholder="Enter password")
                submit_button = st.form_submit_button("Sign In", type="primary", use_container_width=True)

            if submit_button:
                if not username_input or not password_input:
                    st.error("Please enter both username and password.")
                else:
                    try:
                        with get_db() as session:
                            user = authenticate_user(username_input, password_input, session)
                            if user:
                                login_user(user)
                                st.success(f"Welcome back, {user.name}!")
                                st.rerun()
                            else:
                                st.error("Invalid username or password.")
                    except Exception as err:
                        st.error(f"Authentication error: {err}")

            st.caption("🔒 This private application is exclusively for three designated members.")


def main():
    """Main application lifecycle and navigation router."""
    # 1. Database Connection Health Check
    ok, conn_err = check_connection()
    if not ok:
        st.error(
            "⚠️ **Database Connection Failed**\n\n"
            "Unable to connect to the PostgreSQL database.\n\n"
            f"**Error Details:** `{conn_err}`\n\n"
            "**Troubleshooting Checklist:**\n"
            "1. Ensure your `DATABASE_URL` in `.env` is correct.\n"
            "2. Ensure your PostgreSQL server is running and accessible.\n"
            "3. If starting for the first time, run: `python scripts/seed_users.py`."
        )
        st.stop()

    # 2. Check Seed State (Ensure 3 users exist)
    try:
        with get_db() as session:
            users = get_all_users(session)
            if len(users) < 3:
                st.warning(
                    f"⚠️ **Database Incomplete:** Found {len(users)} user(s). Exactly 3 users are required.\n\n"
                    "Please run the database seed script to initialize the 3 users:\n\n"
                    "```bash\npython scripts/seed_users.py\n```"
                )
                st.stop()
    except Exception as db_err:
        st.error(f"Error accessing database: {db_err}")
        st.stop()

    # 3. Authentication Check
    if not is_authenticated():
        render_login()
        return

    current_user = get_current_user()

    # 4. Top User Banner
    top_c1, top_c2 = st.columns([3, 1])
    with top_c1:
        st.markdown(
            f"👤 Logged in as: **{current_user['name']}** (`{current_user['username']}`)"
        )
    with top_c2:
        # Quick logout button on top bar
        if st.button("🚪 Logout", key="top_logout_btn"):
            logout_user()

    st.markdown("<hr style='margin: 8px 0 16px 0; border: none; border-top: 1px solid #E2E8F0;' />", unsafe_allow_html=True)

    # 5. Sidebar Navigation
    with st.sidebar:
        st.markdown(
            """
            <div style="margin-bottom: 20px;">
                <h2 style="color: #2563EB; margin: 0;">🏠 Shared Tracker</h2>
                <span style="font-size: 13px; color: #64748B;">3-Person Expense Sharing</span>
            </div>
            """,
            unsafe_allow_html=True,
        )

        nav_selection = st.radio(
            "Navigation",
            options=[
                "Dashboard",
                "Add Expense",
                "Expenses",
                "Daily Spending",
                "Settlement",
                "Weekly History",
            ],
            index=0,
            label_visibility="collapsed",
        )

        st.markdown("---")
        st.caption(f"Active User: **{current_user['name']}**")

        if st.button("🚪 Log Out", key="sidebar_logout_btn", use_container_width=True):
            logout_user()

    # 6. Page Routing
    if nav_selection == "Dashboard":
        render_dashboard()
    elif nav_selection == "Add Expense":
        render_add_expense()
    elif nav_selection == "Expenses":
        render_expenses()
    elif nav_selection == "Daily Spending":
        render_daily()
    elif nav_selection == "Settlement":
        render_settlement()
    elif nav_selection == "Weekly History":
        render_weekly_history()


if __name__ == "__main__":
    main()
