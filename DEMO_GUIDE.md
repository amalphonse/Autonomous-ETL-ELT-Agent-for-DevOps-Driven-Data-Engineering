# 🎯 Autonomous ETL/ELT Agent - Demo Guide

## Quick Start: Run the Demo UI

### Prerequisites
Ensure you have:
- Python 3.12+
- Virtual environment activated
- Dependencies installed
- Valid `.env` file with API keys

### Step 1: Install Frontend Dependencies

```bash
# Make sure you're in the virtual environment
source .venv/bin/activate

# Install the newly added dependencies (Streamlit & Plotly)
pip install --upgrade -r requirements.txt
```

### Step 2: Start the FastAPI Backend

Open Terminal Window 1 and run:

```bash
# Navigate to project root
cd /Users/anjuma/autonomous_ETL_ELT_DevOps_Project

# Activate virtual environment
source .venv/bin/activate

# Start the FastAPI server
python -m uvicorn src.api:app --reload --host 0.0.0.0 --port 8000
```

You should see:
```
INFO:     Uvicorn running on http://0.0.0.0:8000
```

### Step 3: Start the Streamlit Frontend

Open Terminal Window 2 and run:

```bash
# Navigate to project root
cd /Users/anjuma/autonomous_ETL_ELT_DevOps_Project

# Activate virtual environment
source .venv/bin/activate

# Launch Streamlit app
streamlit run streamlit_app.py
```

This will:
- Launch Streamlit on `http://localhost:8501`
- Auto-open in your default browser
- Show the main demo interface

**Output:**
```
  You can now view your Streamlit app in your browser.

  Local URL: http://localhost:8501
  Network URL: http://192.168.x.x:8501
```

---

## 🎬 Demo Flow

### Tab 1: Submit User Story

This is the **core interactive feature** for demoing the system.

**Steps:**
1. Fill in the form with a user story (see examples below)
2. Click "🚀 Submit Story & Generate Pipeline"
3. Watch as the system orchestrates 5 agents in sequence:
   - ✏️ **Task Agent** - Parses requirements
   - 🔧 **Coding Agent** - Generates PySpark code
   - ✅ **Test Agent** - Auto-generates unit tests
   - ⚡ **Execution Agent** - Runs the code safely
   - 📤 **PR Agent** - Creates GitHub Pull Request

4. View detailed outputs from each agent in tabs:
   - Task Analysis (parsed intent)
   - Generated Code (complete PySpark pipeline)
   - Test Suite (pytest coverage)
   - Execution Results (metrics & logs)
   - PR Details (GitHub link)

### Tab 2: Pipeline History

View all previously executed pipelines with:
- Execution ID (first 8 chars)
- User story title
- Status (success/failed)
- Quality score (0-100)
- Duration
- Creation timestamp

**Features:**
- Pagination (limit/offset)
- Status filtering
- Click to see full execution details

### Tab 3: Analytics

Dashboard showing:
- Total execution count
- Success/failure breakdown
- Success rate percentage
- Average quality score
- Gauge chart for quality visualization
- Pie chart for status distribution

### Tab 4: Data Lineage

Track data flows through pipelines:
- **Datasets** - All source & target datasets discovered
- **Transformations** - All operations (filter, join, aggregate, union, select)
- **Lineage Graph** - DAG visualization with nodes and edges

---

## 📋 Example User Stories for Testing

Copy/paste these into the UI to test different scenarios:

### Example 1: Customer Analytics Pipeline

**Title:** `Transform Customer Orders to Analytics`

**Description:**
```
Load customer orders from our Salesforce CRM system. Join with product master data to get product categories and pricing. 
Filter only completed orders from the last 12 months. Aggregate by customer_id to calculate:
- Total orders per customer
- Total revenue per customer  
- Average order value
- Last order date

Write the final summary to our analytics data warehouse with customer demographics included.
```

**Source System:** `Salesforce CRM`

