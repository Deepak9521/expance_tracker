"""Weekly History page: view past closed weeks and manage 60-day data retention."""

from decimal import Decimal
import streamlit as st
import pandas as pd
from auth.auth import is_authenticated, get_all_users
from database.connection import get_db
from services.expenses import (
    get_weekly_summaries,
    delete_expenses_older_than_60_days,
)
from services.calculations import format_inr
from services.settlement import calculate_settlement


def render_weekly_history():
    """Render Weekly History view and 60-day retention maintenance."""
    if not is_authenticated():
        st.warning("Please log in from the main application page.")
        st.stop()

    st.title("📚 Weekly History & Archives")
    st.caption("Permanent record of all closed and settled weeks.")

    try:
        with get_db() as session:
            users = get_all_users(session)
            summaries = get_weekly_summaries(session)
            user_names = [u.name for u in users] if len(users) >= 3 else ["Person 1", "Person 2", "Person 3"]
    except Exception as e:
        st.error(f"Error loading weekly summaries: {e}")
        return

    # 1. Summaries List
    if not summaries:
        st.info("No closed weeks yet. Weeks can be closed and saved from the **Settlement** page.")
    else:
        st.write(f"Displaying **{len(summaries)}** closed weekly summary archives:")

        for s in summaries:
            w_title = f"🗓️ Week: {s.week_start.strftime('%d %b %Y')} – {s.week_end.strftime('%d %b %Y')}"

            # Calculate balances
            b1 = Decimal(str(s.person_1_paid)) - Decimal(str(s.person_1_share))
            b2 = Decimal(str(s.person_2_paid)) - Decimal(str(s.person_2_share))
            b3 = Decimal(str(s.person_3_paid)) - Decimal(str(s.person_3_share))

            balances_data = [
                {"user_id": users[0].id if len(users) > 0 else 1, "name": user_names[0], "balance": b1},
                {"user_id": users[1].id if len(users) > 1 else 2, "name": user_names[1], "balance": b2},
                {"user_id": users[2].id if len(users) > 2 else 3, "name": user_names[2], "balance": b3},
            ]
            past_instructions = calculate_settlement(balances_data)

            with st.container():
                st.markdown(
                    f"""
                    <div style="background-color: #FFFFFF; border: 1px solid #CBD5E1; border-radius: 10px; padding: 16px; margin-bottom: 16px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #E2E8F0; padding-bottom: 10px; margin-bottom: 12px;">
                            <h4 style="margin: 0; color: #1E293B;">{w_title}</h4>
                            <span style="font-size: 17px; font-weight: 700; color: #2563EB;">Total: {format_inr(s.total_expenses)}</span>
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

                # 3 columns for 3 persons
                c1, c2, c3 = st.columns(3)
                p_data = [
                    (user_names[0], s.person_1_paid, s.person_1_share, b1, c1),
                    (user_names[1], s.person_2_paid, s.person_2_share, b2, c2),
                    (user_names[2], s.person_3_paid, s.person_3_share, b3, c3),
                ]

                for name, paid, share, bal, col in p_data:
                    with col:
                        bal_color = "#16A34A" if bal > 0 else ("#DC2626" if bal < 0 else "#64748B")
                        bal_sign = "+" if bal > 0 else ""
                        st.markdown(
                            f"""
                            <div style="background-color: #F8FAFC; border: 1px solid #E2E8F0; border-radius: 8px; padding: 10px;">
                                <b style="color: #0F172A;">{name}</b><br/>
                                <span style="font-size: 13px; color: #64748B;">Paid: {format_inr(paid)}</span><br/>
                                <span style="font-size: 13px; color: #64748B;">Share: {format_inr(share)}</span><br/>
                                <span style="font-size: 14px; font-weight: 600; color: {bal_color};">
                                    Balance: {bal_sign}{format_inr(bal)}
                                </span>
                            </div>
                            """,
                            unsafe_allow_html=True,
                        )

                # Past settlement instructions
                if past_instructions:
                    st.caption("Settlement instructions executed:")
                    for inst in past_instructions:
                        st.write(f"• {inst.display_text}")

                st.caption(f"Archived on: {s.created_at.strftime('%d %b %Y, %H:%M UTC')}")
                st.markdown("---")

    # 2. 60-Day Data Retention Management Section
    st.markdown("### 🧹 60-Day Data Retention Policy")
    st.write(
        "Individual expense items are retained for approximately 60 days. "
        "Before any old expense records are purged, the system guarantees that corresponding "
        "weekly summaries are generated and permanently archived so financial totals are never lost."
    )

    with st.expander("⚙️ Retention Cleanup Controls", expanded=False):
        st.write("Run a manual check or cleanup of expenses older than 60 days.")

        rc1, rc2 = st.columns(2)
        with rc1:
            if st.button("🔍 Check / Preview Cleanup (Dry-Run)", use_container_width=True):
                try:
                    with get_db() as session:
                        res = delete_expenses_older_than_60_days(session, dry_run=True)
                    st.info(
                        f"**Dry-Run Results:**\n"
                        f"- Cutoff Date: {res['cutoff_date']}\n"
                        f"- Candidate Expenses to Delete: {res['deleted_count']}\n"
                        f"- Unsummarized Weeks to Auto-Archive: {res['archived_weeks']}"
                    )
                except Exception as ex:
                    st.error(f"Dry-run failed: {ex}")

        with rc2:
            confirm_cleanup = st.checkbox("Confirm permanent deletion of >60 day expenses", key="conf_clean")
            if st.button("🗑️ Run Cleanup Now", type="secondary", disabled=not confirm_cleanup, use_container_width=True):
                try:
                    with get_db() as session:
                        res = delete_expenses_older_than_60_days(session, dry_run=False)
                    st.success(
                        f"Cleanup complete! Deleted {res['deleted_count']} old expenses. "
                        f"Auto-archived {res['archived_weeks']} weekly summaries."
                    )
                    st.rerun()
                except Exception as ex:
                    st.error(f"Cleanup failed: {ex}")


if __name__ == "__main__":
    render_weekly_history()
