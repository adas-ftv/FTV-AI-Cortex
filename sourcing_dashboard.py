import streamlit as st
import pandas as pd
from datetime import datetime, timedelta
import plotly.express as px
import plotly.graph_objects as go
from snowflake.snowpark import functions as F

# Page config
st.set_page_config(
    page_title="Sourcing Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Initialize Snowflake connection
@st.cache_resource
def get_snowflake_session():
    try:
        from snowflake.snowpark.context import get_active_session
        session = get_active_session()
    except:
        from snowflake.snowpark import Session
        session = Session.builder.config('connection_name', 'default').create()
    return session

session = get_snowflake_session()

# Title and description
st.title("🎯 Sourcing Dashboard")
st.markdown("Net new company sourcing metrics and attribution analysis")

# Sidebar filters
st.sidebar.header("Filters")

# Time range filter
time_range = st.sidebar.selectbox(
    "Time Period",
    ["Last 30 Days", "Last 90 Days", "Last 6 Months", "Year to Date", "Custom"]
)

# Owner/Team filter
owner_team = st.sidebar.multiselect(
    "Owner/Team",
    ["All"],
    default=["All"]
)

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
tab1, tab2, tab3, tab4 = st.tabs(
    ["📈 Summary", "👥 User Attribution", "💬 Interactions", "🎤 Conferences"]
)

with tab1:
    st.subheader("Net New Companies Metrics")
    st.info("Query: AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES")
    # Placeholder for metrics visualization
    st.write("Metrics will load here")

with tab2:
    st.subheader("User & HQT Attribution")
    st.info("Queries: __USER and HQTENTRY__USER_OWNERTEAM")

    # HQT Attribution query
    hqt_query = """
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
    ORDER BY HQT_APPROVED_YTD DESC
    """

    try:
        df = session.sql(hqt_query).to_pandas()

        # Display top metrics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Total Users", len(df))
        with col2:
            st.metric("Total HQT YTD", int(df["HQT_APPROVED_YTD"].sum()))
        with col3:
            st.metric("Avg HQT per User", round(df["HQT_APPROVED_YTD"].mean(), 1))

        st.divider()

        # User details table
        st.subheader("User Performance Summary")
        st.dataframe(df, use_container_width=True)

        # HQT by team
        st.subheader("HQT Approved by Team (YTD)")
        team_hqt = df.groupby("PRIMARY_TEAM")["HQT_APPROVED_YTD"].sum().sort_values(ascending=False)
        fig = px.bar(team_hqt, title="HQT Approvals by Team", labels={"value": "HQT Count", "index": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading data: {str(e)}")

with tab3:
    st.subheader("Interaction Analytics")
    st.info("Queries: FACT_INTERACTION + BRIDGE_INTERACTION_USER")
    # Placeholder for interaction data
    st.write("Interaction data will load here")

with tab4:
    st.subheader("Conference Sourcing")
    st.info("Queries: FACT_CONFERENCE + BRIDGE_CONFERENCE_USER")
    # Placeholder for conference data
    st.write("Conference data will load here")

# Debug info
with st.expander("ℹ️ Connection Info"):
    st.write(f"**Account:** uy18554")
    st.write(f"**Role:** ACCOUNTADMIN")
    st.write(f"**Warehouse:** ADAS_WH")