**Target System:** `Snowflake Data Warehouse`

**Quality Rules:** 
- No NULL values in key columns
- Unique constraint on ID columns
- Valid date ranges
- Data type validation

---

### Example 2: Real-time Log Processing

**Title:** `Process and Aggregate Application Logs`

**Description:**
```
Stream application logs from S3 that are generated every minute. Parse the JSON logs to extract:
- Timestamp
- Service name
- Log level (ERROR, WARN, INFO)
- Error message/stack trace

Filter for ERROR and WARN level logs only. Group by service and hour to count:
- Total errors per service per hour
- Unique error types
- Error frequency

Write aggregated metrics to Delta Lake for real-time dashboarding. Include alerts for services exceeding 100 errors/hour.
```

**Source System:** `AWS S3 Logs`

**Target System:** `Delta Lake`

**Quality Rules:** 
- No NULL values in key columns
- Valid date ranges
- Data type validation

---

### Example 3: Financial Reconciliation

**Title:** `Reconcile Daily Transactions Across Systems`

**Description:**
```
Read daily transactions from two systems:
1. Bank API - transactions with transaction_id, amount, date
2. Accounting system - journal entries with transaction_ref, amount, date

Join both datasets on transaction ID. Identify:
- Matching transactions
- Missing in bank (accounting-only)
- Missing in accounting (bank-only)
- Amount discrepancies
- Date discrepancies

Generate reconciliation report with:
- Unmatched transaction count
- Total amount variance
- Exception details for manual review

Write to PostgreSQL for auditing.
```

**Source System:** `Bank API + PostgreSQL Accounting`

**Target System:** `PostgreSQL Data Lake`

**Quality Rules:**
- Unique constraint on ID columns
- Valid date ranges
- Referential integrity checks

---

## 🔧 Configuration

### Change API URL

In the Streamlit sidebar:
1. Default is `http://localhost:8000`
2. If running on different server, change URL and click "Check API Connection"
3. Should show "✅ API is running!" if healthy

### Running on Different Machines

**Server Machine A (FastAPI Backend):**
```bash
python -m uvicorn src.api:app --host 0.0.0.0 --port 8000
```

**Client Machine B (Streamlit Frontend):**
```bash
streamlit run streamlit_app.py
# Then in sidebar, change API URL to: http://<MACHINE_A_IP>:8000
# e.g., http://192.168.1.100:8000
```

---

## 📊 What to Show in Demo

### Complete End-to-End Flow

1. **Input Stage** (Tab 1)
   - Fill user story form
   - Show how natural language is captured

2. **Processing Stage**
   - Monitor as system processes through 5 agents
   - Mention LangGraph orchestration under the hood
   - Note the quality scores updating

3. **Output Stage** (Still Tab 1)
   - **Task Agent Output** - Show parsed requirements
   - **Generated Code** - Highlight production-ready PySpark code
   - **Test Suite** - Show auto-generated unit tests with null checks, schema validation
   - **Execution Results** - Show metrics: rows processed, duration, quality
   - **PR Link** - Show GitHub PR created automatically

4. **Historical Perspective** (Tab 2)
   - Show Pipeline History table
   - Demonstrate sorting/filtering
   - Click on existing pipeline to show stored details

5. **Analytics View** (Tab 3)
   - Show aggregate metrics
   - Highlight quality score gauge
   - Status breakdown pie chart

6. **Data Governance** (Tab 4)
   - Show lineage for a pipeline
   - Demonstrate dataset discovery
   - Show transformation mapping

---

## 🐛 Troubleshooting

### Issue: "Cannot reach API. Ensure FastAPI is running"

**Solution:**
```bash
# Check if FastAPI is running
curl http://localhost:8000/health

# If not, start it
python -m uvicorn src.api:app --reload
```

### Issue: Streamlit shows "ModuleNotFoundError: No module named 'streamlit'"

**Solution:**
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt

