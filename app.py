import uuid
from datetime import datetime, timezone

import duckdb
import pandas as pd
import streamlit as st
from streamlit_autorefresh import st_autorefresh

st.set_page_config(
    page_title="Jill Draeger Negotiation Simulation",
    page_icon="🤝",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ---------- Styling ----------
st.markdown("""
<style>
.block-container {max-width: 1150px; padding-top: 1.7rem; padding-bottom: 3rem;}
.hero {padding: 1.35rem 1.6rem; border-radius: 18px; background: linear-gradient(120deg,#102a43,#245b78); color: white; margin-bottom: 1.2rem;}
.hero h1 {color: white; margin: 0 0 .35rem 0;}
.hero p {color: #e7f1f8; margin: 0;}
.small-note {color: #5c6b73; font-size: .9rem;}
div[data-testid="stForm"] {border: 1px solid #dce5ec; border-radius: 14px; padding: 1.1rem;}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero">
  <h1>🤝 The $800,000 Negotiation</h1>
  <p>Jill Draeger · Jing Zhou · Jin Yang-ho | Final deal submission and live group leaderboard</p>
</div>
""", unsafe_allow_html=True)

# ---------- Configuration / MotherDuck ----------
def get_secret(key, default=None):
    try:
        return st.secrets.get(key, default)
    except Exception:
        return default


def get_connection():
    """Use the existing MotherDuck credentials/database; create only a new, additive table."""
    token = get_secret("MOTHERDUCK_TOKEN", "")
    if not token:
        raise RuntimeError(
            "MotherDuck token is not configured. Keep your existing MOTHERDUCK_TOKEN in "
            "Streamlit Community Cloud → App settings → Secrets."
        )

    database = get_secret("MOTHERDUCK_DATABASE", "my_db")
    con = duckdb.connect("md:", config={"motherduck_token": token})
    if database and database.lower() != "my_db":
        escaped_database = database.replace('"', '""')
        con.execute(f'CREATE DATABASE IF NOT EXISTS "{escaped_database}"')
        con.execute(f'USE "{escaped_database}"')

    # This is a NEW table. The existing deal_submissions table is not altered or deleted.
    con.execute("""
        CREATE TABLE IF NOT EXISTS jill_draeger_deals (
            group_number VARCHAR PRIMARY KEY,
            created_at_utc TIMESTAMP,
            yang_prepayment DOUBLE,
            zhou_deferred DOUBLE,
            yang_equity_pct DOUBLE,
            zhou_equity_pct DOUBLE,
            zhou_royalty_pct DOUBLE,
            all_three_accept BOOLEAN,
            valid_deal BOOLEAN,
            jill_score INTEGER,
            zhou_score INTEGER,
            yang_score INTEGER,
            group_score INTEGER,
            rationale VARCHAR
        )
    """)
    return con


def fetch_deals(con):
    return con.execute("""
        SELECT group_number, created_at_utc, yang_prepayment, zhou_deferred,
               yang_equity_pct, zhou_equity_pct, zhou_royalty_pct,
               all_three_accept, valid_deal, jill_score, zhou_score,
               yang_score, group_score, rationale
        FROM jill_draeger_deals
    """).df()


def deal_is_valid(prepayment, deferred, yang_equity, zhou_equity, royalty, accepted):
    allowed = (
        prepayment in [0, 400000, 800000]
        and deferred in [0, 400000, 800000]
        and deferred == 800000 - prepayment
        and yang_equity in [0, 5, 10, 15]
        and zhou_equity in [0, 5, 10]
        and yang_equity + zhou_equity <= 20
        and royalty in [0, 2, 4, 6]
        and accepted is True
    )
    return bool(allowed)


def score_deal(prepayment, yang_equity, zhou_equity, royalty, accepted):
    """Apply the supplied role scorecards exactly; invalid/unsigned deals score zero for everyone."""
    deferred = 800000 - prepayment
    valid = deal_is_valid(prepayment, deferred, yang_equity, zhou_equity, royalty, accepted)
    if not valid:
        return valid, 0, 0, 0, 0

    # Jill: valid deal + total equity + Zhou royalty + Yang cash prepayment
    total_equity = yang_equity + zhou_equity
    jill_equity_points = 30 if total_equity == 0 else (20 if total_equity <= 10 else 5)
    jill_royalty_points = {0: 25, 2: 18, 4: 8, 6: 0}[royalty]
    jill_cash_points = {800000: 15, 400000: 8, 0: 0}[prepayment]
    jill_score = 40 + jill_equity_points + jill_royalty_points + jill_cash_points

    # Zhou: cash paid upfront + additional royalty + own equity
    zhou_cash_points = {800000: 40, 400000: 20, 0: 0}[prepayment]
    zhou_royalty_points = {0: 0, 2: 12, 4: 24, 6: 35}[royalty]
    zhou_equity_points = {0: 0, 5: 12, 10: 25}[zhou_equity]
    zhou_score = zhou_cash_points + zhou_royalty_points + zhou_equity_points

    # Yang: smaller prepayment + own equity + lower Zhou royalty
    yang_cash_points = {0: 30, 400000: 15, 800000: 0}[prepayment]
    yang_equity_points = {0: 0, 5: 15, 10: 30, 15: 45}[yang_equity]
    yang_royalty_points = {0: 20, 2: 12, 4: 5, 6: 0}[royalty]
    yang_score = yang_cash_points + yang_equity_points + yang_royalty_points

    return valid, jill_score, zhou_score, yang_score, jill_score + zhou_score + yang_score


def save_deal(payload):
    con = get_connection()
    try:
        # One final submission per group. The primary key prevents duplicate group entries.
        con.execute("""
            INSERT INTO jill_draeger_deals
            (group_number, created_at_utc, yang_prepayment, zhou_deferred,
             yang_equity_pct, zhou_equity_pct, zhou_royalty_pct,
             all_three_accept, valid_deal, jill_score, zhou_score,
             yang_score, group_score, rationale)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (group_number) DO NOTHING
        """, [
            payload["group_number"], payload["created_at_utc"],
            payload["yang_prepayment"], payload["zhou_deferred"],
            payload["yang_equity_pct"], payload["zhou_equity_pct"],
            payload["zhou_royalty_pct"], payload["all_three_accept"],
            payload["valid_deal"], payload["jill_score"], payload["zhou_score"],
            payload["yang_score"], payload["group_score"], payload["rationale"],
        ])
        inserted = con.execute(
            "SELECT COUNT(*) FROM jill_draeger_deals WHERE group_number = ?",
            [payload["group_number"]],
        ).fetchone()[0]
        return inserted == 1
    finally:
        con.close()


def get_ranked_deals(df):
    if df.empty:
        return df.copy()
    ranked = df.sort_values(["group_score", "group_number"], ascending=[False, True]).copy()
    ranked["Rank"] = ranked["group_score"].rank(method="min", ascending=False).astype(int)
    ranked["Status"] = ranked["valid_deal"].map({True: "Valid deal", False: "No valid deal"})
    return ranked


# ---------- Role cards: supplied activity wording summarized for on-screen use ----------
ROLE_CARDS = {
    "Jill Draeger — Entrepreneur": {
        "objective": "Get watches into production before the deadline without giving away too much upside.",
        "private": "You do not have the $800,000 production cash. Keep new equity and ongoing royalties low, but losing the license is worse. You suspect Yang might finance the whole first order. You need both partners to accept the terms.",
        "scorecard": [
            "Any valid, fully financed deal signed by all three: +40",
            "Total new equity: 0% = +30; 5–10% = +20; 15–20% = +5",
            "Extra Zhou royalty: 0% = +25; 2% = +18; 4% = +8; 6% = +0",
            "Yang prepayment: $800,000 = +15; $400,000 = +8; $0 = +0",
        ],
    },
    "Jing Zhou — Manufacturer": {
        "objective": "Protect Tiger Electronics from financing risk while earning a return for any credit you extend.",
        "private": "Your quote is about $20 per watch. You normally insist on full payment before production. You may defer some or all payment if compensation is attractive. You are nervous because Olympic souvenirs have an expiration date.",
        "scorecard": [
            "Cash paid upfront: $800,000 = +40; $400,000 = +20; $0 = +0",
            "Extra Zhou royalty: 0% = +0; 2% = +12; 4% = +24; 6% = +35",
            "New Zhou equity: 0% = +0; 5% = +12; 10% = +25",
        ],
    },
    "Jin Yang-ho — Retail Partner": {
        "objective": "Help make the launch possible while getting enough upside for the cash you risk.",
        "private": "You already support Jill through Moon Pak and JYD. You are considering prepaying for inventory but do not want cash at risk without additional ownership. You can afford up to $800,000 in this simulation, but strongly prefer a smaller commitment. Your business still has to sell the merchandise.",
        "scorecard": [
            "Yang prepayment: $0 = +30; $400,000 = +15; $800,000 = +0",
            "New Yang equity: 0% = +0; 5% = +15; 10% = +30; 15% = +45",
            "Extra Zhou royalty: 0% = +20; 2% = +12; 4% = +5; 6% = +0",
        ],
    },
}

# ---------- Student entry gate ----------
# Role and group are selected once per Streamlit browser session. No role selector is
# rendered anywhere after entry, so students cannot switch roles using the app controls.
if "participant_group" not in st.session_state or "participant_role" not in st.session_state:
    st.subheader("Enter the negotiation room")
    st.write("Enter your group number and select your assigned role. Your selection will remain fixed for this browser session.")
    with st.form("participant_entry_form", clear_on_submit=False):
        entry_group = st.text_input("Group number", placeholder="e.g., 7 or Group 7", max_chars=40)
        entry_role = st.selectbox("Your assigned role", list(ROLE_CARDS.keys()))
        enter_room = st.form_submit_button("Enter negotiation room", type="primary", use_container_width=True)
    if enter_room:
        if not entry_group.strip():
            st.error("Enter your group number before continuing.")
        else:
            st.session_state["participant_group"] = entry_group.strip()
            st.session_state["participant_role"] = entry_role
            st.rerun()
    st.stop()

participant_group = st.session_state["participant_group"]
role = st.session_state["participant_role"]
st.info(f"**Current participant:** {participant_group}  ·  **Role:** {role}")

# ---------- Navigation ----------
page = st.radio(
    "Choose view",
    ["Role instructions", "Submit final deal", "Live leaderboard", "Instructor dashboard"],
    horizontal=True,
    label_visibility="collapsed",
)

if page == "Role instructions":
    st.subheader("Your role instructions")
    st.warning("Your role is fixed for this browser session. Keep your role card and scorecard confidential from the other negotiators.")
    card = ROLE_CARDS[role]
    st.markdown(f"### Objective\n{card['objective']}")
    st.markdown("### Your private information")
    st.write(card["private"])
    st.markdown("### Your confidential scorecard")
    for item in card["scorecard"]:
        st.markdown(f"- {item}")
    st.caption("The scorecards are classroom simulation mechanics, not facts from the original case.")
    with st.expander("Common negotiation facts and rules"):
        st.markdown("""
        - The first order is 40,000 watches at approximately $20 each: $800,000 total.
        - Yang prepayment options: $0, $400,000, or $800,000.
        - Zhou's deferred amount must equal $800,000 minus Yang's prepayment.
        - New equity to Yang: 0%, 5%, 10%, or 15%; new equity to Zhou: 0%, 5%, or 10%.
        - Combined new equity cannot exceed 20%.
        - Additional royalty to Zhou: 0%, 2%, 4%, or 6% of Jill's wholesale sales.
        - A successful deal requires all three parties to accept. Existing case arrangements remain unchanged.
        """)

elif page == "Submit final deal":
    st.subheader("Submit one final deal per group")
    st.write("Agree the terms together before submitting. Zhou's deferral is calculated automatically as $800,000 minus Yang's prepayment.")

    with st.form("final_deal_form", clear_on_submit=False):
        st.text_input("Group number", value=participant_group, disabled=True)
        prepayment_label = st.selectbox("Yang's cash prepayment", ["$0", "$400,000", "$800,000"], index=1)
        prepayment_map = {"$0": 0, "$400,000": 400000, "$800,000": 800000}
        prepayment = prepayment_map[prepayment_label]
        deferred = 800000 - prepayment
        st.info(f"Zhou's deferred payment: **${deferred:,.0f}** | Total financing: **$800,000**")

        c1, c2 = st.columns(2)
        with c1:
            yang_equity = st.selectbox("New equity to Yang", [0, 5, 10, 15], format_func=lambda x: f"{x}%")
        with c2:
            zhou_equity = st.selectbox("New equity to Zhou", [0, 5, 10], format_func=lambda x: f"{x}%")
        royalty = st.selectbox("Additional royalty to Zhou (% of Jill's wholesale sales)", [0, 2, 4, 6], format_func=lambda x: f"{x}%")
        accepted_label = st.radio("Have all three parties accepted the deal?", ["Yes", "No"], horizontal=True)
        rationale = st.text_area("Why did your group choose this deal? (one or two sentences)", max_chars=1000)
        confirmed = st.checkbox("We confirm this is our group's final agreed submission.")
        submit = st.form_submit_button("Submit final deal", type="primary", use_container_width=True)

    if submit:
        normalized_group = str(st.session_state["participant_group"]).strip()
        accepted = accepted_label == "Yes"
        if not normalized_group:
            st.error("Enter your group number.")
        elif not confirmed:
            st.error("Confirm that this is your group's final submission.")
        else:
            valid, jill_score, zhou_score, yang_score, group_score = score_deal(
                prepayment, yang_equity, zhou_equity, royalty, accepted
            )
            payload = {
                "group_number": normalized_group,
                "created_at_utc": datetime.now(timezone.utc).replace(tzinfo=None),
                "yang_prepayment": prepayment,
                "zhou_deferred": deferred,
                "yang_equity_pct": float(yang_equity),
                "zhou_equity_pct": float(zhou_equity),
                "zhou_royalty_pct": float(royalty),
                "all_three_accept": accepted,
                "valid_deal": valid,
                "jill_score": jill_score,
                "zhou_score": zhou_score,
                "yang_score": yang_score,
                "group_score": group_score,
                "rationale": rationale.strip(),
            }
            try:
                with st.spinner("Saving your group's deal..."):
                    saved = save_deal(payload)
                if saved:
                    st.session_state["submitted_group"] = normalized_group
                    st.success("Your group's deal has been recorded.")
                    if valid:
                        st.info(f"Current combined score: **{group_score}**. Open the Live leaderboard to see your current position.")
                    else:
                        st.warning("This submission is not a valid signed deal, so all three role scores are 0 under the activity rules.")
                    st.caption("One submission is allowed per group. Contact the instructor if a correction is required.")
                else:
                    st.error("A submission already exists for this group. Contact the instructor if it needs correction.")
            except Exception as exc:
                st.error("Could not save the deal. Check the existing MotherDuck connection and table permissions.")
                st.code(str(exc))

elif page == "Live leaderboard":
    # Auto-refresh so ranks can change after other groups submit without a manual reload.
    st_autorefresh(interval=10000, key="leaderboard_autorefresh")
    st.subheader("Live group leaderboard")
    st.caption("Updates automatically about every 10 seconds. Rankings are provisional until all groups have submitted. Ties share the same rank.")
    try:
        con = get_connection()
        try:
            deals = fetch_deals(con)
        finally:
            con.close()
        if deals.empty:
            st.info("No groups have submitted a final deal yet.")
        else:
            ranked = get_ranked_deals(deals)
            submitted_group = st.session_state.get("submitted_group", "")
            if submitted_group:
                own = ranked[ranked["group_number"].astype(str).str.casefold() == str(submitted_group).casefold()]
                if not own.empty:
                    own_row = own.iloc[0]
                    st.success(f"Your group ({submitted_group}) is currently ranked **#{int(own_row['Rank'])}** with **{int(own_row['group_score'])} points**.")
            st.markdown("### Current standings")
            public = ranked[["Rank", "group_number", "group_score", "Status"]].rename(columns={
                "group_number": "Group", "group_score": "Combined score"
            })
            public["Combined score"] = public["Combined score"].astype(int)
            st.dataframe(public, use_container_width=True, hide_index=True)
            st.caption(f"{len(deals)} group(s) have submitted. Private role-by-role score breakdowns are not shown on the student leaderboard.")
    except Exception as exc:
        st.error("Could not load the leaderboard. Check the MotherDuck connection and table permissions.")
        st.code(str(exc))

else:
    st.subheader("Instructor dashboard")
    st.write("Enter the existing instructor dashboard password to view detailed submissions and export results.")
    dashboard_password = get_secret("DASHBOARD_PASSWORD", "")
    entered_password = st.text_input("Instructor password", type="password")
    if not dashboard_password:
        st.warning("DASHBOARD_PASSWORD is not configured in Streamlit secrets.")
    elif entered_password and entered_password == dashboard_password:
        st_autorefresh(interval=15000, key="instructor_autorefresh")
        try:
            con = get_connection()
            try:
                deals = fetch_deals(con)
            finally:
                con.close()
            ranked = get_ranked_deals(deals)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Groups submitted", len(deals))
            c2.metric("Valid signed deals", int(deals["valid_deal"].sum()) if not deals.empty else 0)
            c3.metric("Highest group score", int(deals["group_score"].max()) if not deals.empty else 0)
            c4.metric("Average group score", f"{deals['group_score'].mean():.1f}" if not deals.empty else "—")

            if deals.empty:
                st.info("No submissions yet.")
            else:
                st.markdown("### Ranked results — instructor only")
                instructor_view = ranked[[
                    "Rank", "group_number", "valid_deal", "yang_prepayment", "zhou_deferred",
                    "yang_equity_pct", "zhou_equity_pct", "zhou_royalty_pct",
                    "jill_score", "zhou_score", "yang_score", "group_score", "all_three_accept", "rationale", "created_at_utc"
                ]].rename(columns={
                    "group_number": "Group", "valid_deal": "Valid deal", "yang_prepayment": "Yang prepayment ($)",
                    "zhou_deferred": "Zhou deferred ($)", "yang_equity_pct": "Yang equity (%)",
                    "zhou_equity_pct": "Zhou equity (%)", "zhou_royalty_pct": "Zhou royalty (%)",
                    "jill_score": "Jill score", "zhou_score": "Zhou score", "yang_score": "Yang score",
                    "group_score": "Combined score", "all_three_accept": "All accepted", "rationale": "Rationale",
                    "created_at_utc": "Submitted (UTC)"
                })
                st.dataframe(instructor_view, use_container_width=True, hide_index=True)
                csv_bytes = instructor_view.to_csv(index=False).encode("utf-8-sig")
                st.download_button(
                    "Download ranked results as CSV", data=csv_bytes,
                    file_name=f"jill_draeger_results_{datetime.now().strftime('%Y%m%d_%H%M')}.csv",
                    mime="text/csv", type="primary"
                )
                st.warning("Reset or correction operations are intentionally not exposed on the student app. Correct a submission only through an instructor-controlled process.")
        except Exception as exc:
            st.error("Could not load instructor results. Check the MotherDuck connection and secrets.")
            st.code(str(exc))
    elif entered_password:
        st.error("Incorrect password.")

st.markdown("---")
st.markdown('<p class="small-note">Use one final submission per group. Role selection is fixed for the current browser session. The original deal_submissions table and your existing Streamlit secrets are left unchanged. The new simulation stores its results in a separate jill_draeger_deals table.</p>', unsafe_allow_html=True)
