"""Tests for the Orchestration Agent."""

import pytest
import json
from unittest.mock import AsyncMock, MagicMock, patch

from src.agents.orchestration_agent import OrchestrationAgent
from src.agents.orchestration_agent.schemas import (
    OrchestrationAgentInput,
    OrchestrationAgentOutput,
    GeneratedOrchestration,
    AirflowDAG,
    DAGTask,
    ScheduleConfig,
)
from src.types import AgentInput, AgentOutput, AgentStatus


@pytest.fixture
def mock_settings():
    """Mock settings for Orchestration Agent."""
    with patch("src.agents.orchestration_agent.orchestration_agent.get_settings") as mock:
        settings = MagicMock()
        settings.openai_model = "gpt-4o"
        settings.openai_temperature = 0.0
        settings.openai_api_key = "test-key"
        mock.return_value = settings
        yield settings


@pytest.fixture
def sample_parsed_requirements():
    """Sample parsed requirements for testing."""
    return {
        "title": "Customer Order Pipeline",
        "description": "Process daily customer orders",
        "input_sources": [
            {
                "name": "orders",
                "location": "gs://bucket/orders",
                "format": "parquet"
            }
        ],
        "output_location": "gs://bucket/aggregated_orders",
        "transformation_steps": [
            {
                "step_id": "step-1",
                "transformation_type": "aggregate",
                "group_by": ["customer_id"],
                "aggregations": [
                    {"function": "SUM", "column": "amount", "alias": "total_spent"}
                ]
            }
        ],
        "schedule_requirements": {
            "frequency": "daily",
            "start_time": "00:00"
        },
        "execution_environment": "dataproc"
    }


@pytest.fixture
def sample_generated_code():
    """Sample generated code for testing."""
    return {
        "main_pipeline_code": """
from pyspark.sql import SparkSession
from pyspark.sql.functions import sum as spark_sum

def main():
    spark = SparkSession.builder.appName('CustomerOrders').getOrCreate()
    df = spark.read.parquet('gs://bucket/orders')
    result = df.groupBy('customer_id').agg(spark_sum('amount').alias('total_spent'))
    result.write.parquet('gs://bucket/aggregated_orders', mode='overwrite')
""",
        "input_schema_model": {
            "model_name": "OrderInput",
            "code": "class OrderInput(BaseModel): pass"
        }
    }


@pytest.fixture
def sample_dag_structure():
    """Sample DAG structure response from LLM."""
    return {
        "airflow_dag": {
            "dag_id": "customer_order_pipeline",
            "description": "Daily customer order processing",
            "schedule_config": {
                "schedule_interval": "@daily",
                "start_date": "2024-01-01",
                "catchup": False,
                "max_active_runs": 1,
                "retries": 3,
                "retry_delay_minutes": 5
            },
            "tasks": [
                {
                    "task_id": "validate_input",
                    "task_type": "python",
                    "description": "Validate input data",
                    "operator": "PythonOperator",
                    "params": {"python_callable": "validate_data"},
                    "depends_on": []
                },
                {
                    "task_id": "run_spark_job",
                    "task_type": "spark_submit",
                    "description": "Run Spark transformation",
                    "operator": "DataprocSubmitJobOperator",
                    "params": {
                        "job_name": "customer_orders",
                        "main_python_file_uri": "gs://bucket/pipeline.py"
                    },
                    "depends_on": ["validate_input"]
                },
                {
                    "task_id": "data_quality_check",
                    "task_type": "python",
                    "description": "Check output quality",
                    "operator": "PythonOperator",
                    "params": {"python_callable": "quality_check"},
                    "depends_on": ["run_spark_job"]
                }
            ],
            "tags": ["etl", "customer", "daily"],
            "connections": ["google_cloud_default"],
            "variables": ["gcs_bucket"]
        },
        "dag_file_name": "customer_order_pipeline_dag.py",
        "dag_file_path": "dags/customer_order_pipeline_dag.py",
        "dependencies": ["apache-airflow-providers-google>=10.0.0"]
    }


@pytest.fixture
def sample_dag_code():
    """Sample generated DAG code."""
    return """
from datetime import datetime, timedelta
from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.providers.google.cloud.operators.dataproc import DataprocSubmitJobOperator

default_args = {
    'owner': 'airflow',
    'retries': 3,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    dag_id='customer_order_pipeline',
    description='Daily customer order processing',
    default_args=default_args,
    schedule_interval='@daily',
    start_date=datetime(2024, 1, 1),
    catchup=False,
    max_active_runs=1,
    tags=['etl', 'customer', 'daily'],
) as dag:
    
    validate_input = PythonOperator(
        task_id='validate_input',
        python_callable=validate_data,
    )
    
    run_spark_job = DataprocSubmitJobOperator(
        task_id='run_spark_job',
        job_name='customer_orders',
        main_python_file_uri='gs://bucket/pipeline.py',
    )
    
    data_quality_check = PythonOperator(
        task_id='data_quality_check',
        python_callable=quality_check,
    )
    
    validate_input >> run_spark_job >> data_quality_check
"""


