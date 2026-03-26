"""Tests for the orchestration layer."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import logging

from src.orchestration import AgentOrchestrator, OrchestrationState
from src.types import AgentStatus, AgentOutput, AgentType


@pytest.fixture
def mock_settings():
    """Mock the settings object."""
    with patch("src.config.get_settings") as mock:
        mock.return_value = MagicMock(
            openai_api_key="test-key",
            openai_model="gpt-4o",
            github_token="test-token",
            github_repo_owner="test-owner",
            github_repo_name="test-repo",
            gcp_project_id="test-project",
        )
        yield mock


@pytest.fixture
def orchestrator(mock_settings):
    """Create an orchestrator instance."""
    with patch("src.agents.task_agent.task_agent.get_settings") as task_mock, \
         patch("src.agents.coding_agent.coding_agent.get_settings") as coding_mock, \
         patch("src.agents.test_agent.test_agent.get_settings") as test_mock, \
         patch("src.agents.pr_agent.pr_agent.get_settings") as pr_mock:
        
        mock_settings_obj = MagicMock(
            openai_api_key="test-key",
            openai_model="gpt-4o",
            github_token="test-token",
            github_repo_owner="test-owner",
            github_repo_name="test-repo",
            gcp_project_id="test-project",
        )
        
        task_mock.return_value = mock_settings_obj
        coding_mock.return_value = mock_settings_obj
        test_mock.return_value = mock_settings_obj
        pr_mock.return_value = mock_settings_obj
        
        return AgentOrchestrator()


class TestAgentOrchestrator:
    """Test suite for AgentOrchestrator."""

    @pytest.mark.asyncio
    async def test_orchestrator_initialization(self, orchestrator):
        """Test that orchestrator initializes with all agents."""
        assert orchestrator.task_agent is not None
        assert orchestrator.coding_agent is not None
        assert orchestrator.test_agent is not None
        assert orchestrator.pr_agent is not None

    @pytest.mark.asyncio
    async def test_graph_structure(self, orchestrator):
        """Test that the orchestrator is properly initialized."""
        # Verify all agents are initialized
        assert orchestrator.task_agent is not None
        assert orchestrator.coding_agent is not None
        assert orchestrator.test_agent is not None
        assert orchestrator.pr_agent is not None

    @pytest.mark.asyncio
    async def test_execute_with_all_agents_success(self, orchestrator):
        """Test successful execution through all agents."""

        # Mock all agents to return success
        orchestrator.task_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TASK,
                status=AgentStatus.SUCCESS,
                data={
                    "requirements": {
                        "title": "Test ETL",
                        "description": "Test description",
                    },
                    "confidence_score": 0.95,
                },
                error=None,
            )
        )

        orchestrator.coding_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.CODING,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_code": {"main_pipeline_code": "# PySpark code"},
                    "code_quality_score": 0.88,
                },
                error=None,
            )
        )

        orchestrator.test_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TEST,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_tests": {"test_code": "# Pytest code"},
                    "test_quality_score": 0.85,
                    "coverage_metrics": {"line_coverage": 85.0},
                },
                error=None,
            )
        )

        orchestrator.pr_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.PR,
                status=AgentStatus.SUCCESS,
                data={
                    "pull_request": {"branch_name": "feature/test-etl"},
                    "pr_quality_score": 0.89,
                },
                error=None,
            )
        )

        # Execute orchestration
        user_story = {
            "title": "Test ETL Pipeline",
            "description": "Create a test pipeline",
        }

        final_state = await orchestrator.execute(user_story)

        # Assertions
        assert final_state["status"] == "success"
        assert final_state["task_confidence"] == 0.95
        assert final_state["code_quality_score"] == 0.88
        assert final_state["test_quality_score"] == 0.85
        assert final_state["pr_quality_score"] == 0.89
        assert len(final_state["execution_log"]) == 4

    @pytest.mark.asyncio
    async def test_execute_task_agent_failure(self, orchestrator):
        """Test orchestration when Task Agent fails."""

        orchestrator.task_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TASK,
                status=AgentStatus.FAILED,
                data={},
                error="Failed to parse requirements",
            )
        )

        user_story = {"title": "Test", "description": "Test"}

        final_state = await orchestrator.execute(user_story)

        assert final_state["status"] == "failed"
        assert final_state["error"] is not None
        assert "Task Agent" in final_state["error"]

    @pytest.mark.asyncio
    async def test_execute_without_task_output_for_coding(self, orchestrator):
        """Test that Coding Agent fails without Task Agent output."""

        orchestrator.task_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TASK,
                status=AgentStatus.SUCCESS,
                data={},  # Missing requirements
                error=None,
            )
        )

        user_story = {"title": "Test", "description": "Test"}

        final_state = await orchestrator.execute(user_story)

        assert final_state["status"] == "failed"
        assert "Coding Agent" in final_state["error"] or "missing" in final_state["error"]

    @pytest.mark.asyncio
    async def test_get_summary(self, orchestrator):
        """Test summary generation from final state."""

        state: OrchestrationState = {
            "status": "success",
            "task_confidence": 0.95,
            "code_quality_score": 0.88,
            "test_quality_score": 0.85,
            "pr_quality_score": 0.89,
            "execution_log": [
                "✅ Task Agent: Requirements parsed",
                "✅ Coding Agent: Code generated",
            ],
            "error": None,
            "user_story": None,
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "coverage_metrics": None,
        }

        summary = orchestrator.get_summary(state)

        assert summary["status"] == "success"
        assert summary["task_confidence"] == 0.95
        assert summary["code_quality"] == 0.88
        assert summary["test_quality"] == 0.85
        assert summary["pr_quality"] == 0.89
        assert summary["overall_score"] == pytest.approx(
            (0.88 + 0.85 + 0.89) / 3, abs=0.01
        )
        assert len(summary["execution_log"]) == 2

    @pytest.mark.asyncio
    async def test_run_task_agent(self, orchestrator):
        """Test Task Agent execution in orchestration."""

        state: OrchestrationState = {
            "user_story": {"title": "Test", "description": "Test"},
            "status": "initialized",
            "execution_log": [],
            "error": None,
            "task_confidence": 0.0,
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "code_quality_score": 0.0,
            "test_quality_score": 0.0,
            "pr_quality_score": 0.0,
            "coverage_metrics": None,
        }

        orchestrator.task_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TASK,
                status=AgentStatus.SUCCESS,
                data={
                    "requirements": {"title": "Test"},
                    "confidence_score": 0.92,
                },
                error=None,
            )
        )

        result = await orchestrator._run_task_agent(state)

        assert result["parsed_requirements"] == {"title": "Test"}
        assert result["task_confidence"] == 0.92
        assert "✅ Task Agent" in result["execution_log"][0]

    @pytest.mark.asyncio
    async def test_run_coding_agent(self, orchestrator):
        """Test Coding Agent execution in orchestration."""

        state: OrchestrationState = {
            "parsed_requirements": {
                "title": "Test",
                "transformations": ["test_transform"],
            },
            "status": "initialized",
            "execution_log": [],
            "error": None,
            "user_story": None,
            "task_confidence": 0.0,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "code_quality_score": 0.0,
            "test_quality_score": 0.0,
            "pr_quality_score": 0.0,
            "coverage_metrics": None,
        }

        orchestrator.coding_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.CODING,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_code": {"main_pipeline_code": "# Code"},
                    "code_quality_score": 0.87,
                },
                error=None,
            )
        )

        result = await orchestrator._run_coding_agent(state)

        assert result["generated_code"] == {"main_pipeline_code": "# Code"}
        assert result["code_quality_score"] == 0.87
        assert "✅ Coding Agent" in result["execution_log"][0]

    @pytest.mark.asyncio
    async def test_run_test_agent(self, orchestrator):
        """Test Test Agent execution in orchestration."""

        state: OrchestrationState = {
            "parsed_requirements": {"title": "Test"},
            "generated_code": {"main_pipeline_code": "# Code"},
            "status": "initialized",
            "execution_log": [],
            "error": None,
            "user_story": None,
            "task_confidence": 0.0,
            "generated_tests": None,
            "pull_request": None,
            "code_quality_score": 0.87,
            "test_quality_score": 0.0,
            "pr_quality_score": 0.0,
            "coverage_metrics": None,
        }

        orchestrator.test_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TEST,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_tests": {"test_code": "# Tests"},
                    "test_quality_score": 0.84,
                    "coverage_metrics": {"line_coverage": 80.0},
                },
                error=None,
            )
        )

        result = await orchestrator._run_test_agent(state)

        assert result["generated_tests"] == {"test_code": "# Tests"}
        assert result["test_quality_score"] == 0.84
        assert result["coverage_metrics"]["line_coverage"] == 80.0
        assert "✅ Test Agent" in result["execution_log"][0]

    @pytest.mark.asyncio
    async def test_run_pr_agent(self, orchestrator):
        """Test PR Agent execution in orchestration."""

        state: OrchestrationState = {
            "generated_code": {"main_pipeline_code": "# Code"},
            "generated_tests": {"test_code": "# Tests"},
            "parsed_requirements": {
                "title": "Test Pipeline",
                "description": "Test description",
            },
            "status": "initialized",
            "execution_log": [],
            "error": None,
            "user_story": None,
            "task_confidence": 0.0,
            "pull_request": None,
            "code_quality_score": 0.87,
            "test_quality_score": 0.84,
            "pr_quality_score": 0.0,
            "coverage_metrics": None,
        }

        orchestrator.pr_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.PR,
                status=AgentStatus.SUCCESS,
                data={
                    "pull_request": {"branch_name": "feature/test-pipeline"},
                    "pr_quality_score": 0.88,
                },
                error=None,
            )
        )

        result = await orchestrator._run_pr_agent(state)

        assert result["pull_request"]["branch_name"] == "feature/test-pipeline"
        assert result["pr_quality_score"] == 0.88
        assert "✅ PR Agent" in result["execution_log"][0]

    @pytest.mark.asyncio
    async def test_exception_handling(self, orchestrator):
        """Test graceful exception handling in orchestration."""

        orchestrator.task_agent.execute = AsyncMock(
            side_effect=Exception("Network error")
        )

        user_story = {"title": "Test", "description": "Test"}

        final_state = await orchestrator.execute(user_story)

        assert final_state["status"] == "failed"
        assert final_state["error"] is not None
        assert "Network error" in final_state["error"]

    @pytest.mark.asyncio
    async def test_orchestrator_state_flow(self, orchestrator):
        """Test complete state flow through all agents."""

        # Mock all agents
        orchestrator.task_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TASK,
                status=AgentStatus.SUCCESS,
                data={
                    "requirements": {"title": "E2E Test"},
                    "confidence_score": 0.93,
                },
                error=None,
            )
        )

        orchestrator.coding_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.CODING,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_code": {"main_pipeline_code": "# PySpark"},
                    "code_quality_score": 0.90,
                },
                error=None,
            )
        )

        orchestrator.test_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.TEST,
                status=AgentStatus.SUCCESS,
                data={
                    "generated_tests": {"test_code": "# Pytest"},
                    "test_quality_score": 0.89,
                    "coverage_metrics": {"line_coverage": 88.0},
                },
                error=None,
            )
        )

        orchestrator.pr_agent.execute = AsyncMock(
            return_value=AgentOutput(
                agent_type=AgentType.PR,
                status=AgentStatus.SUCCESS,
                data={
                    "pull_request": {
                        "branch_name": "feature/e2e-test",
                        "commits": ["Commit 1"],
                    },
                    "pr_quality_score": 0.91,
                },
                error=None,
            )
        )

        user_story = {
            "title": "End-to-End Test",
            "description": "Complete orchestration test",
        }

        final_state = await orchestrator.execute(user_story)

        # Verify complete flow
        assert final_state["status"] == "success"
        assert final_state["user_story"]["title"] == "End-to-End Test"
        assert final_state["parsed_requirements"]["title"] == "E2E Test"
        assert final_state["generated_code"] is not None
        assert final_state["generated_tests"] is not None
        assert final_state["pull_request"] is not None

        # Verify all scores are captured
        assert final_state["task_confidence"] == 0.93
        assert final_state["code_quality_score"] == 0.90
        assert final_state["test_quality_score"] == 0.89
        assert final_state["pr_quality_score"] == 0.91

        # Verify execution log
        assert len(final_state["execution_log"]) == 4
        assert "Task Agent" in final_state["execution_log"][0]
        assert "Coding Agent" in final_state["execution_log"][1]
        assert "Test Agent" in final_state["execution_log"][2]
        assert "PR Agent" in final_state["execution_log"][3]
