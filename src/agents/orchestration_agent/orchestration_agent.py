"""Orchestration Agent implementation for generating Airflow DAGs and workflow code."""

import json
import logging
import re
from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.config import get_settings
from src.types import Agent, AgentType, AgentStatus, AgentInput, AgentOutput
from src.agents.orchestration_agent.schemas import (
    OrchestrationAgentInput,
    OrchestrationAgentOutput,
    GeneratedOrchestration,
    AirflowDAG,
    DAGTask,
    ScheduleConfig,
)

logger = logging.getLogger(__name__)


class OrchestrationAgent(Agent):
    """Orchestration Agent: Generates Airflow DAGs and workflow orchestration code.

    This agent takes generated code from the Coding Agent and creates:
    - Production-ready Airflow DAG files
    - Task dependencies and scheduling logic
    - Configuration for different execution environments (Dataproc, Databricks, EMR)
    - Deployment documentation
    """

    def __init__(self):
        """Initialize the Orchestration Agent with LangChain components."""
        super().__init__(AgentType.ORCHESTRATION)
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """Set up LangChain prompts for DAG generation."""
        self.dag_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert Apache Airflow developer. Your task is to generate production-ready
Airflow DAG code for orchestrating PySpark ETL/ELT pipelines.

## EXAMPLE OUTPUT:

For a pipeline that processes customer orders daily:

{{
  "airflow_dag": {{
    "dag_id": "customer_order_pipeline",
    "description": "Daily customer order processing and aggregation",
    "schedule_config": {{
      "schedule_interval": "@daily",
      "start_date": "2024-01-01",
      "catchup": false,
      "max_active_runs": 1,
      "retries": 3,
      "retry_delay_minutes": 5
    }},
    "tasks": [
      {{
        "task_id": "validate_input_data",
        "task_type": "python",
        "description": "Validate input data availability and schema",
        "operator": "PythonOperator",
        "params": {{
          "python_callable": "validate_data_sources"
        }},
        "depends_on": []
      }},
      {{
        "task_id": "run_spark_pipeline",
        "task_type": "spark_submit",
        "description": "Execute PySpark transformation pipeline",
        "operator": "DataprocSubmitJobOperator",
        "params": {{
          "job_name": "customer_order_etl",
          "main_python_file_uri": "gs://bucket/pipelines/customer_order_pipeline.py",
          "cluster_name": "etl-cluster"
        }},
        "depends_on": ["validate_input_data"]
      }},
      {{
        "task_id": "data_quality_check",
        "task_type": "python",
        "description": "Run data quality validations on output",
        "operator": "PythonOperator",
        "params": {{
          "python_callable": "run_quality_checks"
        }},
        "depends_on": ["run_spark_pipeline"]
      }},
      {{
        "task_id": "send_completion_notification",
        "task_type": "python",
        "description": "Send success notification",
        "operator": "PythonOperator",
        "params": {{
          "python_callable": "send_notification"
        }},
        "depends_on": ["data_quality_check"]
      }}
    ],
    "tags": ["etl", "customer", "daily"],
    "connections": ["google_cloud_default", "bigquery_default"],
    "variables": ["gcs_bucket", "bq_dataset"]
  }},
  "dag_file_name": "customer_order_pipeline_dag.py",
  "dag_file_path": "dags/customer_order_pipeline_dag.py",
  "dependencies": ["apache-airflow-providers-google>=10.0.0", "pyspark>=3.4.0"]
}}

---

## ACTUAL REQUIREMENTS TO IMPLEMENT:

**Story Title:** {story_title}

**Story Description:** {story_description}

**Parsed Requirements:**
{requirements_json}

**Generated Code Files:**
{code_files}

**Execution Environment:** {execution_environment}

**Schedule Requirements:** {schedule_requirements}

---

## GENERATION INSTRUCTIONS:

1. **DAG Structure:**
   - Create a meaningful dag_id based on the story (lowercase, underscores)
   - Include comprehensive description
   - Set appropriate schedule_interval based on requirements
   - Configure retries and error handling

2. **Task Breakdown:**
   - Create validation tasks for data sources
   - Main Spark job submission task
   - Data quality validation tasks
   - Notification/alerting tasks
   - Proper task dependencies using depends_on

3. **Execution Environment Mapping:**
   - **dataproc**: Use DataprocSubmitJobOperator
   - **databricks**: Use DatabricksSubmitRunOperator
   - **emr**: Use EmrAddStepsOperator
   - **synapse**: Use AzureSynapseRunSparkBatchOperator

4. **Best Practices:**
   - Use sensors for data availability checks
   - Include data quality validation tasks
   - Add proper error handling and alerting
   - Set resource pools for heavy tasks
   - Use Airflow Variables for configuration
   - Include meaningful task descriptions

