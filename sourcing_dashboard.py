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
def get_snowflake_connection():
    return st.connection("snowflake")

conn = get_snowflake_connection()

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
    # Placeholder for attribution analysis
    st.write("User attribution data will load here")

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
