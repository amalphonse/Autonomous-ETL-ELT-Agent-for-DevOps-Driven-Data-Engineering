"""Schema definitions for Orchestration Agent."""

from typing import List, Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field


class ScheduleConfig(BaseModel):
    """Configuration for DAG scheduling."""

    schedule_interval: str = Field(
        default="@daily",
        description="Airflow schedule interval (cron or preset like @daily, @hourly)",
    )
    start_date: str = Field(
        default="2024-01-01",
        description="DAG start date in YYYY-MM-DD format",
    )
    catchup: bool = Field(
        default=False,
        description="Whether to catch up on missed runs",
    )
    max_active_runs: int = Field(
        default=1,
        description="Maximum number of active DAG runs",
    )
    retries: int = Field(
        default=3,
        description="Number of retries for failed tasks",
    )
    retry_delay_minutes: int = Field(
        default=5,
        description="Delay between retries in minutes",
    )


class TaskDependency(BaseModel):
    """Represents a dependency between tasks."""

    task_id: str = Field(..., description="ID of the dependent task")
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of task IDs this task depends on",
    )


class DAGTask(BaseModel):
    """Represents a task in the Airflow DAG."""

    task_id: str = Field(..., description="Unique task identifier")
    task_type: str = Field(
        ...,
        description="Type of task (spark_submit, python, bash, sensor, etc.)",
    )
    description: str = Field(..., description="Task description")
    operator: str = Field(
        ...,
        description="Airflow operator class (e.g., SparkSubmitOperator, PythonOperator)",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Task-specific parameters",
    )
    depends_on: List[str] = Field(
        default_factory=list,
        description="List of task IDs this task depends on",
    )
    retries: Optional[int] = Field(
        default=None,
        description="Task-specific retry count (overrides DAG default)",
    )
    pool: Optional[str] = Field(
        default=None,
        description="Airflow pool for resource management",
    )


class AirflowDAG(BaseModel):
    """Represents an Airflow DAG structure."""

    dag_id: str = Field(..., description="Unique DAG identifier")
    description: str = Field(..., description="DAG description")
    schedule_config: ScheduleConfig = Field(
        default_factory=ScheduleConfig,
        description="Scheduling configuration",
    )
    tasks: List[DAGTask] = Field(
        default_factory=list,
        description="List of tasks in the DAG",
    )
    default_args: Dict[str, Any] = Field(
        default_factory=dict,
        description="Default arguments for all tasks",
    )
    tags: List[str] = Field(
        default_factory=list,
        description="DAG tags for organization",
    )
    connections: List[str] = Field(
        default_factory=list,
        description="Required Airflow connections",
    )
    variables: List[str] = Field(
        default_factory=list,
        description="Required Airflow variables",
    )


class GeneratedOrchestration(BaseModel):
    """Container for generated orchestration code."""

    airflow_dag: AirflowDAG = Field(..., description="Airflow DAG structure")
    dag_file_name: str = Field(..., description="DAG file name (e.g., customer_pipeline_dag.py)")
    dag_file_path: str = Field(..., description="Relative path for DAG file")
    dag_code: str = Field(..., description="Complete Airflow DAG Python code")
    config_files: Dict[str, str] = Field(
        default_factory=dict,
        description="Additional config files (key=filename, value=content)",
    )
    deployment_notes: str = Field(
        default="",
        description="Notes on deploying this DAG to Airflow",
    )
    dependencies: List[str] = Field(
        default_factory=list,
        description="Python dependencies required for the DAG",
    )


class OrchestrationAgentInput(BaseModel):
    """Input schema for Orchestration Agent."""

    story_title: str = Field(..., description="User story title")
    story_description: str = Field(..., description="User story description")
    parsed_requirements: Dict[str, Any] = Field(
        ...,
        description="Parsed requirements from Task Agent",
    )
    generated_code: Dict[str, Any] = Field(
        ...,
        description="Generated code from Coding Agent",
    )
    schedule_requirements: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Scheduling requirements from user story",
    )
    execution_environment: str = Field(
        default="dataproc",
        description="Execution environment (dataproc, databricks, emr, synapse)",
    )


class OrchestrationAgentOutput(BaseModel):
    """Output schema for Orchestration Agent."""

    generated_orchestration: GeneratedOrchestration = Field(
        ...,
        description="Generated orchestration artifacts",
    )
    quality_score: float = Field(
        default=0.0,
        description="Quality score of generated orchestration (0-1)",
        ge=0.0,
        le=1.0,
    )
    validation_results: Dict[str, Any] = Field(
        default_factory=dict,
        description="Validation results for the generated DAG",
    )
    recommendations: List[str] = Field(
        default_factory=list,
        description="Recommendations for improving the orchestration",
    )