5. **Output Requirements:**
   - Return valid JSON matching the schema
   - Include complete task dependency chain
   - List all required Airflow connections and variables
   - Specify Python dependencies

Generate the complete Airflow DAG structure as valid JSON:
"""
        )

        self.dag_code_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert Apache Airflow developer. Generate complete, production-ready
Airflow DAG Python code based on the DAG structure.

DAG Structure:
{dag_structure}

Story Title: {story_title}
Generated Pipeline Code: {pipeline_code}

Generate complete Airflow DAG code that:
1. Imports all necessary operators and modules
2. Defines helper functions (validators, notifiers, etc.)
3. Creates the DAG with proper configuration
4. Defines all tasks with correct operators
5. Sets up task dependencies
6. Includes comprehensive docstrings and comments
7. Follows Airflow 2.x best practices

Return ONLY the Python code, no markdown formatting or explanation.
"""
        )

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate the input for orchestration agent.

        Args:
            agent_input: Input data to validate.

        Returns:
            True if input is valid, False otherwise.
        """
        data = agent_input.data
        
        # Check required fields
        if not data.get("story_title") or not data.get("parsed_requirements"):
            logger.warning("Missing required fields for orchestration")
            return False
        
        if not data.get("generated_code"):
            logger.warning("Missing generated code for orchestration")
            return False
        
        return True

    async def execute(self, agent_input: AgentInput | dict) -> AgentOutput:
        """Execute the Orchestration Agent.

        Args:
            agent_input: Input containing parsed requirements and generated code.
                        Can be either AgentInput object or dict.

        Returns:
            AgentOutput with generated orchestration code and metadata.
        """
        try:
            logger.info("Starting Orchestration Agent execution")
            self.set_status(AgentStatus.RUNNING)

            # Extract input data - handle both dict and AgentInput
            if isinstance(agent_input, dict):
                input_data = agent_input
            else:
                # If it's an AgentInput object, try to get data or convert to dict
                input_data = getattr(agent_input, 'data', agent_input.model_dump())
            story_title = input_data.get("story_title", "Untitled Pipeline")
            story_description = input_data.get("story_description", "")
            parsed_requirements = input_data.get("parsed_requirements", {})
            generated_code = input_data.get("generated_code", {})
            schedule_requirements = input_data.get("schedule_requirements")
            execution_environment = input_data.get("execution_environment", "dataproc")

            # Generate DAG structure
            dag_structure = await self._generate_dag_structure(
                story_title=story_title,
                story_description=story_description,
                parsed_requirements=parsed_requirements,
                generated_code=generated_code,
                schedule_requirements=schedule_requirements,
                execution_environment=execution_environment,
            )

            # Generate DAG code
            dag_code = await self._generate_dag_code(
                dag_structure=dag_structure,
                story_title=story_title,
                pipeline_code=generated_code.get("main_pipeline_code", ""),
            )

            # Create orchestration output
            generated_orchestration = GeneratedOrchestration(
                airflow_dag=dag_structure["airflow_dag"],
                dag_file_name=dag_structure["dag_file_name"],
                dag_file_path=dag_structure["dag_file_path"],
                dag_code=dag_code,
                dependencies=dag_structure.get("dependencies", []),
                deployment_notes=self._generate_deployment_notes(
                    dag_structure["airflow_dag"], execution_environment
                ),
            )

            # Calculate quality score
            quality_score = self._calculate_quality_score(generated_orchestration)

            # Validate DAG
            validation_results = self._validate_dag(generated_orchestration)

            # Generate recommendations
            recommendations = self._generate_recommendations(
                generated_orchestration, validation_results
            )

            output_data = OrchestrationAgentOutput(
                generated_orchestration=generated_orchestration,
                quality_score=quality_score,
                validation_results=validation_results,
                recommendations=recommendations,
            )

            self.set_status(AgentStatus.COMPLETED)
            logger.info(f"Orchestration Agent completed with quality score: {quality_score}")

            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.COMPLETED,
                data=output_data.model_dump(),
                metadata={
                    "dag_id": dag_structure["airflow_dag"].dag_id,
                    "task_count": len(dag_structure["airflow_dag"].tasks),
                    "execution_environment": execution_environment,
                    "quality_score": quality_score,
                },
            )

        except Exception as e:
            logger.error(f"Orchestration Agent failed: {str(e)}", exc_info=True)
            self.set_status(AgentStatus.FAILED)
            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.FAILED,
                data={},
                metadata={"error": str(e)},
            )

    async def _generate_dag_structure(
        self,
        story_title: str,
        story_description: str,
        parsed_requirements: Dict[str, Any],
        generated_code: Dict[str, Any],
        schedule_requirements: Optional[Dict[str, Any]],
        execution_environment: str,
    ) -> Dict[str, Any]:
        """Generate the Airflow DAG structure using LLM."""
        # Prepare code files summary
        code_files = []
        if generated_code.get("main_pipeline_code"):
            code_files.append("main_pipeline.py")
        if generated_code.get("input_schema_model"):
            code_files.append(generated_code["input_schema_model"].get("module_name", "input_schema.py"))
        if generated_code.get("output_schema_model"):
            code_files.append(generated_code["output_schema_model"].get("module_name", "output_schema.py"))

        # Format prompt inputs
        prompt_input = {
            "story_title": story_title,
            "story_description": story_description,
            "requirements_json": json.dumps(parsed_requirements, indent=2),
            "code_files": ", ".join(code_files) if code_files else "No files",
            "execution_environment": execution_environment,
            "schedule_requirements": json.dumps(schedule_requirements, indent=2) if schedule_requirements else "None specified - use @daily default",
        }

        # Generate DAG structure
        formatted_prompt = self.dag_generation_prompt.format(**prompt_input)
        response = await self.llm.ainvoke(formatted_prompt)
        
        # Parse JSON response
        response_text = response.content.strip()
        
        # Extract JSON from markdown code blocks if present
        if "```json" in response_text:
            json_match = re.search(r"```json\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
        elif "```" in response_text:
            json_match = re.search(r"```\s*(.*?)\s*```", response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(1)
        
        dag_structure = json.loads(response_text)
        
        # Validate and convert to Pydantic models
        airflow_dag = AirflowDAG(**dag_structure["airflow_dag"])
        dag_structure["airflow_dag"] = airflow_dag
        
        return dag_structure

    async def _generate_dag_code(
        self,
        dag_structure: Dict[str, Any],
        story_title: str,
        pipeline_code: str,
    ) -> str:
        """Generate the complete Airflow DAG Python code."""
        prompt_input = {
            "dag_structure": json.dumps(dag_structure["airflow_dag"].model_dump() if hasattr(dag_structure["airflow_dag"], "model_dump") else dag_structure["airflow_dag"], indent=2),
            "story_title": story_title,
            "pipeline_code": pipeline_code[:500] + "..." if len(pipeline_code) > 500 else pipeline_code,
        }

        formatted_prompt = self.dag_code_generation_prompt.format(**prompt_input)
        response = await self.llm.ainvoke(formatted_prompt)
        
        dag_code = response.content.strip()
        
        # Remove markdown code blocks if present
        if "```python" in dag_code:
            code_match = re.search(r"```python\s*(.*?)\s*```", dag_code, re.DOTALL)
            if code_match:
                dag_code = code_match.group(1)
        elif "```" in dag_code:
            code_match = re.search(r"```\s*(.*?)\s*```", dag_code, re.DOTALL)
            if code_match:
                dag_code = code_match.group(1)
        
        return dag_code.strip()

    def _calculate_quality_score(self, orchestration: GeneratedOrchestration) -> float:
        """Calculate quality score for generated orchestration."""
        score = 0.0
        total_checks = 0

        # Check 1: DAG has tasks
        total_checks += 1
        if len(orchestration.airflow_dag.tasks) > 0:
            score += 0.2

        # Check 2: Tasks have dependencies
        total_checks += 1
        has_dependencies = any(task.depends_on for task in orchestration.airflow_dag.tasks)
        if has_dependencies:
            score += 0.2

        # Check 3: DAG has schedule configuration
        total_checks += 1
        if orchestration.airflow_dag.schedule_config:
            score += 0.15

        # Check 4: DAG code is substantial
        total_checks += 1
        if len(orchestration.dag_code) > 500:
            score += 0.15

        # Check 5: Has data quality or validation tasks
        total_checks += 1
        has_validation = any(
            "validat" in task.task_id.lower() or "quality" in task.task_id.lower()
            for task in orchestration.airflow_dag.tasks
        )
        if has_validation:
            score += 0.15

        # Check 6: Has proper description
        total_checks += 1
        if orchestration.airflow_dag.description and len(orchestration.airflow_dag.description) > 20:
            score += 0.15

        return min(score, 1.0)

    def _validate_dag(self, orchestration: GeneratedOrchestration) -> Dict[str, Any]:
        """Validate the generated DAG structure."""
        validation_results = {
            "is_valid": True,
            "errors": [],
            "warnings": [],
        }

        # Check for circular dependencies
        task_deps = {
            task.task_id: set(task.depends_on) for task in orchestration.airflow_dag.tasks
        }
        if self._has_circular_dependency(task_deps):
            validation_results["is_valid"] = False
            validation_results["errors"].append("Circular task dependency detected")

        # Check for orphaned tasks (tasks with no upstream or downstream)
        task_ids = {task.task_id for task in orchestration.airflow_dag.tasks}
        all_deps = set()
        for task in orchestration.airflow_dag.tasks:
            all_deps.update(task.depends_on)
        
        # Tasks that no one depends on (potential leaf nodes are OK)
        # Tasks that depend on nothing and no one depends on them are orphaned
        for task in orchestration.airflow_dag.tasks:
            if not task.depends_on and task.task_id not in all_deps and len(orchestration.airflow_dag.tasks) > 1:
                validation_results["warnings"].append(
                    f"Task '{task.task_id}' appears to be orphaned (no dependencies)"
                )

        # Check for missing task dependencies
        for dep in all_deps:
            if dep not in task_ids:
                validation_results["is_valid"] = False
                validation_results["errors"].append(
                    f"Task dependency '{dep}' does not exist in task list"
                )

        return validation_results

    def _has_circular_dependency(self, task_deps: Dict[str, set]) -> bool:
        """Check if task dependencies have circular references."""
        def has_cycle(node: str, visited: set, rec_stack: set) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for neighbor in task_deps.get(node, []):
                if neighbor not in visited:
                    if has_cycle(neighbor, visited, rec_stack):
                        return True
                elif neighbor in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited = set()
        rec_stack = set()

        for node in task_deps:
            if node not in visited:
                if has_cycle(node, visited, rec_stack):
                    return True

        return False

    def _generate_recommendations(
        self,
        orchestration: GeneratedOrchestration,
        validation_results: Dict[str, Any],
    ) -> List[str]:
        """Generate recommendations for improving the orchestration."""
        recommendations = []

        # Check task count
        if len(orchestration.airflow_dag.tasks) < 3:
            recommendations.append(
                "Consider adding data validation and quality check tasks"
            )

        # Check for monitoring/alerting
        has_notification = any(
            "notif" in task.task_id.lower() or "alert" in task.task_id.lower()
            for task in orchestration.airflow_dag.tasks
        )
        if not has_notification:
            recommendations.append(
                "Consider adding notification/alerting tasks for pipeline completion"
            )

        # Check for data quality
        has_quality = any(
            "quality" in task.task_id.lower() or "validat" in task.task_id.lower()
            for task in orchestration.airflow_dag.tasks
        )
        if not has_quality:
            recommendations.append(
                "Consider adding data quality validation tasks"
            )

        # Check schedule interval
        if orchestration.airflow_dag.schedule_config.schedule_interval == "None":
            recommendations.append(
                "DAG is set to manual triggering - consider adding a schedule if appropriate"
            )

        # Check retry configuration
        if orchestration.airflow_dag.schedule_config.retries < 2:
            recommendations.append(
                "Consider increasing retry count for better resilience"
            )

        return recommendations

    def _generate_deployment_notes(
        self, dag: AirflowDAG, execution_environment: str
    ) -> str:
        """Generate deployment notes for the DAG."""
        notes = f"""# Deployment Notes for {dag.dag_id}

