"""Orchestration module for multi-agent system.

This module implements the orchestration layer to coordinate
all agents in the autonomous ETL/ELT pipeline.
"""

from typing import TypedDict, Optional, Any
import logging

from src.agents.task_agent import TaskAgent, UserStory, ParsedRequirements
from src.agents.coding_agent import CodingAgent, GeneratedCode
from src.agents.test_agent import TestAgent, GeneratedTests
from src.agents.pr_agent import PRAgent, GeneratedPullRequest
from src.types import AgentStatus

logger = logging.getLogger(__name__)


class OrchestrationState(TypedDict):
    """State object that flows through the agent pipeline."""

    # Input
    user_story: Optional[dict] = None

    # Task Agent output
    parsed_requirements: Optional[dict] = None
    task_confidence: float = 0.0

    # Coding Agent output
    generated_code: Optional[dict] = None
    code_quality_score: float = 0.0

    # Test Agent output
    generated_tests: Optional[dict] = None
    test_quality_score: float = 0.0
    coverage_metrics: Optional[dict] = None

    # PR Agent output
    pull_request: Optional[dict] = None
    pr_quality_score: float = 0.0

    # Metadata
    status: str = "initialized"
    error: Optional[str] = None
    execution_log: list = []


class AgentOrchestrator:
    """Master orchestrator for the multi-agent system.

    Coordinates the execution of all agents in sequence:
    1. Task Agent - Parse requirements
    2. Coding Agent - Generate code
    3. Test Agent - Create tests
    4. PR Agent - Prepare Pull Request
    """

    def __init__(self):
        """Initialize the orchestrator with all agents."""
        self.task_agent = TaskAgent()
        self.coding_agent = CodingAgent()
        self.test_agent = TestAgent()
        self.pr_agent = PRAgent()

    async def execute(self, user_story_data: dict) -> OrchestrationState:
        """Execute the complete orchestration pipeline.

        Args:
            user_story_data: User story input data.

        Returns:
            Final state with all agent outputs.
        """
        initial_state: OrchestrationState = {
            "user_story": user_story_data,
            "status": "started",
            "execution_log": [],
        }

        logger.info("Starting orchestration pipeline")

        try:
            # Execute Task Agent
            initial_state = await self._run_task_agent(initial_state)
            if initial_state.get("error"):
                initial_state["status"] = "failed"
                return initial_state

            # Execute Coding Agent
            initial_state = await self._run_coding_agent(initial_state)
            if initial_state.get("error"):
                initial_state["status"] = "failed"
                return initial_state

            # Execute Test Agent
            initial_state = await self._run_test_agent(initial_state)
            if initial_state.get("error"):
                initial_state["status"] = "failed"
                return initial_state

            # Execute PR Agent
            initial_state = await self._run_pr_agent(initial_state)
            if initial_state.get("error"):
                initial_state["status"] = "failed"
                return initial_state

            # All agents completed successfully
            initial_state["status"] = "success"
            logger.info("Orchestration completed successfully")
            return initial_state

        except Exception as e:
            logger.error(f"Orchestration failed: {str(e)}", exc_info=True)
            initial_state["status"] = "failed"
            initial_state["error"] = str(e)
            return initial_state

    async def _run_task_agent(self, state: OrchestrationState) -> OrchestrationState:
        """Run Task Agent - Parse user story into requirements.

        Args:
            state: Current orchestration state.

        Returns:
            Updated state with Task Agent output.
        """
        logger.info("Executing Task Agent")

        try:
            # Prepare input for Task Agent
            task_input = {"user_story": state["user_story"]}

            # Execute Task Agent
            output = await self.task_agent.execute(task_input)

            if output.status == AgentStatus.SUCCESS:
                state["parsed_requirements"] = output.data.get("requirements")
                state["task_confidence"] = output.data.get("confidence_score", 0.0)
                state["execution_log"].append("✅ Task Agent: Requirements parsed successfully")
                logger.info(f"Task Agent confidence: {state['task_confidence']:.2%}")
            else:
                raise Exception(f"Task Agent failed: {output.error}")

        except Exception as e:
            logger.error(f"Task Agent error: {str(e)}")
            state["error"] = str(e)
            state["status"] = "failed"

        return state

    async def _run_coding_agent(self, state: OrchestrationState) -> OrchestrationState:
        """Run Coding Agent - Generate PySpark code.

        Args:
            state: Current orchestration state.

        Returns:
            Updated state with Coding Agent output.
        """
        logger.info("Executing Coding Agent")

        if not state.get("parsed_requirements"):
            state["error"] = "Task Agent output missing"
            return state

        try:
            # Prepare input for Coding Agent
            coding_input = {"requirements": state["parsed_requirements"]}

            # Execute Coding Agent
            output = await self.coding_agent.execute(coding_input)

            if output.status == AgentStatus.SUCCESS:
                state["generated_code"] = output.data.get("generated_code")
                state["code_quality_score"] = output.data.get(
                    "code_quality_score", 0.0
                )
                state["execution_log"].append(
                    "✅ Coding Agent: PySpark code generated successfully"
                )
                logger.info(f"Coding Agent quality score: {state['code_quality_score']:.2%}")
            else:
                raise Exception(f"Coding Agent failed: {output.error}")

        except Exception as e:
            logger.error(f"Coding Agent error: {str(e)}")
            state["error"] = str(e)
            state["status"] = "failed"

        return state

    async def _run_test_agent(self, state: OrchestrationState) -> OrchestrationState:
        """Run Test Agent - Generate pytest suites.

        Args:
            state: Current orchestration state.

        Returns:
            Updated state with Test Agent output.
        """
        logger.info("Executing Test Agent")

        if not state.get("generated_code") or not state.get("parsed_requirements"):
            state["error"] = "Coding or Task Agent output missing"
            return state

        try:
            # Prepare input for Test Agent
            test_input = {
                "generated_code": state["generated_code"],
                "requirements": state["parsed_requirements"],
            }

            # Execute Test Agent
            output = await self.test_agent.execute(test_input)

            if output.status == AgentStatus.SUCCESS:
                state["generated_tests"] = output.data.get("generated_tests")
                state["test_quality_score"] = output.data.get(
                    "test_quality_score", 0.0
                )
                state["coverage_metrics"] = output.data.get("coverage_metrics")
                state["execution_log"].append(
                    "✅ Test Agent: pytest suites generated successfully"
                )
                logger.info(f"Test Agent quality score: {state['test_quality_score']:.2%}")
            else:
                raise Exception(f"Test Agent failed: {output.error}")

        except Exception as e:
            logger.error(f"Test Agent error: {str(e)}")
            state["error"] = str(e)
            state["status"] = "failed"

        return state

    async def _run_pr_agent(self, state: OrchestrationState) -> OrchestrationState:
        """Run PR Agent - Create Pull Request.

        Args:
            state: Current orchestration state.

        Returns:
            Updated state with PR Agent output.
        """
        logger.info("Executing PR Agent")

        if not state.get("generated_code") or not state.get("generated_tests"):
            state["error"] = "Generated code or tests missing"
            return state

        try:
            # Extract test file dict from generated_tests structure
            test_files = {}
            if state.get("generated_tests"):
                test_data = state["generated_tests"]
                if isinstance(test_data, dict) and "test_code" in test_data:
                    test_files[test_data.get("test_file_path", "tests/test_pipeline.py")] = (
                        test_data["test_code"]
                    )

            # Extract code files from generated_code structure
            code_files = {}
            if state.get("generated_code"):
                code_data = state["generated_code"]
                if isinstance(code_data, dict):
                    if "main_pipeline_code" in code_data:
                        code_files["src/pipeline.py"] = code_data["main_pipeline_code"]

            # Get story info from parsed requirements
            requirements = state.get("parsed_requirements", {})

            # Prepare input for PR Agent
            pr_input = {
                "generated_code_files": code_files or {"src/pipeline.py": "# Generated code"},
                "generated_test_files": test_files or {"tests/test_pipeline.py": "# Generated tests"},
                "story_title": requirements.get("title", "ETL Pipeline"),
                "story_description": requirements.get("description", ""),
                "code_quality_score": state["code_quality_score"],
                "test_quality_score": state["test_quality_score"],
                "repository": {
                    "owner": "amalphonse",
                    "repo_name": "Autonomous-ETL-ELT-Agent-for-DevOps-Driven-Data-Engineering",
                },
            }

            # Execute PR Agent
            output = await self.pr_agent.execute(pr_input)

            if output.status == AgentStatus.SUCCESS:
                state["pull_request"] = output.data.get("pull_request")
                state["pr_quality_score"] = output.data.get("pr_quality_score", 0.0)
                state["execution_log"].append(
                    "✅ PR Agent: Pull Request prepared successfully"
                )
                logger.info(f"PR Agent quality score: {state['pr_quality_score']:.2%}")
            else:
                raise Exception(f"PR Agent failed: {output.error}")

        except Exception as e:
            logger.error(f"PR Agent error: {str(e)}")
            state["error"] = str(e)
            state["status"] = "failed"

        return state

    def get_summary(self, state: OrchestrationState) -> dict:
        """Generate a human-readable summary of orchestration results.

        Args:
            state: Final orchestration state.

        Returns:
            Summary dictionary with key metrics.
        """
        return {
            "status": state["status"],
            "task_confidence": state.get("task_confidence", 0.0),
            "code_quality": state.get("code_quality_score", 0.0),
            "test_quality": state.get("test_quality_score", 0.0),
            "pr_quality": state.get("pr_quality_score", 0.0),
            "overall_score": (
                (state.get("code_quality_score", 0.0)
                 + state.get("test_quality_score", 0.0)
                 + state.get("pr_quality_score", 0.0))
                / 3
            ),
            "execution_log": state.get("execution_log", []),
            "error": state.get("error"),
        }
