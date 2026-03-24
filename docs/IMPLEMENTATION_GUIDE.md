# Task Agent Implementation Guide

**Status:** ✅ **Phase 1 & 2 Complete** - Foundation and Task Agent are ready

---

## Overview

We've successfully implemented the **Task Agent** for the Autonomous ETL/ELT System. The Task Agent is the entry point that parses raw DevOps user stories and extracts structured transformation requirements.

---

## What Was Built

### 1. **Project Foundation** (`Phase 1`)

#### Dependencies (`requirements.txt`)
- **LangChain & LangGraph:** Agent orchestration and LLM integration
- **FastAPI & Uvicorn:** REST API framework
- **Pydantic:** Data validation and schema definition
- **PySpark & Delta Lake:** Data processing
- **OpenAI:** LLM backend for NLP parsing
- **PyGithub:** GitHub API integration
- **pytest:** Testing framework
- **Google Cloud BigQuery:** Data warehouse integration

#### Configuration (`config.py` & `.env.example`)
- Environment variable management using Pydantic Settings
- Supports OpenAI, GitHub, GCP, and Spark configuration
- Cached settings singleton for efficient access

#### Base Abstractions (`types.py`)
- `Agent`: Abstract base class for all agents
- `AgentType`, `AgentStatus`: Enums for agent identification and status tracking
- `AgentInput`, `AgentOutput`: Standard input/output formats
- `OrchestrationState`: State machine for tracking workflow progress

---

### 2. **Task Agent Implementation** (`Phase 2`)

#### Schemas (`src/agents/task_agent/schemas.py`)
Comprehensive Pydantic models for:

- **UserStory**: Raw user story input (text, JSON, YAML)
- **TransformationStep**: Individual transformation operation
- **DataSource**: Input data source specification with schema
- **DataType**: Supported data types (string, int, float, timestamp, etc.)
- **ColumnDefinition**: Column schema definition
- **TransformationTypes**: filters, joins, aggregates, windows, dedups, pivots, etc.
- **DataQualityRule**: Validation rules (null checks, schema, uniqueness, range, pattern)
- **ParsedRequirements**: Complete structured requirements output
- **TaskAgentOutput**: Task agent response with confidence score

#### Implementation (`src/agents/task_agent/task_agent.py`)
Core Task Agent class featuring:

- **LLM Integration**: Uses OpenAI GPT-4o via LangChain
- **Prompt Engineering**: Detailed prompts guide LLM to extract structured requirements
- **NLP Parsing**: Converts free-form user stories → structured JSON requirements
- **JSON Parsing**: Robust JSON extraction from LLM responses
- **Confidence Scoring**: Calculates confidence of parsing quality (0-1)
- **Error Handling**: Comprehensive error handling and logging
- **Input Validation**: Validates user story format and structure

#### Key Methods

```python
# Parse a user story and extract requirements
agent = TaskAgent()
user_story = UserStory(
    user_id="user123",
    request_id="req456",
    story="Filter orders from last 30 days where amount > 1000..."
)
output = await agent.execute({"user_story": user_story.dict()})

# Output contains:
# - requirements: ParsedRequirements object with transformation steps
# - confidence_score: 0.0-1.0 indication of parsing quality
# - raw_analysis: Raw LLM response for debugging
```

---

#### Unit Tests (`tests/test_task_agent.py`)
Comprehensive test coverage for:

- **Initialization**: Proper agent setup with LangChain components
- **Input Validation**: Valid/invalid user story formats
- **JSON Parsing**: Handle LLM responses with and without JSON wrapping
- **Formatting**: User story preprocessing for LLM
- **Confidence Scoring**: Scoring logic validation
- **Execution**: End-to-end parsing workflow
- **Error Handling**: LLM failures, invalid inputs
- **Schemas**: Pydantic model validation

Run tests with:
```bash
pytest tests/test_task_agent.py -v
```

---

## Project Structure

```
Autonomous ETL:ELT Agent for DevOps-Driven Data Engineering/
├── src/
│   ├── __init__.py                    # Package marker
│   ├── config.py                      # Configuration & settings
│   ├── types.py                       # Base agent types & abstractions
│   └── agents/
│       ├── __init__.py
│       └── task_agent/
│           ├── __init__.py
│           ├── schemas.py             # Pydantic models for Task Agent
│           └── task_agent.py          # TaskAgent implementation
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py                    # Pytest configuration
│   └── test_task_agent.py             # Unit tests
│
├── framework/                         # (Empty - for DE standards/templates)
├── orchestration/                     # (Empty - for Airflow DAG templates)
├── docs/
│   └── backup/                        # README backup with citations
│
├── requirements.txt                   # Python dependencies
├── .env.example                       # Environment variable template
├── pytest.ini                         # Pytest configuration
└── README.md                          # Project overview with architecture diagrams
```

---

## How to Use the Task Agent

### 1. **Setup**

```bash
# Install dependencies
pip install -r requirements.txt

# Create .env file from template
cp .env.example .env

# Fill in your API keys:
# - OPENAI_API_KEY
# - GITHUB_TOKEN
# - GCP credentials, etc.
```

### 2. **Basic Usage**

