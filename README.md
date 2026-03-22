# Autonomous ETL/ELT Agent for DevOps-Driven Data Engineering

An AI-powered agentic system that automates the Data Engineering lifecycle—transforming DevOps user stories into production-ready, tested, and PR-ready Spark pipelines.

## 🚀 Project Overview
[cite_start]This system minimizes manual effort in the DE lifecycle by using **Agentic AI** to interpret requirements and generate code that aligns with organizational standards[cite: 14]. [cite_start]It specifically targets the transition from a "User Story" to a "Pull Request" without human intervention for standard ETL tasks[cite: 91].

### Key Features
* [cite_start]**NLP Story Parsing:** Extracts transformation intent (filter, join, aggregate) from JSON/YAML DevOps tasks[cite: 16, 22].
* [cite_start]**Automated Spark Generation:** Produces modular PySpark code using Delta Lake patterns[cite: 24, 28].
* [cite_start]**Autonomous Validation:** Auto-generates and runs `pytest` suites including null-checks and schema assertions.
* [cite_start]**Git Automation:** Creates branches, commits code, and raises Pull Requests via GitHub API[cite: 61, 101].
* [cite_start]**Orchestration Ready:** Generates minimal Airflow DAGs for immediate scheduling[cite: 38, 109].

## 🏗 Architecture
[cite_start]The project utilizes a **Multi-Agent Orchestration** pattern powered by **LangGraph**:
1. [cite_start]**Task Agent:** Requirements extraction & mapping[cite: 53].
2. [cite_start]**Coding Agent:** PySpark & Pydantic model generation[cite: 56].
3. [cite_start]**Test Agent:** Unit testing & business logic validation[cite: 30].
4. [cite_start]**PR Agent:** Repository operations & documentation[cite: 60].

## 🛠 Tech Stack
* [cite_start]**AI Engine:** OpenAI GPT-4o / LangChain / LangGraph [cite: 115, 116]
* [cite_start]**Data Processing:** Apache Spark (PySpark) & Delta Lake [cite: 119, 120]
* **Data Warehouse:** Google BigQuery (Storage & Ingestion)
* [cite_start]**Validation:** Pydantic (Schema) & Pytest (Logic) [cite: 117, 131]
* [cite_start]**API/Web:** FastAPI & Uvicorn [cite: 122]
* [cite_start]**DevOps:** GitHub API (PyGithub) [cite: 123]

## 📂 Project Structure
```text
├── src/                # Core Agent logic and FastAPI endpoints
├── framework/          # Predefined DE standards and templates
├── tests/              # Test suites for the Agent and generated code
├── orchestration/      # Airflow DAG templates
├── docs/               # Architecture diagrams and runbooks
└── .env.example        # Environment variables (GCP/OpenAI/GitHub)