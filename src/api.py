"""FastAPI application for the autonomous ETL/ELT agent system."""

import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import uvicorn
import time

from src.config import get_settings
from src.database import init_db, get_db, PipelineExecution
from src.database.repository import PipelineExecutionRepository

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(
    title="Autonomous ETL/ELT Agent",
    description="Multi-agent system for generating production-ready ETL pipelines",
    version="1.0.0",
)

# Global orchestrator instance (lazy-loaded)
_orchestrator = None

def get_orchestrator():
    """Get or create the orchestrator instance."""
    global _orchestrator
    if _orchestrator is None:
        from src.orchestration import AgentOrchestrator
        _orchestrator = AgentOrchestrator()
    return _orchestrator

# Initialize database on startup
@app.on_event("startup")
async def startup_event():
    """Initialize database on application startup."""
    logger.info("Starting up application...")
    init_db()
    logger.info("Database initialized")


class UserStoryInput(BaseModel):
    """Input model for creating an ETL pipeline."""

    title: str = Field(..., description="User story title or feature name")
    description: str = Field(
        ..., description="Detailed description of the ETL requirements"
    )
    source_system: Optional[str] = Field(
        None, description="Source system or data location"
    )
    target_system: Optional[str] = Field(
        None, description="Target system or destination"
    )
    data_quality_rules: Optional[list] = Field(
        None, description="List of data quality validation rules"
    )
    performance_requirements: Optional[dict] = Field(
        None, description="Performance and SLA requirements"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "title": "Transform Customer Orders to Analytics",
                "description": "Load customer orders from Salesforce, join with product data, "
                "and create summary analytics table in Snowflake",
                "source_system": "Salesforce CRM",
                "target_system": "Snowflake Data Warehouse",
                "data_quality_rules": [
                    "Order ID must be unique",
                    "Order date must be valid",
                    "Customer ID must exist in customer table",
                ],
                "performance_requirements": {
                    "max_execution_time_minutes": 30,
                    "expected_row_count": 1000000,
                },
            }
        }


class PipelineResponse(BaseModel):
    """Response model for pipeline creation."""

    execution_id: str
    status: str
    message: str
    task_confidence: float
    code_quality: float
    test_quality: float
    pr_quality: float
    overall_quality: float
    execution_log: list
    error: Optional[str] = None


class PipelineDetailsResponse(PipelineResponse):
    """Detailed pipeline response with generated artifacts."""

    parsed_requirements: Optional[dict] = None
    generated_code: Optional[dict] = None
    generated_tests: Optional[dict] = None
    pull_request: Optional[dict] = None


@app.get("/", tags=["Health"])
async def root():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "Autonomous ETL/ELT Agent",
        "version": "1.0.0",
    }


