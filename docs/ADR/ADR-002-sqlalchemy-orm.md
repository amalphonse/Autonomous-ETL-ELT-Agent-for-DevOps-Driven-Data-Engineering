# ADR-002: SQLAlchemy ORM for Database Abstraction

**Status**: Accepted

**Date**: April 2026

## Context

The system needs to persist pipeline execution data, including:
- Execution metadata (ID, status, timestamps)
- Agent outputs (code, tests, requirements)
- Quality metrics and execution logs
- User story details

We need a database abstraction layer that:
- Works with both SQLite (development) and PostgreSQL (production)
- Provides type-safe data access
- Supports migrations
- Handles schema evolution

## Decision

**Use SQLAlchemy ORM (version 2.0+) with Alembic for migrations.**

SQLAlchemy provides:
- **Declarative Models**: Define schema as Python classes
- **Type Safety**: Python type hints for columns
- **Multi-Database Support**: Works with SQLite, PostgreSQL, MySQL, etc.
- **Relationship Management**: FK constraints and relationships
- **Query Builder**: Pythonic query API

## Rationale

1. **Industry Standard**: Most used Python ORM in production systems
2. **Multi-Database**: Switch from SQLite to PostgreSQL without code changes
3. **Alembic Integration**: Automatic migration generation and tracking
4. **Async Support**: SQLAlchemy 2.0 supports async operations
5. **Community**: Extensive documentation and community support

## Consequences

**Positive**:
- Database abstraction enables flexible deployment
- Migrations tracked in git for infrastructure-as-code
- Type hints caught by IDE and linters
- Easy to test with in-memory SQLite
- Strong ecosystem (alembic, SQLModel, etc.)

**Negative**:
- ORM overhead vs. raw SQL (minimal for our use case)
- Learning curve for developers unfamiliar with ORMs
- Per-database quirks still require knowledge

## Alternatives Considered

1. **Raw SQL**: Write SQL directly
   - Pros: Full control, close to database
   - Cons: No type safety, manual migrations, vendor lock-in

2. **SQLModel**: SQLAlchemy + Pydantic integration
   - Pros: Single model definition for API and database
   - Cons: Newer, less community resources

3. **MongoDB/NoSQL**: Document database
   - Pros: Flexible schema
   - Cons: Harder to model relational data (executions, agents)

## Schema Design

Key tables:
- **PipelineExecution**: Core execution record
- **AgentOutput**: Individual agent results (denormalized for flexibility)
- **QualityMetrics**: Aggregated quality scores

## Future Improvements

- Add database-level audit triggers
- Implement row-level security for multi-tenant deployments
- Add analytics views for reporting
