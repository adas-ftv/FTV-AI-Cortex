import streamlit as st
import pandas as pd
import plotly.express as px

# Page config
st.set_page_config(
    page_title="Sourcing Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── Snowflake session ──
from snowflake.snowpark.context import get_active_session
session = get_active_session()

# ── Helper: run a query safely ──
def run_query(sql):
    """Run SQL and return a DataFrame, or None on error."""
    try:
        return session.sql(sql).to_pandas()
    except Exception as e:
        st.error(f"Query error: {e}")
        return None

# ── Helper: get column names for a table ──
@st.cache_data(ttl=3600)
def get_columns(full_table_name):
    """Return list of column names for a table."""
    df = run_query(f"SHOW COLUMNS IN TABLE {full_table_name}")
    if df is not None and len(df) > 0:
        # SHOW COLUMNS returns a column called "column_name"
        col_name_col = [c for c in df.columns if "column_name" in c.lower()]
        if col_name_col:
            return df[col_name_col[0]].tolist()
        # fallback: try first column
        return df.iloc[:, 0].tolist()
    return []

# ── Helper: preview rows from a table ──
@st.cache_data(ttl=3600)
def preview_table(full_table_name, limit=5):
    """Return a small preview DataFrame."""
    return run_query(f"SELECT * FROM {full_table_name} LIMIT {limit}")

# ── Tables we expect to use ──
TABLES = {
    "sourcing": "AD_VIEWS.DEALCLOUD.SOURCING_METRICS_NET_NEW_COMPANIES",
    "interaction": "DBT.DEV.FACT_INTERACTION",
    "bridge_interaction_user": "DBT.DEV.BRIDGE_INTERACTION_USER",
    "conference": "DBT.DEV.FACT_CONFERENCE",
    "bridge_conference_user": "DBT.DEV.BRIDGE_CONFERENCE_USER",
    "user": "YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.__USER",
    "hqtentry": "YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY",
    "hqtentry_status": "YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__CHOICE_STATUS",
    "hqtentry_status_options": "YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY_STATUS_OPTIONS",
    "hqtentry_ownerteam": "YIRCHFV_DC_ACCOUNT_DC_SF_SHARE.DATA.HQTENTRY__USER_OWNERTEAM",
}

# ── Discover all schemas on load ──
@st.cache_data(ttl=3600)
def discover_schemas():
    """Discover actual column names for every table."""
    schemas = {}
    for key, table in TABLES.items():
        schemas[key] = get_columns(table)
    return schemas

schemas = discover_schemas()

# ── Helper: check if a column exists in a table ──
def has_col(table_key, col_name):
    return col_name.upper() in [c.upper() for c in schemas.get(table_key, [])]

# ── Helper: find columns matching a pattern ──
def find_cols(table_key, pattern):
    """Return columns whose name contains `pattern` (case-insensitive)."""
    return [c for c in schemas.get(table_key, []) if pattern.upper() in c.upper()]

# ═══════════════════════════════════════════════════════════════
# TITLE
# ═══════════════════════════════════════════════════════════════
st.title("📊 Sourcing Dashboard")
st.markdown("Net new company sourcing metrics and attribution analysis")

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - Time period
# ═══════════════════════════════════════════════════════════════
st.sidebar.header("Filters")
time_metric = st.sidebar.radio("Time Metric", ["MTD", "L3M", "YTD"], horizontal=True)
metric_suffix = f"_{time_metric}"

# ═══════════════════════════════════════════════════════════════
# SIDEBAR - Dynamic filters based on actual columns
# ═══════════════════════════════════════════════════════════════
sourcing_table = TABLES["sourcing"]
sourcing_cols = schemas.get("sourcing", [])

# Build filters dynamically from columns that actually exist
selected_filters = {}

# Try common filter columns
for filter_col in ["PRIMARY_TEAM", "TEAM", "TITLE", "SECTOR", "LOCATION"]:
    if has_col("sourcing", filter_col):
        options_df = run_query(f"SELECT DISTINCT {filter_col} FROM {sourcing_table} WHERE {filter_col} IS NOT NULL ORDER BY {filter_col}")
        if options_df is not None and len(options_df) > 0:
            options = options_df.iloc[:, 0].tolist()
            selected = st.sidebar.multiselect(filter_col.replace("_", " ").title(), options)
            if selected:
                selected_filters[filter_col] = selected

def build_where(alias=""):
    """Build WHERE clause from selected filters."""
    prefix = f"{alias}." if alias else ""
    clauses = []
    for col, vals in selected_filters.items():
        escaped = "', '".join([v.replace("'", "''") for v in vals])
        clauses.append(f"{prefix}{col} IN ('{escaped}')")
    return "WHERE " + " AND ".join(clauses) if clauses else ""

# ═══════════════════════════════════════════════════════════════
# TABS
# ═══════════════════════════════════════════════════════════════
tab_schema, tab_summary, tab_detail, tab_trends, tab_ask = st.tabs(
    ["🔍 Schema Explorer", "📈 Summary", "👥 Detail", "📊 Trends", "🤖 Ask"]
)

# ═══════════════════════════════════════════════════════════════
# TAB: Schema Explorer
# ═══════════════════════════════════════════════════════════════
with tab_schema:
    st.subheader("Discovered Table Schemas")
    st.markdown("These are the **actual columns** found in each table. Use this to understand what data is available.")

    for key, table in TABLES.items():
        cols = schemas.get(key, [])
        with st.expander(f"**{table}** ({len(cols)} columns)", expanded=False):
            if cols:
                st.write(", ".join(cols))
                preview = preview_table(table)
                if preview is not None:
                    st.dataframe(preview, use_container_width=True, hide_index=True)
            else:
                st.warning(f"Could not read schema for {table}. Check permissions or table name.")

# ═══════════════════════════════════════════════════════════════
# TAB: Summary
# ═══════════════════════════════════════════════════════════════
with tab_summary:
    st.subheader("Executive Summary")

    if not sourcing_cols:
        st.error(f"Cannot read columns from {sourcing_table}. Check the Schema Explorer tab.")
    else:
        # Dynamically pick columns that exist
        select_cols = []
        # Always try to get a name/user column
        name_col = None
        for candidate in ["USER_NAME", "NAME", "FULLNAME", "USER"]:
            if has_col("sourcing", candidate):
                name_col = candidate
                break

        # Find all metric columns that match the selected time period
        metric_cols = find_cols("sourcing", metric_suffix)

        # Also grab grouping columns
        group_cols = []
        for candidate in ["PRIMARY_TEAM", "TEAM", "TITLE"]:
            if has_col("sourcing", candidate):
                group_cols.append(candidate)

        # Build SELECT list
        all_select = []
        if name_col:
            all_select.append(name_col)
        all_select.extend(group_cols)
        all_select.extend(metric_cols)

        if not all_select:
            st.warning("No recognized columns found. Check the Schema Explorer tab.")
        else:
            where = build_where()
            query = f"SELECT {', '.join(all_select)} FROM {sourcing_table} {where} ORDER BY 1"
            df = run_query(query)

            if df is not None and len(df) > 0:
                # Top-level metrics
                num_cols = [c for c in df.columns if df[c].dtype in ['int64', 'float64']]
                if num_cols:
                    metric_display = st.columns(min(len(num_cols), 4))
                    for i, col in enumerate(num_cols[:4]):
                        with metric_display[i]:
                            st.metric(col.replace("_", " ").title(), int(df[col].sum()))

                st.divider()

                # Leaderboard - top users by first numeric column
                if name_col and num_cols:
                    sort_col = num_cols[0]
                    top = df.nlargest(10, sort_col)
                    st.subheader(f"Top 10 by {sort_col.replace('_', ' ').title()}")
                    st.dataframe(top, use_container_width=True, hide_index=True)

                # Team breakdown if we have a team column
                team_col = None
                for candidate in ["PRIMARY_TEAM", "TEAM"]:
                    if candidate in df.columns:
                        team_col = candidate
                        break

                if team_col and num_cols:
                    st.divider()
                    st.subheader(f"By {team_col.replace('_', ' ').title()}")
                    team_agg = df.groupby(team_col)[num_cols[0]].sum().sort_values(ascending=False).reset_index()
                    fig = px.bar(team_agg, x=team_col, y=num_cols[0],
                                 title=f"{num_cols[0].replace('_', ' ').title()} by {team_col.replace('_', ' ').title()}",
                                 labels={num_cols[0]: "Count", team_col: team_col.replace("_", " ").title()})
                    st.plotly_chart(fig, use_container_width=True)

                # Full data table
                st.divider()
                st.subheader("Full Data")
                st.dataframe(df, use_container_width=True, hide_index=True)
            elif df is not None:
                st.info("No data returned. Try adjusting filters.")

# ═══════════════════════════════════════════════════════════════
# TAB: Detail (Interactions + Conferences)
# ═══════════════════════════════════════════════════════════════
with tab_detail:
    st.subheader("Interaction & Conference Detail")

    detail_sub1, detail_sub2 = st.tabs(["💬 Interactions", "🎤 Conferences"])

    # -- Interactions --
    with detail_sub1:
        int_cols = schemas.get("interaction", [])
        if not int_cols:
            st.warning("Cannot read FACT_INTERACTION schema. Check Schema Explorer.")
        else:
            st.markdown(f"**Available columns:** {', '.join(int_cols[:20])}")
            # Simple query: just show recent interactions
            int_table = TABLES["interaction"]
            # Find a date column
            date_col = None
            for candidate in ["DT", "DATE", "CREATED_DATE", "INTERACTION_DATE"]:
                if has_col("interaction", candidate):
                    date_col = candidate
                    break

            limit_rows = st.slider("Rows to load", 50, 500, 100, key="int_limit")

            if date_col:
                int_query = f"SELECT * FROM {int_table} WHERE {date_col} >= DATEADD('MONTH', -3, CURRENT_DATE()) ORDER BY {date_col} DESC LIMIT {limit_rows}"
            else:
                int_query = f"SELECT * FROM {int_table} LIMIT {limit_rows}"

            df_int = run_query(int_query)
            if df_int is not None and len(df_int) > 0:
                # Summary metrics
                st.metric("Total Rows", len(df_int))

                # If there's an activity type column, show breakdown
                for candidate in ["ACTIVITY_TYPE", "TYPE", "INTERACTION_TYPE"]:
                    if candidate in df_int.columns:
                        st.subheader("By Type")
                        type_counts = df_int[candidate].value_counts().reset_index()
                        type_counts.columns = ["Type", "Count"]
                        fig = px.pie(type_counts, values="Count", names="Type", title="Interaction Types")
                        st.plotly_chart(fig, use_container_width=True)
                        break

                st.dataframe(df_int, use_container_width=True, hide_index=True)
            elif df_int is not None:
                st.info("No interaction data found.")

    # -- Conferences --
    with detail_sub2:
        conf_cols = schemas.get("conference", [])
        if not conf_cols:
            st.warning("Cannot read FACT_CONFERENCE schema. Check Schema Explorer.")
        else:
            st.markdown(f"**Available columns:** {', '.join(conf_cols[:20])}")
            conf_table = TABLES["conference"]

            # Find a date column
            date_col = None
            for candidate in ["STARTDATE", "START_DATE", "DATE", "CONFERENCE_DATE"]:
                if has_col("conference", candidate):
                    date_col = candidate
                    break

            limit_rows = st.slider("Rows to load", 50, 500, 100, key="conf_limit")

            if date_col:
                conf_query = f"SELECT * FROM {conf_table} WHERE {date_col} >= DATEADD('MONTH', -12, CURRENT_DATE()) ORDER BY {date_col} DESC LIMIT {limit_rows}"
            else:
                conf_query = f"SELECT * FROM {conf_table} LIMIT {limit_rows}"

            df_conf = run_query(conf_query)
            if df_conf is not None and len(df_conf) > 0:
                st.metric("Total Rows", len(df_conf))
                st.dataframe(df_conf, use_container_width=True, hide_index=True)
            elif df_conf is not None:
                st.info("No conference data found.")

# ═══════════════════════════════════════════════════════════════
# TAB: Trends
# ═══════════════════════════════════════════════════════════════
with tab_trends:
    st.subheader("Trend Analysis")

    # We need the sourcing table to have time-based metric columns
    # Look for columns with MTD/L3M/YTD patterns
    all_metric_bases = set()
    for col in sourcing_cols:
        for suffix in ["_MTD", "_L3M", "_YTD"]:
            if col.upper().endswith(suffix):
                base = col[:col.upper().rfind(suffix)]
                all_metric_bases.add(base)

    if not all_metric_bases:
        st.info("No time-period metric columns found in the sourcing table. Check Schema Explorer.")
    else:
        st.markdown(f"**Available metrics:** {', '.join(sorted(all_metric_bases))}")

        selected_metric = st.selectbox("Select metric to compare across time periods", sorted(all_metric_bases))

        if selected_metric:
            # Build query to get MTD, L3M, YTD for this metric
            period_cols = []
            for suffix in ["_MTD", "_L3M", "_YTD"]:
                col_name = f"{selected_metric}{suffix}"
                if has_col("sourcing", col_name):
                    period_cols.append(col_name)

            if period_cols:
                # Find name and team columns
                name_col = None
                for candidate in ["USER_NAME", "NAME", "FULLNAME"]:
                    if has_col("sourcing", candidate):
                        name_col = candidate
                        break

                team_col = None
                for candidate in ["PRIMARY_TEAM", "TEAM"]:
                    if has_col("sourcing", candidate):
                        team_col = candidate
                        break

                select_list = []
                if name_col:
                    select_list.append(name_col)
                if team_col:
                    select_list.append(team_col)
                select_list.extend(period_cols)

                where = build_where()
                query = f"SELECT {', '.join(select_list)} FROM {sourcing_table} {where} ORDER BY {period_cols[-1]} DESC"
                df_trend = run_query(query)

                if df_trend is not None and len(df_trend) > 0:
                    # Show totals across periods
                    period_totals = {col: int(df_trend[col].sum()) for col in period_cols if col in df_trend.columns}
                    cols_display = st.columns(len(period_totals))
                    for i, (col, total) in enumerate(period_totals.items()):
                        with cols_display[i]:
                            st.metric(col.replace("_", " ").title(), total)

                    st.divider()

                    # Bar chart by team if available
                    if team_col and team_col in df_trend.columns:
                        for pcol in period_cols:
                            team_agg = df_trend.groupby(team_col)[pcol].sum().sort_values(ascending=False).reset_index()
                            fig = px.bar(team_agg, x=team_col, y=pcol,
                                         title=f"{pcol.replace('_', ' ').title()} by {team_col.replace('_', ' ').title()}")
                            st.plotly_chart(fig, use_container_width=True)

                    st.divider()
                    st.subheader("Detail")
                    st.dataframe(df_trend, use_container_width=True, hide_index=True)

# ═══════════════════════════════════════════════════════════════
# TAB: Ask (Natural Language via Cortex)
# ═══════════════════════════════════════════════════════════════
with tab_ask:
    st.subheader("Ask Questions About Your Data")

    # Build schema context from discovered schemas
    schema_lines = []
    for key, cols in schemas.items():
        if cols:
            schema_lines.append(f"- {TABLES[key]}: {', '.join(cols)}")
    schema_context = "\n".join(schema_lines)

    with st.expander("Available Tables & Columns", expanded=False):
        st.code(schema_context)

    st.markdown("**Examples:** _Who had the most outreach YTD?_ / _Show conferences by team_ / _Top 5 users by net new companies_")

    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_question = st.chat_input("Ask a question about your sourcing data...")

    if user_question:
        st.session_state.chat_history.append({"role": "user", "content": user_question})

        with st.spinner("Thinking..."):
            try:
                prompt = f"""You are a Snowflake SQL expert. Convert this natural language question into a valid Snowflake SQL query.

Here are the actual table schemas (use ONLY these column names):
{schema_context}

Question: {user_question}

Return ONLY the SQL query. No explanation, no markdown formatting, no code fences."""

                cortex_query = f"""SELECT SNOWFLAKE.CORTEX.COMPLETE('claude-haiku-4-5', '{prompt.replace("'", "''")}')"""
                result = session.sql(cortex_query).collect()[0][0]

                # Clean up
                sql_query = result.strip()
                if sql_query.startswith("```"):
                    lines = sql_query.split("\n")
                    sql_query = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
                    sql_query = sql_query.strip()

                df_result = run_query(sql_query)

                if df_result is not None and len(df_result) > 0:
                    st.success(f"Found {len(df_result)} results")
                    st.dataframe(df_result, use_container_width=True, hide_index=True)
                    st.session_state.chat_history.append({"role": "assistant", "content": f"Found {len(df_result)} results"})
                elif df_result is not None:
                    st.info("Query returned no results.")

                with st.expander("Generated SQL", expanded=False):
                    st.code(sql_query, language="sql")

            except Exception as e:
                st.error(f"Error: {e}")
                st.session_state.chat_history.append({"role": "assistant", "content": f"Error: {e}"})

    # Show recent chat
    if st.session_state.chat_history:
        st.divider()
        for msg in st.session_state.chat_history[-10:]:
            st.chat_message(msg["role"]).write(msg["content"])

# ═══════════════════════════════════════════════════════════════
# Footer: connection info
# ═══════════════════════════════════════════════════════════════
with st.expander("Connection Info"):
    st.write(f"**Time Metric:** {time_metric}")
    st.write(f"**Active Filters:** {selected_filters if selected_filters else 'None'}")
    st.write(f"**Tables discovered:** {sum(1 for v in schemas.values() if v)}/{len(schemas)}")