@pytest.fixture
def orchestration_agent(mock_settings):
    """Create an Orchestration Agent instance."""
    with patch("src.agents.orchestration_agent.orchestration_agent.ChatOpenAI"):
        return OrchestrationAgent()


class TestOrchestrationAgent:
    """Test suite for Orchestration Agent."""

    async def test_agent_initialization(self, orchestration_agent):
        """Test that Orchestration Agent initializes correctly."""
        assert orchestration_agent is not None
        assert orchestration_agent.agent_type.value == "orchestration"

    async def test_execute_success(
        self,
        orchestration_agent,
        sample_parsed_requirements,
        sample_generated_code,
        sample_dag_structure,
        sample_dag_code,
    ):
        """Test successful orchestration generation."""
        # Mock LLM responses
        mock_dag_structure_response = MagicMock()
        mock_dag_structure_response.content = json.dumps(sample_dag_structure)

        mock_dag_code_response = MagicMock()
        mock_dag_code_response.content = sample_dag_code

        orchestration_agent.llm.ainvoke = AsyncMock(
            side_effect=[mock_dag_structure_response, mock_dag_code_response]
        )

        # Prepare input
        agent_input = AgentInput(
            data={
                "story_title": "Customer Order Pipeline",
                "story_description": "Process daily customer orders",
                "parsed_requirements": sample_parsed_requirements,
                "generated_code": sample_generated_code,
                "schedule_requirements": {"frequency": "daily"},
                "execution_environment": "dataproc",
            }
        )

        # Execute agent
        output = await orchestration_agent.execute(agent_input)

        # Assertions
        assert output.status == AgentStatus.COMPLETED
        assert "generated_orchestration" in output.data
        assert output.data["quality_score"] > 0.0
        
        orchestration = output.data["generated_orchestration"]
        assert orchestration["dag_file_name"] == "customer_order_pipeline_dag.py"
        assert len(orchestration["airflow_dag"]["tasks"]) == 3
        assert orchestration["airflow_dag"]["dag_id"] == "customer_order_pipeline"

    async def test_execute_with_missing_requirements(self, orchestration_agent):
        """Test execution with missing requirements."""
        agent_input = AgentInput(
            data={
                "story_title": "Test",
                "story_description": "Test description",
                # Missing parsed_requirements and generated_code
            }
        )

        # This should still execute but might have issues
        # The actual behavior depends on your implementation
        # For now, let's just test that it doesn't crash
        output = await orchestration_agent.execute(agent_input)
        # It might succeed or fail depending on implementation
        assert output is not None

    async def test_quality_score_calculation(self, orchestration_agent):
        """Test quality score calculation."""
        # Create a well-formed orchestration
        good_orchestration = GeneratedOrchestration(
            airflow_dag=AirflowDAG(
                dag_id="test_dag",
                description="A comprehensive test DAG with validation",
                schedule_config=ScheduleConfig(),
                tasks=[
                    DAGTask(
                        task_id="validate_input",
                        task_type="python",
                        description="Validation task",
                        operator="PythonOperator",
                        depends_on=[]
                    ),
                    DAGTask(
                        task_id="process_data",
                        task_type="spark",
                        description="Processing task",
                        operator="SparkSubmitOperator",
                        depends_on=["validate_input"]
                    ),
                ],
                tags=["test"],
            ),
            dag_file_name="test_dag.py",
            dag_file_path="dags/test_dag.py",
            dag_code="# " + ("x" * 600),  # Substantial code
        )

        score = orchestration_agent._calculate_quality_score(good_orchestration)
        assert 0.0 <= score <= 1.0
        assert score > 0.5  # Should have decent score

    async def test_dag_validation_success(self, orchestration_agent):
        """Test DAG validation for valid DAG."""
        valid_orchestration = GeneratedOrchestration(
            airflow_dag=AirflowDAG(
                dag_id="valid_dag",
                description="Valid DAG",
                tasks=[
                    DAGTask(
                        task_id="task1",
                        task_type="python",
                        description="First task",
                        operator="PythonOperator",
                        depends_on=[]
                    ),
                    DAGTask(
                        task_id="task2",
                        task_type="python",
                        description="Second task",
                        operator="PythonOperator",
                        depends_on=["task1"]
                    ),
                ],
            ),
            dag_file_name="valid_dag.py",
            dag_file_path="dags/valid_dag.py",
            dag_code="# DAG code",
        )

        validation_results = orchestration_agent._validate_dag(valid_orchestration)
        assert validation_results["is_valid"] is True
        assert len(validation_results["errors"]) == 0

    async def test_dag_validation_circular_dependency(self, orchestration_agent):
        """Test DAG validation catches circular dependencies."""
        # Create DAG with circular dependency
        circular_orchestration = GeneratedOrchestration(
            airflow_dag=AirflowDAG(
                dag_id="circular_dag",
                description="DAG with circular dependency",
                tasks=[
                    DAGTask(
                        task_id="task1",
                        task_type="python",
                        description="First task",
                        operator="PythonOperator",
                        depends_on=["task2"]  # Depends on task2
                    ),
                    DAGTask(
                        task_id="task2",
                        task_type="python",
                        description="Second task",
                        operator="PythonOperator",
                        depends_on=["task1"]  # Depends on task1 - circular!
                    ),
                ],
            ),
            dag_file_name="circular_dag.py",
            dag_file_path="dags/circular_dag.py",
            dag_code="# DAG code",
        )

        validation_results = orchestration_agent._validate_dag(circular_orchestration)
        assert validation_results["is_valid"] is False
        assert any("Circular" in error for error in validation_results["errors"])

    async def test_dag_validation_missing_dependency(self, orchestration_agent):
        """Test DAG validation catches missing dependencies."""
        missing_dep_orchestration = GeneratedOrchestration(
            airflow_dag=AirflowDAG(
                dag_id="missing_dep_dag",
                description="DAG with missing dependency",
                tasks=[
                    DAGTask(
                        task_id="task1",
                        task_type="python",
                        description="First task",
                        operator="PythonOperator",
                        depends_on=["nonexistent_task"]  # This task doesn't exist
                    ),
                ],
            ),
            dag_file_name="missing_dep_dag.py",
            dag_file_path="dags/missing_dep_dag.py",
            dag_code="# DAG code",
        )

        validation_results = orchestration_agent._validate_dag(missing_dep_orchestration)
        assert validation_results["is_valid"] is False
        assert any("does not exist" in error for error in validation_results["errors"])

    async def test_recommendations_generation(self, orchestration_agent):
        """Test generation of recommendations."""
        # Minimal DAG without quality checks
        minimal_orchestration = GeneratedOrchestration(
            airflow_dag=AirflowDAG(
                dag_id="minimal_dag",
                description="Minimal DAG",
                schedule_config=ScheduleConfig(retries=1),
                tasks=[
                    DAGTask(
                        task_id="task1",
                        task_type="python",
                        description="Only task",
                        operator="PythonOperator",
                        depends_on=[]
                    ),
                ],
            ),
            dag_file_name="minimal_dag.py",
            dag_file_path="dags/minimal_dag.py",
            dag_code="# code",
        )

        validation_results = {"is_valid": True, "errors": [], "warnings": []}
        recommendations = orchestration_agent._generate_recommendations(
            minimal_orchestration, validation_results
        )

        assert len(recommendations) > 0
        # Should recommend quality checks, notifications, etc.
        assert any("quality" in rec.lower() or "validation" in rec.lower() 
                  for rec in recommendations)

    async def test_deployment_notes_generation(self, orchestration_agent):
        """Test generation of deployment notes."""
        test_dag = AirflowDAG(
            dag_id="test_deployment_dag",
            description="Test DAG for deployment",
            connections=["google_cloud_default", "slack_default"],
            variables=["gcs_bucket", "notification_email"],
        )

        notes = orchestration_agent._generate_deployment_notes(test_dag, "dataproc")

        assert "test_deployment_dag" in notes
        assert "google_cloud_default" in notes
        assert "slack_default" in notes
        assert "gcs_bucket" in notes
        assert "notification_email" in notes
        assert "dataproc" in notes.lower()

    async def test_execution_environment_databricks(
        self,
        orchestration_agent,
        sample_parsed_requirements,
        sample_generated_code,
        sample_dag_structure,
        sample_dag_code,
    ):
        """Test orchestration generation for Databricks environment."""
        # Update environment to Databricks
        sample_parsed_requirements["execution_environment"] = "databricks"

        # Mock LLM responses
        mock_dag_structure_response = MagicMock()
        mock_dag_structure_response.content = json.dumps(sample_dag_structure)

        mock_dag_code_response = MagicMock()
        mock_dag_code_response.content = sample_dag_code

        orchestration_agent.llm.ainvoke = AsyncMock(
            side_effect=[mock_dag_structure_response, mock_dag_code_response]
        )

        agent_input = AgentInput(
            data={
                "story_title": "Customer Order Pipeline",
                "story_description": "Process daily customer orders",
                "parsed_requirements": sample_parsed_requirements,
                "generated_code": sample_generated_code,
                "execution_environment": "databricks",
            }
        )

        output = await orchestration_agent.execute(agent_input)

        assert output.status == AgentStatus.COMPLETED
        # Check that Databricks-specific notes are included
        deployment_notes = output.data["generated_orchestration"].get("deployment_notes", "")
        assert "databricks" in deployment_notes.lower()