# Or manually:
pip install streamlit==1.28.1 plotly==5.17.0
```

### Issue: "Request timed out"

**Solution:**
- API calls timeout after 5 minutes
- LLM call may be slow
- Check API logs for errors
- Try a simpler user story (fewer words)

### Issue: No results in Pipeline History

**Solution:**
- Execute at least one pipeline first (Tab 1)
- Check that the database file exists: `etl_agent.db`
- Verify database is initialized:
  ```bash
  python -c "from src.database.db import init_db; init_db()"
  ```

---

## 🚀 Advanced Demo Scenarios

### Scenario 1: Show Agent Specialization

**Goal:** Demonstrate how each agent has a specific role

Submit one user story, then compare outputs:
- Task Agent's parsed intent vs. original description
- Coding Agent's code structure vs. requirements
- Test Agent's test coverage vs. edge cases
- Execution Agent's metrics vs. performance goals

**Talking Points:**
- "Each agent is specialized in LangChain"
- "LangGraph orchestrates them in sequence"
- "Each one validates the previous output"

---

### Scenario 2: Show Code Quality

**Goal:** Highlight production-readiness

Examine generated code for:
- Delta Lake patterns (UPSERT, MERGE)
- Error handling with try/except
- Logging and metrics collection
- Pydantic model validation
- Type hints throughout
- Documentation strings

**Talking Points:**
- "Code follows organizational standards"
- "Auto-generated but production-ready"
- "Aligns with delta lake best practices"

---

### Scenario 3: Show Test Coverage

**Goal:** Demonstrate autonomous testing

Look at generated test suite for:
- Unit tests for each transformation
- Null checks for key columns
- Schema validation
- Edge case handling
- Integration tests

Click "Test Results" to see:
- Which tests passed/failed
- Coverage percentage
- Assert failures (if any)

**Talking Points:**
- "Tests auto-generated from requirements"
- "Coverage for null handling"
- "Business logic validation"

---

### Scenario 4: Show Lineage & Governance

**Goal:** Show data compliance capabilities

1. Submit pipeline (Tab 1)
2. Get execution ID from results
3. Go to Tab 4 (Data Lineage)
4. Paste execution ID
5. View lineage graph with:
   - Source datasets
   - Transformation nodes
   - Target datasets

**Talking Points:**
- "Compliance tracking built-in"
- "OpenLineage protocol compliance"
- "Automatic documentation"

---

## 📹 Recording Demo Tips

### Camera Setup
- Show code in one half
- Show Streamlit in other half
- This shows real-time code generation

### Demo Script

```
1. "This is an autonomous ETL agent system"
   → Show README architecture diagram

2. "Let's see it in action with a real user story"
   → Fill out customer analytics form

3. "Submit and watch as 5 agents orchestrate automatically"
   → Submit story, show spinner

4. "First, the Task Agent parses requirements"
   → Click Task Analysis tab

5. "Then Coding Agent generates production-ready PySpark code"
   → Show generated code, highlight delta lake patterns

6. "Test Agent auto-generates pytest suite"
   → Show test code, highlight null checks

7. "Execution Agent safely runs the code"
   → Show execution results and metrics

8. "PR Agent creates a GitHub PR automatically"
   → Show PR link

9. "All results are stored with lineage for compliance"
   → Switch to lineage tab, show graph

Total demo time: 5-7 minutes
```

---

## 🎓 Learning Resources

- **LangGraph Docs:** https://langchain-ai.github.io/langgraph/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **Streamlit Docs:** https://docs.streamlit.io/
- **PySpark Docs:** https://spark.apache.org/docs/latest/api/python/
- **Delta Lake:** https://docs.delta.io/

---

## 📞 Support

For issues:
1. Check logs: `tail -f logs/app.log`
2. Check API health: `curl http://localhost:8000/health`
3. Review `src/config.py` for settings
4. See main README.md for architecture details
