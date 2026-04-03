# Architecture Decision Records (ADRs)

This directory contains Architecture Decision Records for the Autonomous ETL/ELT Agent project.

## What is an ADR?

An Architecture Decision Record (ADR) is a lightweight method of recording important architectural decisions made throughout the development of a software system. Each ADR documents:

- The decision that was made
- The context and rationale
- The consequences and trade-offs
- Alternatives that were considered

This provides a historical record of why certain architectural choices were made, which is valuable for future maintainers and architects.

## ADR Format

Each ADR follows this structure:
- **Title**: A short, descriptive title
- **Status**: Proposed, Accepted, Deprecated, Superseded
- **Context**: The issue or requirement that prompted the decision
- **Decision**: What was decided
- **Rationale**: Why this decision was made
- **Consequences**: The positive and negative impacts
- **Alternatives**: Other options that were considered

## List of ADRs

1. [ADR-001: Use LangGraph for Multi-Agent Orchestration](./ADR-001-langgraph-orchestration.md)
2. [ADR-002: SQLAlchemy ORM for Database Abstraction](./ADR-002-sqlalchemy-orm.md)
3. [ADR-003: Bearer Token Authentication for FastAPI](../api.py) *(see Bearer token implementation in API)*
4. [ADR-004: Streamlit for Interactive Dashboard](./ADR-004-streamlit-dashboard.md)
