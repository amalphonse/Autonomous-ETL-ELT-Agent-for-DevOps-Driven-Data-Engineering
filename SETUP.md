# Setup Guide - Autonomous ETL/ELT Agent

Complete setup instructions for running the Autonomous ETL/ELT Agent system.

## Prerequisites

- **Python 3.12.6** or higher
- **pip 24.2** or higher
- **Git** (for version control)

Verify your Python version:
```bash
python3.12 --version
pip3.12 --version
```

## Installation

### 1. Clone the Repository

```bash
git clone https://github.com/amalphonse/Autonomous-ETL-ELT-Agent-for-DevOps-Driven-Data-Engineering.git
cd Autonomous-ETL-ELT-Agent-for-DevOps-Driven-Data-Engineering
```

### 2. Install Dependencies

```bash
pip3.12 install -r requirements.txt
```

This installs:
- **LangChain & LangGraph** - Agent orchestration framework
- **OpenAI** - GPT-4o access
- **FastAPI & Uvicorn** - REST API server
- **PySpark & Delta Lake** - Data processing
- **PyGithub** - GitHub integration
- **Pytest** - Test framework
- And more (see `requirements.txt`)

### 3. Configure Environment Variables

Copy the example environment file:
```bash
cp .env.example .env
```

Edit `.env` with your credentials:
```bash
nano .env  # or use your favorite editor
```

