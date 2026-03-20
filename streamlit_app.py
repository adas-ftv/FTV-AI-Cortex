import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go

# Page config
st.set_page_config(
    page_title="Sourcing Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Snowflake connection
# In Snowflake Streamlit, get_active_session() provides direct access
@st.cache_resource
def get_snowflake_session():
    from snowflake.snowpark.context import get_active_session
    return get_active_session()

session = get_snowflake_session()

# Title and description
st.title("🎯 Sourcing Dashboard")
st.markdown("Net new company sourcing metrics and attribution analysis")

# Sidebar filters
st.sidebar.header("Filters")

# Time period selector - MTD/L3M/YTD
time_metric = st.sidebar.radio(
    "Time Metric",
    ["MTD", "L3M", "YTD"],
    horizontal=True
)

# Map time metrics to column suffixes
metric_suffix = f"_{time_metric}"

# Get unique teams, titles, sectors, and locations from summary query
@st.cache_data(ttl=3600)
def get_filter_options():
    try:
        teams_query = "SELECT DISTINCT PRIMARY_TEAM FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES ORDER BY PRIMARY_TEAM"
        titles_query = "SELECT DISTINCT TITLE FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES ORDER BY TITLE"
        sectors_query = "SELECT DISTINCT SECTOR FROM YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER WHERE DP_IS_ACTIVE = TRUE AND SECTOR IS NOT NULL ORDER BY SECTOR"
        locations_query = "SELECT DISTINCT LOCATION FROM DBT.DEV.FACT_CONFERENCE WHERE LOCATION IS NOT NULL ORDER BY LOCATION"

        teams = session.sql(teams_query).to_pandas()["PRIMARY_TEAM"].tolist()
        titles = session.sql(titles_query).to_pandas()["TITLE"].tolist()

        try:
            sectors = session.sql(sectors_query).to_pandas()["SECTOR"].tolist()
        except:
            sectors = []

        try:
            locations = session.sql(locations_query).to_pandas()["LOCATION"].tolist()
        except:
            locations = []

        return teams, titles, sectors, locations
    except:
        return [], [], [], []

teams, titles, sectors, locations = get_filter_options()

# Team filter
selected_teams = st.sidebar.multiselect(
    "Teams",
    teams,
    default=teams[:3] if teams else []
)

# Title filter
selected_titles = st.sidebar.multiselect(
    "Titles",
    titles,
    default=titles if titles else []
)

# Sector filter
selected_sectors = st.sidebar.multiselect(
    "Sectors",
    sectors,
    default=sectors[:3] if sectors else []
)

# Location filter
selected_locations = st.sidebar.multiselect(
    "Locations",
    locations,
    default=locations[:3] if locations else []
)

# Build WHERE clause for filters with sector/location joins
def build_filter_clause(table_alias=""):
    filters = []
    prefix = f"{table_alias}." if table_alias else ""
    if selected_teams:
        team_list = "', '".join([t.replace("'", "''") for t in selected_teams])
        filters.append(f"{prefix}PRIMARY_TEAM IN ('{team_list}')")
    if selected_titles:
        title_list = "', '".join([t.replace("'", "''") for t in selected_titles])
        filters.append(f"{prefix}TITLE IN ('{title_list}')")
    return " AND ".join(filters) if filters else "1=1"

def build_sector_location_filters():
    """Build filter clause for sector/location joins to __USER and FACT_CONFERENCE"""
    filters = []
    if selected_sectors:
        sector_list = "', '".join([s.replace("'", "''") for s in selected_sectors])
        filters.append(f"u.SECTOR IN ('{sector_list}')")
    if selected_locations:
        location_list = "', '".join([l.replace("'", "''") for l in selected_locations])
        filters.append(f"fc.LOCATION IN ('{location_list}')")
    return " AND ".join(filters) if filters else "1=1"

# Initialize session state for drill-downs
if "drill_user" not in st.session_state:
    st.session_state.drill_user = None
if "drill_metric" not in st.session_state:
    st.session_state.drill_metric = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# Drill-down dialogs
@st.dialog("Interaction Details")
def show_interaction_detail(user_name, period):
    """Show detailed interactions for a user"""
    detail_query = f"""
    SELECT
        fi.DT,
        fi.ACTIVITY_TYPE,
        fi.SUBJECT,
        fi.NOTES
    FROM DBT.DEV.FACT_INTERACTION fi
    JOIN DBT.DEV.BRIDGE_INTERACTION_USER bu ON fi.ID = bu.INTERACTION_ID
    JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
    WHERE LOWER(u.FULLNAME) = LOWER('{user_name.replace("'", "''")}')
    """

    if period == "MTD":
        detail_query += " AND fi.DT >= DATE_TRUNC('MONTH', CURRENT_DATE())"
    elif period == "L3M":
        detail_query += " AND fi.DT >= DATEADD('MONTH', -3, CURRENT_DATE())"
    elif period == "YTD":
        detail_query += " AND fi.DT >= DATE_TRUNC('YEAR', CURRENT_DATE())"

    detail_query += " ORDER BY fi.DT DESC"

    try:
        df_detail = session.sql(detail_query).to_pandas()
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading details: {str(e)}")

@st.dialog("Conference Details")
def show_conference_detail(user_name, period):
    """Show detailed conferences for a user"""
    detail_query = f"""
    SELECT
        fc.STARTDATE,
        fc.NAME,
        fc.LOCATION
    FROM DBT.DEV.FACT_CONFERENCE fc
    JOIN DBT.DEV.BRIDGE_CONFERENCE_USER bu ON fc.ID = bu.CONFERENCE_ID
    JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
    WHERE LOWER(u.FULLNAME) = LOWER('{user_name.replace("'", "''")}')
    """

    if period == "MTD":
        detail_query += " AND fc.STARTDATE >= DATE_TRUNC('MONTH', CURRENT_DATE())"
    elif period == "L3M":
        detail_query += " AND fc.STARTDATE >= DATEADD('MONTH', -3, CURRENT_DATE())"
    elif period == "YTD":
        detail_query += " AND fc.STARTDATE >= DATE_TRUNC('YEAR', CURRENT_DATE())"

    detail_query += " ORDER BY fc.STARTDATE DESC"

    try:
        df_detail = session.sql(detail_query).to_pandas()
        st.dataframe(df_detail, use_container_width=True, hide_index=True)
    except Exception as e:
        st.error(f"Error loading details: {str(e)}")

# Main metrics row
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.metric(
        label="Net New Companies",
        value="—",
        help="From SOURCING_METRICS_NET_NEW_COMPANIES"
    )

with col2:
    st.metric(
        label="Active Users",
        value="—",
        help="From __USER"
    )

with col3:
    st.metric(
        label="Interactions",
        value="—",
        help="From FACT_INTERACTION"
    )

with col4:
    st.metric(
        label="Conferences",
        value="—",
        help="From FACT_CONFERENCE"
    )

# Main dashboard sections
tab1, tab2, tab3, tab4, tab5, tab6, tab7 = st.tabs(
    ["📈 Summary", "👥 User Attribution", "💬 Interactions", "🎤 Conferences", "💼 Active Deals", "📊 Trends", "🤖 Ask"]
)

# ===== TAB 1: SUMMARY =====
with tab1:
    st.subheader("Executive Summary")

    summary_query = f"""
    SELECT
        USER_NAME,
        PRIMARY_TEAM,
        TITLE,
        NET_NEW_COMPANIES_MTD, NET_NEW_COMPANIES_L3M, NET_NEW_COMPANIES_YTD,
        OUTREACH_MTD, OUTREACH_L3M, OUTREACH_YTD,
        PROSPECT_INTERACTIONS_MTD, PROSPECT_INTERACTIONS_L3M, PROSPECT_INTERACTIONS_YTD,
        PASSED_LEADS_MTD, PASSED_LEADS_L3M, PASSED_LEADS_YTD,
        CONFERENCES_ATTENDED_MTD, CONFERENCES_ATTENDED_L3M, CONFERENCES_ATTENDED_YTD,
        ACTIVE_DEALS_CURRENT, ACTIVE_DEALS_L3M, ACTIVE_DEALS_YTD
    FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES
    WHERE {build_filter_clause()}
    ORDER BY NET_NEW_COMPANIES_YTD DESC
    """

    try:
        df_summary = session.sql(summary_query).to_pandas()

        # Top metrics by category
        col1, col2, col3 = st.columns(3)
        with col1:
            top_companies = df_summary.nlargest(5, f"NET_NEW_COMPANIES{metric_suffix}")
            st.subheader("🏆 Top 5 Net New Companies")
            st.dataframe(top_companies[["USER_NAME", "PRIMARY_TEAM", f"NET_NEW_COMPANIES{metric_suffix}"]], use_container_width=True, hide_index=True)

        with col2:
            top_outreach = df_summary.nlargest(5, f"OUTREACH{metric_suffix}")
            st.subheader("📞 Top 5 Outreach")
            st.dataframe(top_outreach[["USER_NAME", "PRIMARY_TEAM", f"OUTREACH{metric_suffix}"]], use_container_width=True, hide_index=True)

        with col3:
            top_hqt = df_summary.nlargest(5, f"PASSED_LEADS{metric_suffix}")
            st.subheader("✅ Top 5 Passed Leads")
            st.dataframe(top_hqt[["USER_NAME", "PRIMARY_TEAM", f"PASSED_LEADS{metric_suffix}"]], use_container_width=True, hide_index=True)

        st.divider()

        # Team leaderboard
        st.subheader(f"Performance by Team ({time_metric})")
        team_summary = df_summary.groupby("PRIMARY_TEAM").agg({
            f"NET_NEW_COMPANIES{metric_suffix}": "sum",
            f"OUTREACH{metric_suffix}": "sum",
            f"PROSPECT_INTERACTIONS{metric_suffix}": "sum",
            f"PASSED_LEADS{metric_suffix}": "sum"
        }).sort_values(f"NET_NEW_COMPANIES{metric_suffix}", ascending=False)

        fig = px.bar(team_summary, title=f"Net New Companies by Team ({time_metric})", labels={"value": "Count", "index": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading summary data: {str(e)}")

# ===== TAB 2: USER ATTRIBUTION & HQT =====
with tab2:
    st.subheader("User & HQT Attribution")

    hqt_query = f"""
    WITH user_id_map AS (
        SELECT DISTINCT USER_ID, USER_EMAIL
        FROM YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__USER_OWNERTEAM
        WHERE USER_EMAIL IS NOT NULL AND DP_IS_ACTIVE = TRUE
    ),
    approved_entries AS (
        SELECT h.ID, h.APPROVEDDATE
        FROM YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY h
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__CHOICE_STATUS cs ON h.ID = cs.HQTENTRY_ID_BASE AND cs.DP_IS_ACTIVE = TRUE
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY_STATUS_OPTIONS cs_opt ON cs.HQTENTRY_STATUS_OPTIONS_ID = cs_opt.ID AND cs_opt.NAME = 'Approved'
        WHERE h.APPROVEDDATE IS NOT NULL
    ),
    hqt_attribution AS (
        SELECT ae.ID, COALESCE(ot.USER_EMAIL, uid.USER_EMAIL) AS USER_EMAIL, ae.APPROVEDDATE
        FROM approved_entries ae
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__USER_OWNERTEAM ot ON ae.ID = ot.HQTENTRY_ID_BASE AND ot.DP_IS_ACTIVE = TRUE
        LEFT JOIN user_id_map uid ON ot.USER_ID = uid.USER_ID
    ),
    hqt_by_user AS (
        SELECT
            u.FULLNAME AS USER_NAME,
            COUNT(DISTINCT CASE WHEN ha.APPROVEDDATE >= DATE_TRUNC('MONTH', CURRENT_DATE()) THEN ha.ID END) AS HQT_APPROVED_MTD,
            COUNT(DISTINCT CASE WHEN ha.APPROVEDDATE >= DATEADD('MONTH', -3, CURRENT_DATE()) THEN ha.ID END) AS HQT_APPROVED_L3M,
            COUNT(DISTINCT CASE WHEN ha.APPROVEDDATE >= DATE_TRUNC('YEAR', CURRENT_DATE()) THEN ha.ID END) AS HQT_APPROVED_YTD
        FROM YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u
        JOIN hqt_attribution ha ON u.EMAIL = ha.USER_EMAIL
        WHERE u.DP_IS_ACTIVE = TRUE
        GROUP BY u.FULLNAME
    )
    SELECT
        sm.USER_NAME,
        sm.PRIMARY_TEAM,
        sm.TITLE,
        sm.NET_NEW_COMPANIES_MTD,    sm.NET_NEW_COMPANIES_L3M,    sm.NET_NEW_COMPANIES_YTD,
        sm.CONFERENCES_ATTENDED_MTD, sm.CONFERENCES_ATTENDED_L3M, sm.CONFERENCES_ATTENDED_YTD,
        sm.OUTREACH_MTD,             sm.OUTREACH_L3M,             sm.OUTREACH_YTD,
        sm.PROSPECT_INTERACTIONS_MTD, sm.PROSPECT_INTERACTIONS_L3M, sm.PROSPECT_INTERACTIONS_YTD,
        sm.PASSED_LEADS_MTD,         sm.PASSED_LEADS_L3M,         sm.PASSED_LEADS_YTD,
        sm.ACTIVE_DEALS_CURRENT,     sm.ACTIVE_DEALS_L3M,         sm.ACTIVE_DEALS_YTD,
        COALESCE(hu.HQT_APPROVED_MTD, 0) AS HQT_APPROVED_MTD,
        COALESCE(hu.HQT_APPROVED_L3M, 0) AS HQT_APPROVED_L3M,
        COALESCE(hu.HQT_APPROVED_YTD, 0) AS HQT_APPROVED_YTD
    FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES sm
    LEFT JOIN hqt_by_user hu ON sm.USER_NAME = hu.USER_NAME
    WHERE {build_filter_clause('sm')}
    ORDER BY HQT_APPROVED_YTD DESC
    """

    try:
        df_hqt = session.sql(hqt_query).to_pandas()

        # Display top metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", len(df_hqt))
        with col2:
            st.metric(f"Total HQT {time_metric}", int(df_hqt[f"HQT_APPROVED{metric_suffix}"].sum()))
        with col3:
            st.metric(f"Avg HQT per User {time_metric}", round(df_hqt[f"HQT_APPROVED{metric_suffix}"].mean(), 1))

        st.divider()

        # User details table
        st.subheader("User Performance Summary")
        st.dataframe(df_hqt, use_container_width=True)

        # HQT by team
        st.subheader(f"HQT Approved by Team ({time_metric})")
        team_hqt = df_hqt.groupby("PRIMARY_TEAM")[f"HQT_APPROVED{metric_suffix}"].sum().sort_values(ascending=False)
        fig = px.bar(team_hqt, title=f"HQT Approvals by Team ({time_metric})", labels={"value": "HQT Count", "index": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading HQT data: {str(e)}")

# ===== TAB 3: INTERACTIONS =====
with tab3:
    st.subheader("Interaction Analytics")

    interactions_query = f"""
    WITH interaction_data AS (
        SELECT
            bu.USER_ID,
            u.FULLNAME AS USER_NAME,
            u.EMAIL,
            fi.ID AS INTERACTION_ID,
            fi.DT,
            fi.SUBJECT,
            fi.NOTES,
            fi.ACTIVITY_TYPE,
            CASE
                WHEN fi.ACTIVITY_TYPE IN ('Email', 'LinkedIn InMail', 'Text Message', 'Voicemail')
                    THEN 'Outreach'
                WHEN fi.ACTIVITY_TYPE IN ('Call', 'Meeting', 'Setup Call/Meeting for PVP')
                    THEN 'Prospect Interactions'
                WHEN fi.ACTIVITY_TYPE = 'Passed Lead'
                    THEN 'Passed Leads'
                ELSE 'Other'
            END AS INTERACTION_CLASS
        FROM DBT.DEV.FACT_INTERACTION fi
        JOIN DBT.DEV.BRIDGE_INTERACTION_USER bu ON fi.ID = bu.INTERACTION_ID
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
        WHERE u.DP_IS_ACTIVE = TRUE
    ),
    user_summary AS (
        SELECT
            sm.USER_NAME,
            sm.PRIMARY_TEAM,
            sm.TITLE,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Outreach' AND id.DT >= DATE_TRUNC('MONTH', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS OUTREACH_MTD,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Outreach' AND id.DT >= DATEADD('MONTH', -3, CURRENT_DATE()) THEN id.INTERACTION_ID END) AS OUTREACH_L3M,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Outreach' AND id.DT >= DATE_TRUNC('YEAR', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS OUTREACH_YTD,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Prospect Interactions' AND id.DT >= DATE_TRUNC('MONTH', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PROSPECT_INTERACTIONS_MTD,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Prospect Interactions' AND id.DT >= DATEADD('MONTH', -3, CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PROSPECT_INTERACTIONS_L3M,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Prospect Interactions' AND id.DT >= DATE_TRUNC('YEAR', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PROSPECT_INTERACTIONS_YTD,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Passed Leads' AND id.DT >= DATE_TRUNC('MONTH', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PASSED_LEADS_MTD,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Passed Leads' AND id.DT >= DATEADD('MONTH', -3, CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PASSED_LEADS_L3M,
            COUNT(DISTINCT CASE WHEN id.INTERACTION_CLASS = 'Passed Leads' AND id.DT >= DATE_TRUNC('YEAR', CURRENT_DATE()) THEN id.INTERACTION_ID END) AS PASSED_LEADS_YTD
        FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES sm
        LEFT JOIN interaction_data id ON LOWER(sm.USER_NAME) = LOWER(id.USER_NAME)
        WHERE {build_filter_clause('sm')}
        GROUP BY sm.USER_NAME, sm.PRIMARY_TEAM, sm.TITLE
    )
    SELECT * FROM user_summary
    ORDER BY PROSPECT_INTERACTIONS_YTD DESC
    """

    try:
        df_interactions = session.sql(interactions_query).to_pandas()

        # Three metric cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"Total Outreach {time_metric}", int(df_interactions[f"OUTREACH{metric_suffix}"].sum()))
        with col2:
            st.metric(f"Total Prospect Interactions {time_metric}", int(df_interactions[f"PROSPECT_INTERACTIONS{metric_suffix}"].sum()))
        with col3:
            st.metric(f"Total Passed Leads {time_metric}", int(df_interactions[f"PASSED_LEADS{metric_suffix}"].sum()))

        st.divider()

        # Interaction details table with drill-down
        st.subheader("Interaction Summary by User")
        selected_interaction_user = st.selectbox(
            "Select a user to drill down:",
            [""] + df_interactions["USER_NAME"].tolist(),
            key="interaction_selectbox"
        )
        if selected_interaction_user:
            if st.button("View Details", key="interaction_detail_btn"):
                show_interaction_detail(selected_interaction_user, time_metric)

        st.dataframe(df_interactions, use_container_width=True)

        # Interactions by type
        st.subheader(f"Interactions by Type ({time_metric})")
        interaction_types = pd.DataFrame({
            'Type': ['Outreach', 'Prospect Interactions', 'Passed Leads'],
            'Count': [
                df_interactions[f"OUTREACH{metric_suffix}"].sum(),
                df_interactions[f"PROSPECT_INTERACTIONS{metric_suffix}"].sum(),
                df_interactions[f"PASSED_LEADS{metric_suffix}"].sum()
            ]
        })
        fig = px.pie(interaction_types, values='Count', names='Type', title=f"Interactions by Type ({time_metric})")
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading interactions: {str(e)}")

# ===== TAB 4: CONFERENCES =====
with tab4:
    st.subheader("Conference Sourcing")

    conferences_query = f"""
    WITH conference_data AS (
        SELECT
            bu.USER_ID,
            u.FULLNAME AS USER_NAME,
            u.EMAIL,
            fc.ID AS CONFERENCE_ID,
            fc.STARTDATE,
            fc.NAME,
            fc.LOCATION
        FROM DBT.DEV.FACT_CONFERENCE fc
        JOIN DBT.DEV.BRIDGE_CONFERENCE_USER bu ON fc.ID = bu.CONFERENCE_ID
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
        WHERE u.DP_IS_ACTIVE = TRUE
    ),
    user_conferences AS (
        SELECT
            sm.USER_NAME,
            sm.PRIMARY_TEAM,
            sm.TITLE,
            COUNT(DISTINCT CASE WHEN cd.STARTDATE >= DATE_TRUNC('MONTH', CURRENT_DATE()) THEN cd.CONFERENCE_ID END) AS CONFERENCES_ATTENDED_MTD,
            COUNT(DISTINCT CASE WHEN cd.STARTDATE >= DATEADD('MONTH', -3, CURRENT_DATE()) THEN cd.CONFERENCE_ID END) AS CONFERENCES_ATTENDED_L3M,
            COUNT(DISTINCT CASE WHEN cd.STARTDATE >= DATE_TRUNC('YEAR', CURRENT_DATE()) THEN cd.CONFERENCE_ID END) AS CONFERENCES_ATTENDED_YTD
        FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES sm
        LEFT JOIN conference_data cd ON LOWER(sm.USER_NAME) = LOWER(cd.USER_NAME)
        WHERE {build_filter_clause('sm')}
        GROUP BY sm.USER_NAME, sm.PRIMARY_TEAM, sm.TITLE
    )
    SELECT * FROM user_conferences
    ORDER BY CONFERENCES_ATTENDED_YTD DESC
    """

    try:
        df_conferences = session.sql(conferences_query).to_pandas()

        # Metric card
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric(f"Total Conferences {time_metric}", int(df_conferences[f"CONFERENCES_ATTENDED{metric_suffix}"].sum()))
        with col2:
            st.metric("Active Users", len(df_conferences[df_conferences[f"CONFERENCES_ATTENDED{metric_suffix}"] > 0]))
        with col3:
            st.metric(f"Avg Conferences per User {time_metric}", round(df_conferences[f"CONFERENCES_ATTENDED{metric_suffix}"].mean(), 1))

        st.divider()

        # Conference details table with drill-down
        st.subheader("Conference Summary by User")
        selected_conference_user = st.selectbox(
            "Select a user to drill down:",
            [""] + df_conferences["USER_NAME"].tolist(),
            key="conference_selectbox"
        )
        if selected_conference_user:
            if st.button("View Details", key="conference_detail_btn"):
                show_conference_detail(selected_conference_user, time_metric)

        st.dataframe(df_conferences, use_container_width=True)

        # Conferences by team
        st.subheader(f"Conferences Attended by Team ({time_metric})")
        team_conferences = df_conferences.groupby("PRIMARY_TEAM")[f"CONFERENCES_ATTENDED{metric_suffix}"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(team_conferences, x="PRIMARY_TEAM", y=f"CONFERENCES_ATTENDED{metric_suffix}", title=f"Conferences by Team ({time_metric})", labels={f"CONFERENCES_ATTENDED{metric_suffix}": "Conference Count", "PRIMARY_TEAM": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading conferences: {str(e)}")

# ===== TAB 5: ACTIVE DEALS =====
with tab5:
    st.subheader("Active Deals")

    deals_query = f"""
    SELECT
        USER_NAME,
        PRIMARY_TEAM,
        TITLE,
        ACTIVE_DEALS_CURRENT,
        ACTIVE_DEALS_L3M,
        ACTIVE_DEALS_YTD
    FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES
    WHERE {build_filter_clause()}
    ORDER BY ACTIVE_DEALS_YTD DESC
    """

    try:
        df_deals = session.sql(deals_query).to_pandas()

        # Metric cards
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Active Deals (Current)", int(df_deals["ACTIVE_DEALS_CURRENT"].sum()))
        with col2:
            st.metric("Total Active Deals (L3M)", int(df_deals["ACTIVE_DEALS_L3M"].sum()))
        with col3:
            st.metric("Total Active Deals (YTD)", int(df_deals["ACTIVE_DEALS_YTD"].sum()))

        st.divider()

        # Active deals table
        st.subheader("Active Deals by User")
        st.dataframe(df_deals, use_container_width=True)

        # Deals by team
        st.subheader("Active Deals by Team (YTD)")
        team_deals = df_deals.groupby("PRIMARY_TEAM")["ACTIVE_DEALS_YTD"].sum().sort_values(ascending=False).reset_index()
        fig = px.bar(team_deals, x="PRIMARY_TEAM", y="ACTIVE_DEALS_YTD", title="Active Deals by Team (YTD)", labels={"ACTIVE_DEALS_YTD": "Deal Count", "PRIMARY_TEAM": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading deals data: {str(e)}")

# ===== TAB 6: TRENDS =====
with tab6:
    st.subheader("12-Month Trend Analysis")

    trends_query = """
    WITH monthly_interactions AS (
        SELECT
            DATE_TRUNC('MONTH', fi.DT) AS MONTH,
            SUM(CASE WHEN fi.ACTIVITY_TYPE IN ('Email', 'LinkedIn InMail', 'Text Message', 'Voicemail') THEN 1 ELSE 0 END) AS OUTREACH,
            SUM(CASE WHEN fi.ACTIVITY_TYPE IN ('Call', 'Meeting', 'Setup Call/Meeting for PVP') THEN 1 ELSE 0 END) AS PROSPECT_INTERACTIONS,
            SUM(CASE WHEN fi.ACTIVITY_TYPE = 'Passed Lead' THEN 1 ELSE 0 END) AS PASSED_LEADS
        FROM DBT.DEV.FACT_INTERACTION fi
        JOIN DBT.DEV.BRIDGE_INTERACTION_USER bu ON fi.ID = bu.INTERACTION_ID
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
        WHERE fi.DT >= DATEADD('MONTH', -12, CURRENT_DATE()) AND u.DP_IS_ACTIVE = TRUE
        GROUP BY 1
    ),
    monthly_conferences AS (
        SELECT
            DATE_TRUNC('MONTH', fc.STARTDATE) AS MONTH,
            COUNT(DISTINCT fc.ID) AS CONFERENCES
        FROM DBT.DEV.FACT_CONFERENCE fc
        JOIN DBT.DEV.BRIDGE_CONFERENCE_USER bu ON fc.ID = bu.CONFERENCE_ID
        WHERE fc.STARTDATE >= DATEADD('MONTH', -12, CURRENT_DATE())
        GROUP BY 1
    ),
    monthly_hqt AS (
        SELECT
            DATE_TRUNC('MONTH', h.APPROVEDDATE) AS MONTH,
            COUNT(DISTINCT h.ID) AS HQT_APPROVALS
        FROM YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY h
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__CHOICE_STATUS cs ON h.ID = cs.HQTENTRY_ID_BASE AND cs.DP_IS_ACTIVE = TRUE
        JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY_STATUS_OPTIONS cs_opt ON cs.HQTENTRY_STATUS_OPTIONS_ID = cs_opt.ID AND cs_opt.NAME = 'Approved'
        WHERE h.APPROVEDDATE >= DATEADD('MONTH', -12, CURRENT_DATE())
        GROUP BY 1
    )
    SELECT
        COALESCE(mi.MONTH, mc.MONTH, mh.MONTH) AS MONTH,
        COALESCE(mi.OUTREACH, 0) AS OUTREACH,
        COALESCE(mi.PROSPECT_INTERACTIONS, 0) AS PROSPECT_INTERACTIONS,
        COALESCE(mi.PASSED_LEADS, 0) AS PASSED_LEADS,
        COALESCE(mc.CONFERENCES, 0) AS CONFERENCES,
        COALESCE(mh.HQT_APPROVALS, 0) AS HQT_APPROVALS
    FROM monthly_interactions mi
    FULL OUTER JOIN monthly_conferences mc ON mi.MONTH = mc.MONTH
    FULL OUTER JOIN monthly_hqt mh ON mi.MONTH = mh.MONTH
    ORDER BY MONTH
    """

    try:
        df_trends = session.sql(trends_query).to_pandas()
        df_trends["MONTH"] = pd.to_datetime(df_trends["MONTH"])
        df_trends = df_trends.sort_values("MONTH")

        # Create multi-line chart
        fig = px.line(df_trends, x="MONTH", y=["OUTREACH", "PROSPECT_INTERACTIONS", "PASSED_LEADS", "CONFERENCES", "HQT_APPROVALS"],
                      title="Sourcing Activity Trends (12 months)",
                      labels={"value": "Count", "variable": "Metric", "MONTH": "Month"},
                      markers=True)
        st.plotly_chart(fig, use_container_width=True)

        st.divider()

        # Team-level trends
        st.subheader("Trends by Team")
        team_trends_query = f"""
        WITH monthly_team_interactions AS (
            SELECT
                DATE_TRUNC('MONTH', fi.DT) AS MONTH,
                sm.PRIMARY_TEAM,
                SUM(CASE WHEN fi.ACTIVITY_TYPE IN ('Email', 'LinkedIn InMail', 'Text Message', 'Voicemail') THEN 1 ELSE 0 END) AS OUTREACH,
                SUM(CASE WHEN fi.ACTIVITY_TYPE IN ('Call', 'Meeting', 'Setup Call/Meeting for PVP') THEN 1 ELSE 0 END) AS PROSPECT_INTERACTIONS
            FROM DBT.DEV.FACT_INTERACTION fi
            JOIN DBT.DEV.BRIDGE_INTERACTION_USER bu ON fi.ID = bu.INTERACTION_ID
            JOIN YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER u ON CAST(bu.USER_ID AS VARCHAR) = u.DC_ID
            JOIN AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES sm ON LOWER(u.FULLNAME) = LOWER(sm.USER_NAME)
            WHERE fi.DT >= DATEADD('MONTH', -12, CURRENT_DATE()) AND u.DP_IS_ACTIVE = TRUE
            GROUP BY 1, 2
        )
        SELECT * FROM monthly_team_interactions
        ORDER BY MONTH, PRIMARY_TEAM
        """

        try:
            df_team_trends = session.sql(team_trends_query).to_pandas()
            df_team_trends["MONTH"] = pd.to_datetime(df_team_trends["MONTH"])

            fig_team = px.line(df_team_trends, x="MONTH", y="OUTREACH", color="PRIMARY_TEAM",
                              title="Outreach Activity by Team (12 months)",
                              labels={"OUTREACH": "Outreach Count", "MONTH": "Month"},
                              markers=True)
            st.plotly_chart(fig_team, use_container_width=True)
        except Exception as e:
            st.warning(f"Team trends data unavailable: {str(e)}")

    except Exception as e:
        st.error(f"Error loading trend data: {str(e)}")

# ===== TAB 7: NATURAL LANGUAGE QUERY =====
with tab7:
    st.subheader("💬 Ask Questions About Your Data")
    st.markdown("Use natural language to query your sourcing metrics. Examples:")
    with st.expander("📚 Example Questions", expanded=True):
        st.markdown("""
        - Who had the most outreach last month?
        - Which team attended the most conferences YTD?
        - Show me passed leads by title this quarter
        - What's the total HQT approvals for the growth team?
        - Who has the most active deals currently?
        """)

    # Chat interface
    st.markdown("---")
    user_question = st.chat_input("Ask a question about your sourcing data...")

    if user_question:
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        with st.spinner("🤔 Thinking..."):
            try:
                # Build schema context
                schema_context = """
                Available tables and columns:
                - AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES: USER_NAME, PRIMARY_TEAM, TITLE, NET_NEW_COMPANIES_MTD/L3M/YTD, OUTREACH_MTD/L3M/YTD, PROSPECT_INTERACTIONS_MTD/L3M/YTD, PASSED_LEADS_MTD/L3M/YTD, CONFERENCES_ATTENDED_MTD/L3M/YTD, ACTIVE_DEALS_CURRENT/L3M/YTD
                - DBT.DEV.FACT_INTERACTION: ID, DT, SUBJECT, NOTES, ACTIVITY_TYPE (Email, Call, Meeting, LinkedIn InMail, etc)
                - DBT.DEV.FACT_CONFERENCE: ID, STARTDATE, NAME, LOCATION
                - YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER: FULLNAME, EMAIL, DC_ID, SECTOR, DP_IS_ACTIVE
                - YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY: ID, APPROVEDDATE
                """

                prompt = f"""You are a Snowflake SQL expert. Convert this natural language question into a valid Snowflake SQL query.
Schema: {schema_context}

Question: {user_question}

Return ONLY the SQL query without any explanation, comments, or markdown formatting. The query must be executable against Snowflake."""

                # Use Cortex to generate SQL
                cortex_query = f"""
                SELECT SNOWFLAKE.CORTEX.COMPLETE(
                    'claude-haiku-4-5',
                    '{prompt.replace("'", "''")}'
                )
                """

                result = session.sql(cortex_query).collect()[0][0]

                # Clean up result
                sql_query = result.strip()
                if sql_query.startswith("```"):
                    sql_query = sql_query.split("```")[1].replace("sql", "").strip()
                if sql_query.startswith("SELECT"):
                    sql_query = sql_query

                # Execute the generated SQL
                df_result = session.sql(sql_query).to_pandas()

                # Store response in chat history
                st.session_state.chat_history.append({"role": "assistant", "content": f"Found {len(df_result)} results"})

                # Display results
                st.success("✅ Query executed successfully")
                st.subheader("Results")
                st.dataframe(df_result, use_container_width=True)

                # Show generated SQL
                with st.expander("🔍 Generated SQL", expanded=False):
                    st.code(sql_query, language="sql")

            except Exception as e:
                st.error(f"❌ Error executing query: {str(e)}")
                st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {str(e)}"})

    # Display chat history
    if st.session_state.chat_history:
        st.markdown("---")
        st.subheader("Chat History")
        for msg in st.session_state.chat_history[-10:]:  # Show last 10 messages
            if msg["role"] == "user":
                st.chat_message("user").write(msg["content"])
            else:
                st.chat_message("assistant").write(msg["content"])

# Debug info
with st.expander("ℹ️ Connection Info"):
    st.write(f"**Account:** uy18554")
    st.write(f"**Role:** ACCOUNTADMIN")
    st.write(f"**Warehouse:** ADAS_WH")
    st.write(f"**Time Metric:** {time_metric}")
    st.write(f"**Selected Teams:** {selected_teams if selected_teams else 'None'}")
    st.write(f"**Selected Titles:** {selected_titles if selected_titles else 'None'}")
    st.write(f"**Selected Sectors:** {selected_sectors if selected_sectors else 'None'}")
    st.write(f"**Selected Locations:** {selected_locations if selected_locations else 'None'}")
