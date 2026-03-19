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

# Time period selector - MTD/L3M/YTD
time_metric = st.sidebar.radio(
    "Time Metric",
    ["MTD", "L3M", "YTD"],
    horizontal=True
)

# Map time metrics to column suffixes
metric_suffix = f"_{time_metric}"

# Get unique teams and titles from the summary query
@st.cache_data(ttl=3600)
def get_filter_options():
    try:
        teams_query = "SELECT DISTINCT PRIMARY_TEAM FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES ORDER BY PRIMARY_TEAM"
        titles_query = "SELECT DISTINCT TITLE FROM AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES ORDER BY TITLE"

        teams = session.sql(teams_query).to_pandas()["PRIMARY_TEAM"].tolist()
        titles = session.sql(titles_query).to_pandas()["TITLE"].tolist()

        return teams, titles
    except:
        return [], []

teams, titles = get_filter_options()

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

# Build WHERE clause for filters
def build_filter_clause(table_alias="sm"):
    filters = []
    if selected_teams:
        team_list = "', '".join(selected_teams)
        filters.append(f"{table_alias}.PRIMARY_TEAM IN ('{team_list}')")
    if selected_titles:
        title_list = "', '".join(selected_titles)
        filters.append(f"{table_alias}.TITLE IN ('{title_list}')")
    return " AND ".join(filters) if filters else "1=1"

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
tab1, tab2, tab3, tab4, tab5 = st.tabs(
    ["📈 Summary", "👥 User Attribution", "💬 Interactions", "🎤 Conferences", "💼 Active Deals"]
)

# ===== TAB 1: SUMMARY =====
with tab1:
    st.subheader("Net New Companies Metrics")
    st.info("Query: AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES")
    st.write("Metrics will load here")

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

        # Interaction details table
        st.subheader("Interaction Summary by User")
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

        # Conference details table
        st.subheader("Conference Summary by User")
        st.dataframe(df_conferences, use_container_width=True)

        # Conferences by team
        st.subheader(f"Conferences Attended by Team ({time_metric})")
        team_conferences = df_conferences.groupby("PRIMARY_TEAM")[f"CONFERENCES_ATTENDED{metric_suffix}"].sum().sort_values(ascending=False)
        fig = px.bar(team_conferences, title=f"Conferences by Team ({time_metric})", labels={"value": "Conference Count", "index": "Team"})
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
        team_deals = df_deals.groupby("PRIMARY_TEAM")["ACTIVE_DEALS_YTD"].sum().sort_values(ascending=False)
        fig = px.bar(team_deals, title="Active Deals by Team (YTD)", labels={"value": "Deal Count", "index": "Team"})
        st.plotly_chart(fig, use_container_width=True)

    except Exception as e:
        st.error(f"Error loading deals data: {str(e)}")

# Debug info
with st.expander("ℹ️ Connection Info"):
    st.write(f"**Account:** uy18554")
    st.write(f"**Role:** ACCOUNTADMIN")
    st.write(f"**Warehouse:** ADAS_WH")
    st.write(f"**Time Metric:** {time_metric}")
    st.write(f"**Selected Teams:** {selected_teams if selected_teams else 'All'}")
    st.write(f"**Selected Titles:** {selected_titles if selected_titles else 'All'}")