Required values:
- **OPENAI_API_KEY** - Get from [OpenAI API Keys](https://platform.openai.com/api-keys)
- **GITHUB_TOKEN** - Create at [GitHub Personal Access Tokens](https://github.com/settings/tokens)
  - Required scopes: `repo`, `workflow`
- **GITHUB_REPO_OWNER** - Your GitHub username
- **GITHUB_REPO_NAME** - Repository name
- **GCP_PROJECT_ID** - Your Google Cloud project ID

Secure your `.env` file:
```bash
chmod 600 .env
```

## Quick Start

### Run the FastAPI Server

```bash
python3.12 -m uvicorn src.api:app --reload
```

Server starts at: `http://localhost:8000`

### Create a Pipeline

```bash
curl -X POST http://localhost:8000/pipelines/create \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Customer Orders ETL",
    "description": "Load customer orders from Salesforce to Snowflake",
    "source_system": "Salesforce",
    "target_system": "Snowflake",
    "data_quality_rules": [
      "Order ID must be unique",
      "Order date must be valid",
      "Customer ID must exist"
    ]
  }'
```

Response:
```json
{
  "execution_id": "uuid-...",
  "status": "success",
  "task_confidence": 0.95,
  "code_quality": 0.88,
  "test_quality": 0.85,
  "pr_quality": 0.89,
  "overall_quality": 0.87,
  "execution_log": [
    "✅ Task Agent: Requirements parsed successfully",
    "✅ Coding Agent: PySpark code generated successfully",
    "✅ Test Agent: pytest suites generated successfully",
    "✅ PR Agent: Pull Request prepared successfully"
  ]
}
```

### List All Pipelines

```bash
curl http://localhost:8000/pipelines
```

### Get Pipeline Details

```bash
curl http://localhost:8000/pipelines/{execution_id}
```

### Health Check

```bash
curl http://localhost:8000/
```

## Running Tests

### Run All Tests

```bash
python3.12 -m pytest tests/ -v
```

### Run Specific Test Suite

```bash
# Orchestration tests
python3.12 -m pytest tests/test_orchestration.py -v

# API tests
python3.12 -m pytest tests/test_api.py -v

# Agent tests
python3.12 -m pytest tests/test_coding_agent.py tests/test_test_agent.py tests/test_pr_agent.py -v
```

### Test Coverage

```bash
python3.12 -m pytest tests/ --cov=src --cov-report=html
```

Current Status: **75/76 tests passing** ✅

## Project Structure

```
autonomous_ETL_ELT_DevOps_Project/
├── src/
│   ├── __init__.py
│   ├── config.py                 # Environment configuration
│   ├── types.py                  # Base agent types & enums
│   ├── orchestration.py          # Multi-agent orchestrator
│   ├── api.py                    # FastAPI application
│   └── agents/
│       ├── task_agent/           # NLP parsing → requirements
│       ├── coding_agent/         # Generate PySpark code
│       ├── test_agent/           # Generate pytest suites
│       └── pr_agent/             # Create Pull Requests
├── tests/
│   ├── conftest.py
│   ├── test_orchestration.py     # Orchestrator tests (12)
│   ├── test_api.py               # FastAPI tests (15)
│   ├── test_coding_agent.py      # Coding agent tests (15)
│   ├── test_test_agent.py        # Test agent tests (13)
│   └── test_pr_agent.py          # PR agent tests (22)
├── docs/
│   └── IMPLEMENTATION_GUIDE.md
├── .env.example                  # Environment template
├── requirements.txt              # Python dependencies
├── pytest.ini                    # Test configuration
├── README.md                     # Project overview
└── SETUP.md                      # This file
```

## Workflow Overview

The system orchestrates 4 agents sequentially:

```
User Story (JSON)
    ↓
[Task Agent]
  - Parses requirements via NLP
  - Extracts transformations, data quality rules
  - Returns: ParsedRequirements
    ↓
[Coding Agent]
  - Generates PySpark transformation code
  - Creates Pydantic data models
  - Returns: GeneratedCode
    ↓
[Test Agent]
  - Creates pytest test suites
  - Calculates code coverage
  - Returns: GeneratedTests
    ↓
[PR Agent]
  - Creates Git branch (feature/...)
  - Writes commit messages
  - Composes PR description
  - Returns: GeneratedPullRequest
    ↓
Pipeline Result
  - status: success/failed
  - Quality scores (0.0-1.0)
  - Generated artifacts
  - Execution log
```

## API Endpoints

### Health Check
```
GET /
```

### Create Pipeline
```
POST /pipelines/create
Request Body:
{
  "title": "string",
  "description": "string",
  "source_system": "string?",
  "target_system": "string?",
  "data_quality_rules": ["string?"],
  "performance_requirements": {"string": "any?"}
}

Response:
{
  "execution_id": "string",
  "status": "success|failed",
  "task_confidence": number,
  "code_quality": number,
  "test_quality": number,
  "pr_quality": number,
  "overall_quality": number,
  "execution_log": ["string"],
  "error": "string?"
}
```

### Get Pipeline Details
```
GET /pipelines/{execution_id}

Response includes all fields from POST response plus:
{
  "parsed_requirements": {...},
  "generated_code": {...},
  "generated_tests": {...},
  "pull_request": {...}
}
```

### List Pipelines
```
GET /pipelines

Response:
{
  "total": number,
  "pipelines": [
    {
      "execution_id": "string",
      "status": "string",
      "story_title": "string",
      "overall_quality": number
    }
  ]
}
```

## Troubleshooting

### Import Errors

If you see `ModuleNotFoundError`, reinstall dependencies:
```bash
pip3.12 install -r requirements.txt --force-reinstall
```

### Missing API Keys

Error: `ValidationError: openai_api_key Field required`

Solution: Ensure `.env` exists and contains all required keys:
```bash
cat .env | grep OPENAI_API_KEY
```

### Port Already in Use

Error: `Address already in use`

Solution: Use a different port:
```bash
python3.12 -m uvicorn src.api:app --port 8001
```

### Python Version Mismatch

Ensure you're using Python 3.12:
```bash
which python3.12
python3.12 --version
```

## Development

### Linting & Formatting

```bash
# Format code
black src/ tests/

# Check syntax
flake8 src/ tests/

# Type checking
mypy src/
```

### Git Workflow

```bash
# Create a branch
git checkout -b feature/your-feature-name

# Make changes and test
python3.12 -m pytest tests/ -v

# Commit
git add -A
git commit -m "feat: describe your changes"

# Push
git push origin feature/your-feature-name
```

## Next Steps

1. **GitHub Integration**: Implement actual PR creation with PyGithub
2. **Environment Docs**: Add production deployment guide
3. **Monitoring**: Add observability metrics
4. **Performance**: Optimize LLM calls and parallelization

## Support

For issues or questions:
1. Check this SETUP.md file
2. Review [IMPLEMENTATION_GUIDE.md](docs/IMPLEMENTATION_GUIDE.md)
3. Run tests: `python3.12 -m pytest tests/ -v`
4. Check logs: `tail -f logs/app.log`

---

**Last Updated**: March 30, 2026
**Python Version**: 3.12.6
**Test Status**: 75/76 passing ✅