```python
from src.agents.task_agent import TaskAgent, UserStory
import asyncio

async def main():
    # Initialize the agent
    agent = TaskAgent()
    
    # Create a user story
    story = UserStory(
        user_id="analyst_001",
        request_id="etl_001",
        story="""
        I need to build an ETL pipeline that:
        1. Reads customer transaction data from S3 (CSV format)
        2. Filters for transactions in the last 90 days
        3. Joins with customer dimension table
        4. Aggregates by region to calculate total revenue
        5. Outputs results to BigQuery in the analytics table
        
        The pipeline should run daily and complete within 2 hours.
        """,
        format="text"
    )
    
    # Execute the agent
    output = await agent.execute({"user_story": story.dict()})
    
    # Access results
    if output.status == "success":
        requirements = output.data["requirements"]
        confidence = output.data["confidence_score"]
        
        print(f"✓ Parsed with {confidence:.1%} confidence")
        print(f"  Input sources: {len(requirements['input_sources'])}")
        print(f"  Transformation steps: {len(requirements['transformation_steps'])}")
        print(f"  Output location: {requirements['output_location']}")
    else:
        print(f"✗ Parsing failed: {output.error}")

asyncio.run(main())
```

### 3. **With FastAPI (Coming Next)**

Once the API server is implemented, you'll be able to:

```bash
# Start the server
uvicorn src.main:app --reload

# Submit a user story via HTTP
curl -X POST http://localhost:8000/api/tasks/parse \
  -H "Content-Type: application/json" \
  -d '{
    "user_id": "analyst_001",
    "request_id": "etl_001",
    "story": "Filter and aggregate transaction data..."
  }'
```

---

## What the Task Agent Extracts

From a user story, the Task Agent identifies:

### **Input Data Sources**
- Data location (S3, BigQuery, Delta Lake, etc.)
- Format (CSV, Parquet, JSON, Delta)
- Schema (columns, types, nullability)
- Whether streaming or batch

### **Transformation Steps** (in order)
- **Filter**: Row-level filtering with conditions
- **Join**: Combining multiple data sources
- **Aggregate**: Grouping and summarization
- **Window**: Time-window calculations
- **Dedup**: Removing duplicates
- **Union**: Combining datasets
- **Pivot**: Reshaping data
- **Custom**: Any other transformations

### **Output Schema**
- Column names and data types
- Nullability constraints
- Descriptions

### **Quality Rules**
- Null checks
- Schema validation
- Uniqueness constraints
- Value ranges
- Pattern matching

### **Metadata**
- Execution frequency (daily, hourly, etc.)
- SLA (service level agreement)
- Upstream dependencies
- Custom metadata

---

## Next Steps

With the Task Agent complete, the architecture flow is:

```
┌───────────────────┐
│  User Story       │
│  (JSON/YAML/Text) │
└────────┬──────────┘
         │
         ▼
┌───────────────────────────────────┐
│  Task Agent (COMPLETE ✓)          │  ← You are here
│  - Parse requirements             │
│  - Extract transformations        │
│  - Define schemas & quality rules │
└────────┬────────────────────────┘
         │
         ▼
    [Coding Agent]           ← Next: Generate PySpark code + Pydantic models
         │
         ▼
    [Test Agent]             ← Generate pytest test suite
         │
         ▼
    [PR Agent]               ← Create GitHub PR with code
         │
         ▼
┌───────────────────────┐
│  Production Ready PR  │
├───────────────────────┤
│ ✓ PySpark code        │
│ ✓ Tests               │
│ ✓ Schema validation   │
│ ✓ Quality checks      │
└───────────────────────┘
```

## Next Implementation: Coding Agent

The **Coding Agent** will:
1. Take parsed requirements from Task Agent
2. Generate modular PySpark code using Delta Lake patterns
3. Create Pydantic models for schema validation
4. Return code ready for testing

Would you like to proceed with building the **Coding Agent**?

---

## Testing

Run all tests:
```bash
pytest tests/ -v
```

Run specific test file:
```bash
pytest tests/test_task_agent.py -v
```

Run with coverage:
```bash
pytest tests/ --cov=src --cov-report=html
```

---

## Architecture Notes

- **async/await**: The agent uses async execution for LLM calls (supporting LangGraph's async-first design)
- **Error Handling**: Comprehensive logging with `loguru` for debugging
- **Extensibility**: Abstract `Agent` base class allows easy addition of new agents
- **Type Safety**: Full Pydantic validation ensures data consistency
- **LLM Integration**: Prompt engineering guides GPT-4o to produce consistent JSON output

---

## Troubleshooting

**"OPENAI_API_KEY not set"**
```bash
# Make sure your .env file has:
OPENAI_API_KEY=sk-....
```

**"Parser error: Could not parse JSON"**
- The LLM response may have been malformed
- Check the `.data["raw_analysis"]` in the output for what the LLM returned
- Consider adjusting the temperature in config.py (current: 0.3)

**Tests failing with import errors**
```bash
# Make sure project root is in PYTHONPATH
export PYTHONPATH="${PYTHONPATH}:/path/to/project"
pytest tests/
```

---

## References

- [LangChain Documentation](https://python.langchain.com/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [Pydantic Documentation](https://docs.pydantic.dev/)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [OpenAI API Reference](https://platform.openai.com/docs/api-reference)
