"""
Streamlit UI for Autonomous ETL/ELT Agent Demo
Provides an interactive interface to submit user stories and visualize pipeline execution
"""

import streamlit as st
import requests
import json
import pandas as pd
from datetime import datetime
import time
from typing import Optional
import plotly.graph_objects as go
import plotly.express as px
import os

# Page configuration
st.set_page_config(
    page_title="ETL Agent Demo",
    page_icon="🚀",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Styling
st.markdown("""
<style>
    .main {
        padding-top: 2rem;
    }
    .stTabs [data-baseweb="tab-list"] button {
        font-size: 16px;
    }
    .success-box {
        background-color: #d4edda;
        border: 1px solid #c3e6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        border: 1px solid #f5c6cb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        border: 1px solid #bee5eb;
        border-radius: 5px;
        padding: 1rem;
        margin: 1rem 0;
    }
</style>
""", unsafe_allow_html=True)

# Session state initialization
if "api_url" not in st.session_state:
    # Get API URL from environment variable or use default
    st.session_state.api_url = os.getenv("API_URL", "http://localhost:8000")
if "api_key" not in st.session_state:
    st.session_state.api_key = os.getenv("API_KEY", "")
if "last_execution" not in st.session_state:
    st.session_state.last_execution = None
if "polling" not in st.session_state:
    st.session_state.polling = False

# Sidebar configuration
st.sidebar.title("⚙️ Configuration")

# Allow override of API URL in development
environment = os.getenv("ENVIRONMENT", "development")
if environment == "development":
    api_url = st.sidebar.text_input(
        "API URL",
        value=st.session_state.api_url,
        help="FastAPI server endpoint"
    )
    st.session_state.api_url = api_url
    api_key = st.sidebar.text_input(
        "API Key (optional)",
        value=st.session_state.api_key,
        type="password",
        help="Bearer token for API authentication"
    )
    st.session_state.api_key = api_key
else:
    # Production: use environment variables only
    api_url = st.session_state.api_url
    api_key = st.session_state.api_key
    st.sidebar.info(f"📍 API: {api_url}")

# Check API health
def check_api_health():
    """Check if API is reachable and healthy."""
    try:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        response = requests.get(f"{api_url}/health", timeout=5, headers=headers)
        return response.status_code == 200
    except requests.exceptions.ConnectionError:
        return False
    except Exception:
        return False


def make_api_request(endpoint: str, method: str = "GET", json_data: dict = None) -> Optional[dict]:
    """Make authenticated API request.
    
    Args:
        endpoint: API endpoint path (e.g., '/pipelines/demo')
        method: HTTP method (GET, POST, etc.)
        json_data: JSON data to send
        
    Returns:
        Response JSON or None if request failed
    """
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    
    try:
        url = f"{api_url}{endpoint}"
        if method == "POST":
            response = requests.post(url, json=json_data, headers=headers, timeout=60)
        elif method == "GET":
            response = requests.get(url, headers=headers, timeout=10)
        else:
            raise ValueError(f"Unsupported method: {method}")
        
        response.raise_for_status()
        return response.json()
    except requests.exceptions.Timeout:
        st.error("⏱️ Request timeout. API is taking too long to respond.")
        return None
    except requests.exceptions.ConnectionError:
        st.error(f"❌ Cannot reach API at {api_url}. Ensure the server is running.")
        return None
    except requests.exceptions.HTTPError as e:
        error_text = e.response.text[:200] if hasattr(e.response, 'text') else str(e)
        st.error(f"❌ API Error: {e.response.status_code} - {error_text}")
        return None
    except Exception as e:
        st.error(f"❌ Error: {str(e)}")
        return None


if st.sidebar.button("🔗 Check API Connection"):
    if check_api_health():
        st.sidebar.success("✅ API is healthy!")
    else:
        st.sidebar.error(f"""❌ Cannot reach API.

Make sure:
1. FastAPI is running: `uvicorn src.api:app --reload`
2. API URL is correct: {api_url}
3. API_KEY is valid (if required)
""")

st.sidebar.markdown("---")

# Main interface
st.title("🚀 Autonomous ETL/ELT Agent Demo")
st.markdown("""
### Submit User Stories and Generate Production-Ready Spark Pipelines
Transform DevOps user stories into fully tested, PR-ready data pipelines automatically.
""")

# Create tabs for different functionalities
tab1, tab2, tab3, tab4 = st.tabs([
    "📝 Submit User Story",
    "📊 Pipeline History",
    "📈 Analytics",
    "🔗 Data Lineage"
])

# ============================================================================
# TAB 1: Submit User Story
# ============================================================================
with tab1:
    st.header("Submit a User Story")
    st.markdown("Fill in the details about your ETL/ELT transformation requirement:")

    col1, col2 = st.columns(2)
    
    with col1:
        title = st.text_input(
            "📌 User Story Title",
            placeholder="e.g., Transform Customer Orders to Analytics",
            help="Brief name for your pipeline"
        )
        
        source_system = st.text_input(
            "📥 Source System",
            placeholder="e.g., Salesforce CRM, PostgreSQL, S3",
            help="Where data comes from"
        )
        
        target_system = st.text_input(
            "📤 Target System",
            placeholder="e.g., Snowflake, BigQuery, Delta Lake",
            help="Where data goes to"
        )

    with col2:
        description = st.text_area(
            "📄 Detailed Description",
            placeholder="""Describe your ETL requirements in detail. Examples:
- Load customer orders from Salesforce
- Join with product data
- Filter for orders > $100
- Calculate monthly summary
- Write to analytics table""",
            height=150,
            help="Be specific about transformations needed"
        )

    st.markdown("---")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("🔒 Data Quality Rules")
        data_quality_options = [
            "No NULL values in key columns",
            "Unique constraint on ID columns",
            "Valid date ranges",
            "Referential integrity checks",
            "Data type validation"
        ]
        selected_quality_rules = st.multiselect(
            "Select applicable quality rules:",
            data_quality_options,
            default=["No NULL values in key columns"],
            help="Quality checks for generated tests"
        )

    with col2:
        st.subheader("⚡ Performance Requirements")
        max_execution_time = st.number_input(
            "Max Execution Time (minutes):",
            min_value=1,
            max_value=1440,
            value=30,
            help="SLA timeout for pipeline execution"
        )
        
        expected_row_count = st.number_input(
            "Expected Row Count:",
            min_value=0,
            value=1000000,
            help="Expected data volume"
        )

    st.markdown("---")

    # Submit button
    col1, col2, col3 = st.columns([1, 1, 1])
    
    with col2:
        submit_button = st.button(
            "🚀 Submit Story & Generate Pipeline",
            use_container_width=True,
            type="primary"
        )

    if submit_button:
        if not title or not description:
            st.error("❌ Please fill in Title and Description")
        elif not check_api_health():
            st.error("❌ API is not running. Start FastAPI server first:\n`python -m uvicorn src.api:app --reload`")
        else:
            # Prepare request
            payload = {
                "title": title,
                "description": description,
                "source_system": source_system if source_system else None,
                "target_system": target_system if target_system else None,
                "data_quality_rules": selected_quality_rules,
                "performance_requirements": {
                    "max_execution_time_minutes": max_execution_time,
                    "expected_row_count": expected_row_count
                }
            }

            with st.spinner("🔄 Submitting user story and orchestrating agents..."):
                try:
                    response = requests.post(
                        f"{api_url}/pipelines/create",
                        json=payload,
                        timeout=600  # 10 minute timeout for real agent execution
                    )
                    
                    if response.status_code in [200, 201]:
                        result = response.json()
                        st.session_state.last_execution = result
                        
                        st.markdown('<div class="success-box">', unsafe_allow_html=True)
                        st.success("✅ Pipeline execution completed!")
                        st.markdown('</div>', unsafe_allow_html=True)
                        
                        # Display execution summary
                        st.markdown("### 📊 Execution Summary")
                        
                        summary_cols = st.columns(5)
                        
                        overall_q = result.get('overall_quality', result.get('overall_quality_score', 0)) * 100
                        duration = result.get('duration_seconds', result.get('execution_duration_seconds', 0))
                        metrics = [
                            ("Execution ID", result.get("execution_id", "N/A")[:8] + "..."),
                            ("Status", result.get("status", "Unknown")),
                            ("Quality Score", f"{overall_q:.1f}/100"),
                            ("Duration", f"{duration:.1f}s"),
                            ("Task Confidence", f"{result.get('task_confidence', 0)*100:.0f}%")
                        ]
                        
                        for col, (label, value) in zip(summary_cols, metrics):
                            with col:
                                st.metric(label, value)
                        
                        # Detailed agent results
                        st.markdown("### 🤖 Agent Outputs")
                        
                        agent_tabs = st.tabs([
                            "Task Analysis",
                            "Generated Code",
                            "Test Suite",
                            "Execution Results",
                            "PR Details"
                        ])
                        
                        with agent_tabs[0]:  # Task Agent
                            st.subheader("Task Analysis")
                            task_output = result.get("task_agent_output") or result.get("parsed_requirements")
                            if task_output:
                                if isinstance(task_output, dict):
                                    st.json(task_output)
                                else:
                                    st.code(str(task_output))
                            else:
                                # Show quality scores as fallback
                                st.metric("Task Confidence", f"{result.get('task_confidence', 0)*100:.0f}%")
                                st.info("Detailed task analysis not returned. Check Pipeline History for full details.")
                        
                        with agent_tabs[1]:  # Coding Agent
                            st.subheader("Generated PySpark Code")
                            code_output = result.get("coding_agent_output") or result.get("generated_code")
                            if code_output:
                                if isinstance(code_output, dict):
                                    generated_code = code_output.get("pipeline_code") or code_output.get("generated_code", "")
                                    st.code(generated_code, language="python")
                                    if "pydantic_models" in code_output:
                                        with st.expander("📋 Pydantic Models"):
                                            st.code(code_output["pydantic_models"], language="python")
                                else:
                                    st.code(str(code_output), language="python")
                            else:
                                st.metric("Code Quality", f"{result.get('code_quality', 0)*100:.0f}%")
                                st.info("Generated code stored on GitHub — check the PR for the full source.")
                        
                        with agent_tabs[2]:  # Test Agent
                            st.subheader("Generated Test Suite")
                            test_output = result.get("test_agent_output") or result.get("generated_tests")
                            if test_output:
                                if isinstance(test_output, dict):
                                    test_code = test_output.get("test_code") or test_output.get("generated_tests", "")
                                    st.code(test_code, language="python")
                                    test_results = test_output.get("test_results", {})
                                    if test_results:
                                        with st.expander("✅ Test Results"):
                                            st.json(test_results)
                                else:
                                    st.code(str(test_output), language="python")
                            else:
                                st.metric("Test Quality", f"{result.get('test_quality', 0)*100:.0f}%")
                                st.info("Test suite stored on GitHub — check the PR for the full source.")
                        
                        with agent_tabs[3]:  # Execution Agent
                            st.subheader("Execution Results")
                            exec_output = result.get("execution_agent_output") or result.get("execution_result")
                            if exec_output:
                                if isinstance(exec_output, dict):
                                    st.json(exec_output)
                                else:
                                    st.code(str(exec_output))
                            else:
                                log = result.get("execution_log", [])
                                if log:
                                    for entry in log:
                                        st.write(entry)
                                else:
                                    st.info("No execution results (PySpark not available in serverless environment)")
                        
                        with agent_tabs[4]:  # PR Agent
                            st.subheader("Pull Request Details")
                            pr_output = result.get("pr_agent_output") or result.get("pull_request")
                            if pr_output:
                                if isinstance(pr_output, dict):
                                    pr_url = pr_output.get("pr_url") or pr_output.get("html_url")
                                    pr_number = pr_output.get("pr_number") or pr_output.get("number")
                                    if pr_url:
                                        st.success(f"✅ Pull Request #{pr_number} created!")
                                        st.markdown(f"### 🔗 [View PR #{pr_number} on GitHub]({pr_url})")
                                    with st.expander("PR Details (JSON)"):
                                        st.json(pr_output)
                                else:
                                    st.text(str(pr_output))
                            else:
                                st.metric("PR Quality", f"{result.get('pr_quality', 0)*100:.0f}%")
                                st.info("PR created on GitHub — see the link above or visit the GitHub repo.")
                        
                    else:
                        st.error(f"❌ Error: {response.status_code}")
                        st.code(response.text)
                        
                except requests.exceptions.ConnectionError:
                    st.error("❌ Cannot connect to API. Ensure FastAPI is running:\n`python -m uvicorn src.api:app --reload`")
                except requests.exceptions.Timeout:
                    st.warning("⏱️ Request timed out. The pipeline may still be processing. Check Pipeline History tab.")
                except Exception as e:
                    st.error(f"❌ Error: {str(e)}")

# ============================================================================
# TAB 2: Pipeline History
# ============================================================================
with tab2:
    st.header("📊 Pipeline Execution History")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        limit = st.number_input("Limit results:", min_value=1, value=10)
    with col2:
        offset = st.number_input("Offset:", min_value=0, value=0)
    with col3:
        status_filter = st.selectbox("Filter by status:", ["All", "success", "failed", "pending"])

    if st.button("🔄 Load Pipeline History"):
        try:
            params = {"limit": limit, "offset": offset}
            if status_filter != "All":
                params["status"] = status_filter
            
            response = requests.get(
                f"{api_url}/pipelines",
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total", 0)
                pipelines = data.get("pipelines", [])
                
                st.metric("Total Pipelines", total)
                
                if pipelines:
                    # Convert to DataFrame for better display
                    df_data = []
                    for p in pipelines:
                        df_data.append({
                            "ID": p.get("execution_id", "")[:8],
                            "Title": p.get("title", "")[:40],
                            "Status": p.get("status", ""),
                            "Quality Score": f"{p.get('overall_quality_score', 0):.1f}",
                            "Duration (s)": f"{p.get('execution_duration_seconds', 0):.1f}",
                            "Created": p.get("created_at", "")[:10]
                        })
                    
                    df = pd.DataFrame(df_data)
                    st.dataframe(df, use_container_width=True)
                    
                    # Click on row to see details
                    selected_idx = st.selectbox("Select pipeline for details:", range(len(pipelines)))
                    if selected_idx is not None:
                        selected_pipeline = pipelines[selected_idx]
                        
                        with st.expander("📋 Full Pipeline Details"):
                            st.json(selected_pipeline)
                else:
                    st.info("No pipelines found")
            else:
                st.error(f"Error: {response.status_code}")
        except Exception as e:
            st.error(f"Error loading history: {str(e)}")

# ============================================================================
# TAB 3: Analytics
# ============================================================================
with tab3:
    st.header("📈 Analytics Dashboard")
    
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("📊 Load Analytics Summary"):
            try:
                response = requests.get(f"{api_url}/pipelines/analytics/summary", timeout=10)
                if response.status_code == 200:
                    analytics = response.json()
                    
                    # Display metrics
                    metric_cols = st.columns(4)
                    
                    with metric_cols[0]:
                        st.metric("Total Executions", analytics.get("total_executions", 0))
                    with metric_cols[1]:
                        st.metric("Successful", analytics.get("successful", 0))
                    with metric_cols[2]:
                        st.metric("Failed", analytics.get("failed", 0))
                    with metric_cols[3]:
                        success_rate = analytics.get("success_rate", 0)
                        st.metric("Success Rate", f"{success_rate*100:.1f}%" if success_rate else "N/A")
                    
                    # Quality score
                    avg_quality = analytics.get("average_quality", 0)
                    st.metric("Average Quality Score", f"{avg_quality:.2f}/100")
                    
                    # Gauge chart for quality
                    fig = go.Figure(go.Indicator(
                        mode="gauge+number",
                        value=avg_quality,
                        title="Overall Quality",
                        domain={'x': [0, 1], 'y': [0, 1]},
                        gauge={
                            'axis': {'range': [0, 100]},
                            'bar': {'color': "darkblue"},
                            'steps': [
                                {'range': [0, 50], 'color': "lightgray"},
                                {'range': [50, 80], 'color': "gray"}],
                            'threshold': {
                                'line': {'color': "red", 'width': 4},
                                'thickness': 0.75,
                                'value': 90}}
                    ))
                    fig.update_layout(height=400)
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error loading analytics: {str(e)}")
    
    with col2:
        if st.button("📉 Load Status Breakdown"):
            try:
                response = requests.get(
                    f"{api_url}/pipelines/analytics/by-status",
                    timeout=10
                )
                if response.status_code == 200:
                    status_data = response.json()
                    
                    # Create pie chart
                    statuses = list(status_data.keys())
                    counts = list(status_data.values())
                    
                    fig = px.pie(
                        values=counts,
                        names=statuses,
                        title="Pipeline Status Distribution",
                        hole=0.3
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
            except Exception as e:
                st.error(f"Error: {str(e)}")

# ============================================================================
# TAB 4: Data Lineage
# ============================================================================
with tab4:
    st.header("🔗 Data Lineage & Governance")
    
    st.markdown("""
    Track data flows through your pipelines and understand transformation lineage.
    """)
    
    lineage_tabs = st.tabs(["Datasets", "Transformations", "Lineage Graph"])
    
    with lineage_tabs[0]:
        st.subheader("📊 Discovered Datasets")
        if st.button("Load Datasets"):
            try:
                response = requests.get(
                    f"{api_url}/lineage/datasets",
                    params={"limit": 20},
                    timeout=10
                )
                if response.status_code == 200:
                    datasets = response.json()
                    if isinstance(datasets, list):
                        st.json(datasets)
                    else:
                        st.info(datasets.get("message", "No datasets found"))
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    with lineage_tabs[1]:
        st.subheader("🔄 Transformations")
        if st.button("Load Transformations"):
            try:
                response = requests.get(
                    f"{api_url}/lineage/transformations",
                    timeout=10
                )
                if response.status_code == 200:
                    transformations = response.json()
                    st.json(transformations)
            except Exception as e:
                st.error(f"Error: {str(e)}")
    
    with lineage_tabs[2]:
        st.subheader("🎯 Lineage DAG")
        execution_id = st.text_input(
            "Enter Execution ID:",
            placeholder="Paste execution ID from pipeline history"
        )
        
        if execution_id and st.button("Load Lineage Graph"):
            try:
                response = requests.get(
                    f"{api_url}/pipelines/{execution_id}/lineage",
                    timeout=10
                )
                if response.status_code == 200:
                    lineage_data = response.json()
                    st.json(lineage_data)
            except Exception as e:
                st.error(f"Error: {str(e)}")

# ============================================================================
# Footer
# ============================================================================
st.markdown("---")
st.markdown("""
<div style='text-align: center; margin-top: 3rem;'>
    <p>🚀 <strong>Autonomous ETL/ELT Agent</strong> | AI-powered pipeline generation</p>
    <p><small>Powered by LangGraph, OpenAI, FastAPI & Streamlit</small></p>
    <p><a href='https://github.com/amalphonse/Autonomous-ETL-ELT-Agent-for-DevOps-Driven-Data-Engineering'>GitHub Repository</a></p>
</div>
""", unsafe_allow_html=True)