@app.post(
    "/pipelines/create",
    response_model=PipelineResponse,
    tags=["Pipelines"],
    summary="Create an ETL pipeline from user story",
)
async def create_pipeline(
    story: UserStoryInput, 
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
) -> PipelineResponse:
    """Create a production-ready ETL pipeline from a user story.

    This endpoint orchestrates all agents:
    1. Task Agent parses requirements
    2. Coding Agent generates PySpark code
    3. Test Agent creates pytest suites
    4. PR Agent prepares a Pull Request

    Args:
        story: User story input with ETL requirements.
        background_tasks: FastAPI background task handler.
        db: Database session dependency.

    Returns:
        PipelineResponse with execution status and quality metrics.

    Raises:
        HTTPException: If pipeline creation fails.
    """
    import uuid

    execution_id = str(uuid.uuid4())
    logger.info(f"Creating pipeline {execution_id} for: {story.title}")
    
    start_time = time.time()

    try:
        # Create database record for this execution
        PipelineExecutionRepository.create(
            db=db,
            execution_id=execution_id,
            user_story_title=story.title,
            user_story_description=story.description,
            user_story_json={
                "title": story.title,
                "description": story.description,
                "source_system": story.source_system,
                "target_system": story.target_system,
            }
        )

        # Prepare input for orchestrator
        user_story_data = {
            "title": story.title,
            "description": story.description,
            "source_system": story.source_system,
            "target_system": story.target_system,
            "data_quality_rules": story.data_quality_rules or [],
            "performance_requirements": story.performance_requirements or {},
        }

        # Get orchestrator instance
        orchestrator = get_orchestrator()

        # Run orchestration
        final_state = await orchestrator.execute(user_story_data)

        # Calculate duration
        duration_seconds = time.time() - start_time

        # Get summary
        summary = orchestrator.get_summary(final_state)

        # Update database record with results
        PipelineExecutionRepository.update(
            db=db,
            execution_id=execution_id,
            status=final_state["status"],
            task_confidence=summary["task_confidence"],
            code_quality=summary["code_quality"],
            test_quality=summary["test_quality"],
            pr_quality=summary["pr_quality"],
            overall_quality=summary["overall_score"],
            execution_log=summary["execution_log"],
            error_message=summary.get("error"),
            parsed_requirements=final_state.get("parsed_requirements"),
            generated_code=final_state.get("generated_code"),
            generated_tests=final_state.get("generated_tests"),
            pull_request=final_state.get("pull_request"),
            duration_seconds=duration_seconds,
        )

        # Log execution
        logger.info(
            f"Pipeline {execution_id} completed with status: {final_state['status']} in {duration_seconds:.2f}s"
        )

        return PipelineResponse(
            execution_id=execution_id,
            status=final_state["status"],
            message=f"Pipeline creation {'completed successfully' if final_state['status'] == 'success' else 'failed'}",
            task_confidence=summary["task_confidence"],
            code_quality=summary["code_quality"],
            test_quality=summary["test_quality"],
            pr_quality=summary["pr_quality"],
            overall_quality=summary["overall_score"],
            execution_log=summary["execution_log"],
            error=summary.get("error"),
        )

    except Exception as e:
        logger.error(f"Pipeline creation failed: {str(e)}", exc_info=True)
        # Update database record with error
        duration_seconds = time.time() - start_time
        try:
            PipelineExecutionRepository.update(
                db=db,
                execution_id=execution_id,
                status="failed",
                error_message=str(e),
                duration_seconds=duration_seconds,
            )
        except Exception as db_error:
            logger.error(f"Failed to update execution record: {str(db_error)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/pipelines/{execution_id}",
    response_model=PipelineDetailsResponse,
    tags=["Pipelines"],
    summary="Get pipeline execution details",
)
async def get_pipeline(
    execution_id: str,
    db: Session = Depends(get_db)
) -> PipelineDetailsResponse:
    """Get detailed results from a pipeline execution.

    Args:
        execution_id: The UUID of the pipeline execution.
        db: Database session dependency.

    Returns:
        PipelineDetailsResponse with all generated artifacts.

    Raises:
        HTTPException: If execution_id not found.
    """
    execution = PipelineExecutionRepository.get_by_id(db, execution_id)
    
    if not execution:
        raise HTTPException(status_code=404, detail="Pipeline execution not found")

    return PipelineDetailsResponse(
        execution_id=execution.execution_id,
        status=execution.status,
        message=f"Pipeline creation {'completed successfully' if execution.status == 'success' else 'failed'}",
        task_confidence=execution.task_confidence,
        code_quality=execution.code_quality,
        test_quality=execution.test_quality,
        pr_quality=execution.pr_quality,
        overall_quality=execution.overall_quality,
        execution_log=execution.execution_log or [],
        error=execution.error_message,
        parsed_requirements=execution.parsed_requirements,
        generated_code=execution.generated_code,
        generated_tests=execution.generated_tests,
        pull_request=execution.pull_request,
    )


@app.get("/pipelines", tags=["Pipelines"], summary="List all pipeline executions")
async def list_pipelines(
    limit: int = 50,
    offset: int = 0,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get list of all pipeline executions with pagination and filtering.

    Args:
        limit: Maximum number of results to return.
        offset: Number of results to skip.
        status: Filter by status (success/failed/initialized).
        db: Database session dependency.

    Returns:
        List of execution summaries.
    """
    executions = PipelineExecutionRepository.list_all(
        db=db,
        limit=limit,
        offset=offset,
        status=status
    )
    
    summaries = [
        {
            "execution_id": e.execution_id,
            "created_at": e.created_at.isoformat() if e.created_at else None,
            "status": e.status,
            "user_story_title": e.user_story_title,
            "overall_quality": e.overall_quality,
            "duration_seconds": e.duration_seconds,
        }
        for e in executions
    ]
    
    return {
        "total": len(summaries),
        "limit": limit,
        "offset": offset,
        "pipelines": summaries
    }


class ExecutionAnalytics(BaseModel):
    """Model for execution analytics."""
    
    total_executions: int
    successful: int
    failed: int
    success_rate: float
    average_quality: float
    average_task_confidence: float
    average_code_quality: float
    average_test_quality: float
    average_pr_quality: float


@app.get(
    "/pipelines/analytics/summary",
    response_model=ExecutionAnalytics,
    tags=["Analytics"],
    summary="Get execution analytics"
)
async def get_analytics(db: Session = Depends(get_db)):
    """Get aggregated analytics about all pipeline executions.

    Returns:
        ExecutionAnalytics with summary metrics.
    """
    analytics = PipelineExecutionRepository.get_analytics(db)
    return ExecutionAnalytics(**analytics)


@app.get(
    "/pipelines/analytics/by-status",
    tags=["Analytics"],
    summary="Get execution counts by status"
)
async def get_stats_by_status(db: Session = Depends(get_db)):
    """Get execution count breakdown by status.

    Returns:
        Dictionary with status counts.
    """
    stats = PipelineExecutionRepository.get_stats_by_status(db)
    return {"status_counts": stats}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
