"""FastAPI application for the autonomous ETL/ELT agent system."""

import asyncio
import logging
from typing import Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field
import uvicorn

from src.config import get_settings

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

# Store pipeline execution results
pipeline_results: dict = {}


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
    story: UserStoryInput, background_tasks: BackgroundTasks
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

    Returns:
        PipelineResponse with execution status and quality metrics.

    Raises:
        HTTPException: If pipeline creation fails.
    """
    import uuid

    execution_id = str(uuid.uuid4())
    logger.info(f"Creating pipeline {execution_id} for: {story.title}")

    try:
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

        # Run orchestration in background
        final_state = await orchestrator.execute(user_story_data)

        # Store results
        pipeline_results[execution_id] = final_state

        # Get summary
        summary = orchestrator.get_summary(final_state)

        # Log execution
        logger.info(
            f"Pipeline {execution_id} completed with status: {final_state['status']}"
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
        raise HTTPException(status_code=500, detail=str(e))


@app.get(
    "/pipelines/{execution_id}",
    response_model=PipelineDetailsResponse,
    tags=["Pipelines"],
    summary="Get pipeline execution details",
)
async def get_pipeline(execution_id: str) -> PipelineDetailsResponse:
    """Get detailed results from a pipeline execution.

    Args:
        execution_id: The UUID of the pipeline execution.

    Returns:
        PipelineDetailsResponse with all generated artifacts.

    Raises:
        HTTPException: If execution_id not found.
    """
    if execution_id not in pipeline_results:
        raise HTTPException(status_code=404, detail="Pipeline execution not found")

    final_state = pipeline_results[execution_id]
    orchestrator = get_orchestrator()
    summary = orchestrator.get_summary(final_state)

    return PipelineDetailsResponse(
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
        parsed_requirements=final_state.get("parsed_requirements"),
        generated_code=final_state.get("generated_code"),
        generated_tests=final_state.get("generated_tests"),
        pull_request=final_state.get("pull_request"),
    )


@app.get("/pipelines", tags=["Pipelines"], summary="List all pipeline executions")
async def list_pipelines():
    """Get list of all pipeline executions.

    Returns:
        List of execution summaries.
    """
    orchestrator = get_orchestrator()
    summaries = []
    for execution_id, state in pipeline_results.items():
        summary = orchestrator.get_summary(state)
        summaries.append(
            {
                "execution_id": execution_id,
                "status": state["status"],
                "story_title": state.get("user_story", {}).get("title", "Unknown"),
                "overall_quality": summary["overall_score"],
            }
        )
    return {"total": len(summaries), "pipelines": summaries}


if __name__ == "__main__":
    settings = get_settings()
    uvicorn.run(
        "src.api:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