## Prerequisites

1. **Airflow Setup:**
   - Airflow 2.x installed and running
   - Required providers installed (see dependencies)

2. **Connections Required:**
"""
        for conn in dag.connections:
            notes += f"   - `{conn}`: Configure in Airflow UI\n"

        notes += "\n3. **Variables Required:**\n"
        for var in dag.variables:
            notes += f"   - `{var}`: Set in Airflow UI\n"

        notes += f"""
## Deployment Steps

1. **Copy DAG file:**
   ```bash
   cp {dag.dag_id}_dag.py $AIRFLOW_HOME/dags/
   ```

2. **Install dependencies:**
   ```bash
   pip install apache-airflow-providers-google pyspark
   ```

3. **Upload PySpark code to storage:**
   - For Dataproc: Upload to GCS bucket
   - For Databricks: Upload to DBFS
   - For EMR: Upload to S3 bucket

4. **Configure Airflow connections and variables in UI**

5. **Test the DAG:**
   ```bash
   airflow dags test {dag.dag_id} 2024-01-01
   ```

6. **Enable the DAG:**
   ```bash
   airflow dags unpause {dag.dag_id}
   ```

## Execution Environment: {execution_environment}

"""
        
        if execution_environment == "dataproc":
            notes += """### Dataproc Configuration
- Ensure Dataproc cluster exists or configure auto-create
- Set appropriate machine types and worker counts
- Configure GCS bucket for staging
"""
        elif execution_environment == "databricks":
            notes += """### Databricks Configuration
- Configure Databricks connection with token
- Set cluster configuration or use job clusters
- Upload code to DBFS
"""
        elif execution_environment == "emr":
            notes += """### EMR Configuration
- Configure EMR cluster or use transient clusters
- Set appropriate EC2 instance types
- Configure S3 bucket for logs and staging
"""

        return notes
