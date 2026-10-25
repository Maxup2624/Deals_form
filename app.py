import json
import uuid
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="Negotiation Deal Blueprint",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {max-width: 1050px; padding-top: 2rem; padding-bottom: 3rem;}
.hero {padding: 1.4rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#102a43,#245b78); color: white; margin-bottom: 1.2rem;}
.hero h1 {color: white; margin: 0 0 .35rem 0;}
.hero p {color: #e7f1f8; margin: 0;}
div[data-testid="stForm"] {border: 1px solid #dce5ec; border-radius: 14px; padding: 1.2rem;}
.small-note {color: #5c6b73; font-size: .9rem;}
.metric-card {border: 1px solid #dce5ec; border-radius: 12px; padding: 1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🤝 Negotiation Deal Blueprint</h1>
  <p>Record your group's proposed deal terms. Submit once, then review the class-level results in the dashboard.</p>
</div>
""", unsafe_allow_html=True)

# ---------- Configuration / database ----------
def get_secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default

def get_connection():
    token = get_secret("MOTHERDUCK_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MotherDuck token is not configured. Add MOTHERDUCK_TOKEN to "
            ".streamlit/secrets.toml locally or Streamlit Community Cloud → App settings → Secrets."
        )
    database = get_secret("MOTHERDUCK_DATABASE", "my_db")
    # The token is passed as a config value, never embedded in source code.
    con = duckdb.connect("md:", config={"motherduck_token": token})
    # Create/select a database if needed; default is commonly my_db.
    if database and database.lower() != "my_db":
        con.execute(f'CREATE DATABASE IF NOT EXISTS "{database.replace(chr(34), chr(34)*2)}"')
        con.execute(f'USE "{database.replace(chr(34), chr(34)*2)}"')
    con.execute("""
        CREATE TABLE IF NOT EXISTS deal_submissions (
            submission_id VARCHAR PRIMARY KEY,
            created_at_utc TIMESTAMP,
            group_number VARCHAR,
            role VARCHAR,
            royalty_pct DOUBLE,
            cash_equity_pct DOUBLE,
            commission_pct DOUBLE,
            alternative_structure VARCHAR,
            submitter_note VARCHAR
        )
    """)
    return con

def fetch_submissions(con):
    return con.execute("""
        SELECT submission_id, created_at_utc, group_number, role,
               royalty_pct, cash_equity_pct, commission_pct,
               alternative_structure, submitter_note
        FROM deal_submissions
        ORDER BY created_at_utc DESC
    """).df()

def insert_submission(payload):
    con = get_connection()
    try:
        # submission_id is unique; duplicate browser submissions are ignored.
        con.execute("""
            INSERT INTO deal_submissions
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (submission_id) DO NOTHING
        """, [
            payload["submission_id"], payload["created_at_utc"],
            payload["group_number"], payload["role"],
            payload["royalty_pct"], payload["cash_equity_pct"],
            payload["commission_pct"], payload["alternative_structure"],
            payload["submitter_note"],
        ])
    finally:
        con.close()

def safe_count(df):
    return 0 if df is None else len(df)

# ---------- Navigation ----------
page = st.radio(
    "Choose view",
    ["Submit deal", "Instructor dashboard"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "Submit deal":
    st.subheader("Step 1 — Group setup")
    with st.form("deal_form", clear_on_submit=False):
        col1, col2 = st.columns(2)
        with col1:
            group_number = st.text_input(
                "Group number",
                placeholder="e.g., Group 7",
                help="Use the group label assigned by your instructor.",
            )
        with col2:
            role = st.selectbox("Your role", ["Founder", "Investor", "Distributor"])

        st.divider()
        st.subheader("Step 2 — Deal terms")
        st.caption("Use the sliders to record the terms your group negotiated. These percentages are independent fields and do not need to add up to 100%.")
        royalty = st.slider("Royalty (%)", min_value=0, max_value=50, value=10, step=1)
        equity = st.slider("Cash equity (%)", min_value=0, max_value=100, value=20, step=1)
        commission = st.slider("Commission (%)", min_value=0, max_value=40, value=5, step=1)
        alternative = st.text_area(
            "Alternative deal structures (optional)",
            placeholder="Describe any milestone payments, exclusivity, performance clauses, minimum guarantees, or other terms.",
            height=120,
            max_chars=3000,
        )
        note = st.text_input("Optional note (no personal or sensitive information)", max_chars=300)
        confirmed = st.checkbox("I have checked the group and deal terms before submitting.")
        submitted = st.form_submit_button("Submit Deal Blueprint", type="primary", use_container_width=True)

    if submitted:
        if not group_number.strip():
            st.error("Please enter your group number.")
        elif not confirmed:
            st.error("Please confirm the details before submitting.")
        else:
            # A stable session ID is retained after successful submission to avoid duplicate clicks/reruns.
            if "submission_id" not in st.session_state:
                st.session_state.submission_id = str(uuid.uuid4())
            payload = {
                "submission_id": st.session_state.submission_id,
                "created_at_utc": datetime.now(timezone.utc).replace(tzinfo=None),
                "group_number": group_number.strip(),
                "role": role,
                "royalty_pct": float(royalty),
                "cash_equity_pct": float(equity),
                "commission_pct": float(commission),
                "alternative_structure": alternative.strip(),
                "submitter_note": note.strip(),
            }
            with st.spinner("Saving entry… please wait."):
                try:
                    insert_submission(payload)
                    st.success("Deal Blueprint saved successfully.")
                    st.session_state.last_saved_id = payload["submission_id"]
                    st.session_state.submission_id = str(uuid.uuid4())
                    st.info("Your entry has been stored centrally. You may close this page.")
                except Exception as exc:
                    st.error("The entry could not be saved. Please try again or tell the instructor.")
                    st.code(str(exc))
                    st.caption("If this is a connection error, check the MotherDuck token and database name in your secrets.")

    st.markdown('<p class="small-note">Privacy: submit only your group label and negotiated terms. Do not enter personal, confidential, or sensitive information.</p>', unsafe_allow_html=True)

else:
    st.subheader("Instructor dashboard")
    st.write("Enter the instructor password to view responses and download the CSV.")
    dashboard_password = get_secret("DASHBOARD_PASSWORD", "")
    entered_password = st.text_input("Instructor password", type="password")
    if not dashboard_password:
        st.warning("DASHBOARD_PASSWORD is not configured in secrets. Add it before using the instructor dashboard.")
    elif entered_password and entered_password == dashboard_password:
        try:
            con = get_connection()
            try:
                df = fetch_submissions(con)
            finally:
                con.close()

            c1, c2, c3 = st.columns(3)
            c1.metric("Total submissions", safe_count(df))
            c2.metric("Groups represented", int(df["group_number"].nunique()) if not df.empty else 0)
            c3.metric("Roles represented", int(df["role"].nunique()) if not df.empty else 0)

            if df.empty:
                st.info("No submissions yet. Responses will appear here after students submit.")
            else:
                st.markdown("### Deal terms overview")
                a, b, c = st.columns(3)
                a.metric("Average royalty", f'{df["royalty_pct"].mean():.1f}%')
                b.metric("Average cash equity", f'{df["cash_equity_pct"].mean():.1f}%')
                c.metric("Average commission", f'{df["commission_pct"].mean():.1f}%')

                st.markdown("### Submissions by role")
                role_counts = df.groupby("role", as_index=False).size().rename(columns={"size": "Submissions"})
                st.bar_chart(role_counts.set_index("role"))

                st.markdown("### Deal terms by role")
                terms = df.groupby("role")[["royalty_pct", "cash_equity_pct", "commission_pct"]].mean().round(2)
                st.dataframe(terms, use_container_width=True)

                st.markdown("### All submissions")
                display_df = df.drop(columns=["submission_id"])
                st.dataframe(display_df, use_container_width=True, hide_index=True)

                csv_bytes = df.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Download all responses as CSV",
                    data=csv_bytes,
                    file_name=f"negotiation_deal_submissions_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv",
                    type="primary",
                )
        except Exception as exc:
            st.error("Could not load the dashboard data. Check the database connection and secrets.")
            st.code(str(exc))
    elif entered_password:
        st.error("Incorrect password.")
