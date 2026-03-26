"""Tests for FastAPI endpoints."""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import uuid
from src.types import AgentStatus, AgentOutput


@pytest.fixture
def mock_orchestrator_settings():
    """Mock the settings for orchestrator initialization."""
    with patch("src.config.get_settings") as mock_settings:
        mock_settings.return_value = MagicMock(
            openai_api_key="test-key",
            openai_model="gpt-4o",
            github_token="test-token",
            github_repo_owner="test-owner",
            github_repo_name="test-repo",
            gcp_project_id="test-project",
        )
        yield mock_settings


@pytest.fixture
def client(mock_orchestrator_settings):
    """Create a test client for the FastAPI app with mocked settings."""
    # Import app after settings are mocked
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
        
        from src.api import app
        return TestClient(app)


class TestHealthEndpoint:
    """Test suite for health check endpoints."""

    def test_root_endpoint(self, client):
        """Test the root health check endpoint."""
        response = client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Autonomous ETL/ELT Agent"
        assert "version" in data


class TestCreatePipelineEndpoint:
    """Test suite for POST /pipelines/create endpoint."""

    def test_create_pipeline_success(self, client):
        """Test successful pipeline creation."""

        # Mock the orchestrator's execute and get_summary methods
        with patch("src.api.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_get_orch.return_value = mock_orch
            
            mock_orch.execute = AsyncMock(
                return_value={
                    "status": "success",
                    "user_story": {
                        "title": "Test Pipeline",
                        "description": "Test",
                    },
                    "parsed_requirements": {"title": "Test"},
                    "generated_code": {"main_pipeline_code": "# Code"},
                    "generated_tests": {"test_code": "# Tests"},
                    "pull_request": {"branch_name": "feature/test"},
                    "task_confidence": 0.95,
                    "code_quality_score": 0.88,
                    "test_quality_score": 0.85,
                    "pr_quality_score": 0.89,
                    "execution_log": ["✅ All agents completed"],
                    "error": None,
                }
            )

            mock_orch.get_summary.return_value = {
                "status": "success",
                "task_confidence": 0.95,
                "code_quality": 0.88,
                "test_quality": 0.85,
                "pr_quality": 0.89,
                "overall_score": 0.873,
                "execution_log": ["✅ All agents completed"],
                "error": None,
            }

            payload = {
                "title": "Test Pipeline",
                "description": "Create a test ETL pipeline",
                "source_system": "Salesforce",
                "target_system": "Snowflake",
            }

            response = client.post("/pipelines/create", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "success"
            assert data["task_confidence"] == 0.95
            assert data["code_quality"] == 0.88
            assert data["overall_quality"] == pytest.approx(0.873, abs=0.01)
            assert "execution_id" in data
            assert len(data["execution_id"]) > 0

    def test_create_pipeline_with_data_quality_rules(self, client):
        """Test pipeline creation with data quality rules."""

        with patch("src.api.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_get_orch.return_value = mock_orch
            
            mock_orch.execute = AsyncMock(
                return_value={
                    "status": "success",
                    "user_story": {"title": "Pipeline with QA Rules"},
                    "parsed_requirements": {"title": "Test"},
                    "generated_code": {"main_pipeline_code": "# Code"},
                    "generated_tests": {"test_code": "# Tests"},
                    "pull_request": {"branch_name": "feature/test"},
                    "task_confidence": 0.95,
                    "code_quality_score": 0.88,
                    "test_quality_score": 0.85,
                    "pr_quality_score": 0.89,
                    "execution_log": ["✅ Complete"],
                    "error": None,
                }
            )
            
            mock_orch.get_summary.return_value = {
                "status": "success",
                "task_confidence": 0.95,
                "code_quality": 0.88,
                "test_quality": 0.85,
                "pr_quality": 0.89,
                "overall_score": 0.873,
                "execution_log": ["✅ Complete"],
                "error": None,
            }
            
            payload = {
                "title": "Pipeline with QA Rules",
                "description": "Test with data quality",
                "data_quality_rules": [
                    "No nulls in customer_id",
                    "Valid email format",
                    "Date in valid range",
                ],
            }

            response = client.post("/pipelines/create", json=payload)

            assert response.status_code == 200

    def test_create_pipeline_with_performance_requirements(self, client):
        """Test pipeline creation with performance requirements."""

        with patch("src.api.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_get_orch.return_value = mock_orch
            
            mock_orch.execute = AsyncMock(
                return_value={
                    "status": "success",
                    "user_story": {"title": "High Performance Pipeline"},
                    "parsed_requirements": {"title": "Test"},
                    "generated_code": {"main_pipeline_code": "# Code"},
                    "generated_tests": {"test_code": "# Tests"},
                    "pull_request": {"branch_name": "feature/test"},
                    "task_confidence": 0.95,
                    "code_quality_score": 0.88,
                    "test_quality_score": 0.85,
                    "pr_quality_score": 0.89,
                    "execution_log": ["✅ Complete"],
                    "error": None,
                }
            )
            
            mock_orch.get_summary.return_value = {
                "status": "success",
                "task_confidence": 0.95,
                "code_quality": 0.88,
                "test_quality": 0.85,
                "pr_quality": 0.89,
                "overall_score": 0.873,
                "execution_log": ["✅ Complete"],
                "error": None,
            }
            
            payload = {
                "title": "High Performance Pipeline",
                "description": "Test with performance SLAs",
                "performance_requirements": {
                    "max_execution_time_minutes": 30,
                    "expected_row_count": 5000000,
                },
            }

            response = client.post("/pipelines/create", json=payload)

            assert response.status_code == 200

    def test_create_pipeline_missing_required_fields(self, client):
        """Test pipeline creation with missing required fields."""

        payload = {
            "title": "Incomplete Pipeline"
            # Missing required 'description'
        }

        response = client.post("/pipelines/create", json=payload)

        assert response.status_code == 422  # Validation error

    def test_create_pipeline_failure(self, client):
        """Test pipeline creation when orchestrator fails."""

        with patch("src.api.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_get_orch.return_value = mock_orch
            
            mock_orch.execute = AsyncMock(
                return_value={
                    "status": "failed",
                    "user_story": None,
                    "parsed_requirements": None,
                    "generated_code": None,
                    "generated_tests": None,
                    "pull_request": None,
                    "task_confidence": 0.0,
                    "code_quality_score": 0.0,
                    "test_quality_score": 0.0,
                    "pr_quality_score": 0.0,
                    "execution_log": [],
                    "error": "Task parsing failed",
                }
            )

            mock_orch.get_summary.return_value = {
                "status": "failed",
                "task_confidence": 0.0,
                "code_quality": 0.0,
                "test_quality": 0.0,
                "pr_quality": 0.0,
                "overall_score": 0.0,
                "execution_log": [],
                "error": "Task parsing failed",
            }

            payload = {
                "title": "Failing Pipeline",
                "description": "This will fail",
            }

            response = client.post("/pipelines/create", json=payload)

            assert response.status_code == 200
            data = response.json()
            assert data["status"] == "failed"
            assert data["error"] is not None


class TestGetPipelineEndpoint:
    """Test suite for GET /pipelines/{execution_id} endpoint."""

    def test_get_existing_pipeline(self, client):
        """Test retrieving an existing pipeline execution."""

        # Create a pipeline first
        execution_id = str(uuid.uuid4())

        with patch("src.api.get_orchestrator") as mock_get_orch:
            mock_orch = MagicMock()
            mock_get_orch.return_value = mock_orch
            
            execution_state = {
                "status": "success",
                "user_story": {"title": "Test Pipeline"},
                "parsed_requirements": {"title": "Test"},
                "generated_code": {"main_pipeline_code": "# Code"},
                "generated_tests": {"test_code": "# Tests"},
                "pull_request": {"branch_name": "feature/test"},
                "task_confidence": 0.95,
                "code_quality_score": 0.88,
                "test_quality_score": 0.85,
                "pr_quality_score": 0.89,
                "execution_log": ["✅ Complete"],
                "error": None,
            }

            mock_orch.get_summary.return_value = {
                "status": "success",
                "task_confidence": 0.95,
                "code_quality": 0.88,
                "test_quality": 0.85,
                "pr_quality": 0.89,
                "overall_score": 0.873,
                "execution_log": ["✅ Complete"],
            }

            # Store execution result
            from src.api import pipeline_results
            pipeline_results[execution_id] = execution_state

            # Retrieve the pipeline
            response = client.get(f"/pipelines/{execution_id}")

            assert response.status_code == 200
            data = response.json()
            assert data["execution_id"] == execution_id
            assert data["status"] == "success"
            assert data["generated_code"] is not None
            assert data["generated_tests"] is not None
            assert data["pull_request"] is not None

    def test_get_nonexistent_pipeline(self, client):
        """Test retrieving a non-existent pipeline."""

        execution_id = str(uuid.uuid4())

        response = client.get(f"/pipelines/{execution_id}")

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()


class TestListPipelinesEndpoint:
    """Test suite for GET /pipelines endpoint."""

    def test_list_pipelines_empty(self, client):
        """Test listing pipelines when none exist."""

        from src.api import pipeline_results

        # Clear pipeline results for this test
        original_results = dict(pipeline_results)
        pipeline_results.clear()
        
        try:
            response = client.get("/pipelines")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0
            assert data["pipelines"] == []
        finally:
            # Restore original results
            pipeline_results.update(original_results)

    def test_list_pipelines_multiple(self, client):
        """Test listing multiple pipelines."""

        from src.api import pipeline_results

        # Create mock executions
        exec_id_1 = str(uuid.uuid4())
        exec_id_2 = str(uuid.uuid4())

        execution_1 = {
            "status": "success",
            "user_story": {"title": "Pipeline 1"},
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "task_confidence": 0.95,
            "code_quality_score": 0.88,
            "test_quality_score": 0.85,
            "pr_quality_score": 0.89,
            "execution_log": [],
            "error": None,
        }

        execution_2 = {
            "status": "success",
            "user_story": {"title": "Pipeline 2"},
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "task_confidence": 0.92,
            "code_quality_score": 0.85,
            "test_quality_score": 0.82,
            "pr_quality_score": 0.86,
            "execution_log": [],
            "error": None,
        }

        # Store temporarily
        original_results = dict(pipeline_results)
        pipeline_results.clear()
        pipeline_results[exec_id_1] = execution_1
        pipeline_results[exec_id_2] = execution_2
        
        try:
            with patch("src.api.get_orchestrator") as mock_get_orch:
                mock_orch = MagicMock()
                mock_get_orch.return_value = mock_orch
                mock_orch.get_summary.side_effect = [
                    {
                        "status": "success",
                        "overall_score": 0.873,
                        "execution_log": [],
                    },
                    {
                        "status": "success",
                        "overall_score": 0.843,
                        "execution_log": [],
                    },
                ]

                response = client.get("/pipelines")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                assert len(data["pipelines"]) == 2
                assert data["pipelines"][0]["status"] == "success"
                assert data["pipelines"][1]["status"] == "success"
        finally:
            # Restore original results
            pipeline_results.clear()
            pipeline_results.update(original_results)

    def test_list_pipelines_with_mixed_statuses(self, client):
        """Test listing pipelines with different statuses."""

        from src.api import pipeline_results

        exec_id_1 = str(uuid.uuid4())
        exec_id_2 = str(uuid.uuid4())

        execution_1 = {
            "status": "success",
            "user_story": {"title": "Successful Pipeline"},
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "task_confidence": 0.95,
            "code_quality_score": 0.88,
            "test_quality_score": 0.85,
            "pr_quality_score": 0.89,
            "execution_log": [],
            "error": None,
        }

        execution_2 = {
            "status": "failed",
            "user_story": {"title": "Failed Pipeline"},
            "parsed_requirements": None,
            "generated_code": None,
            "generated_tests": None,
            "pull_request": None,
            "task_confidence": 0.0,
            "code_quality_score": 0.0,
            "test_quality_score": 0.0,
            "pr_quality_score": 0.0,
            "execution_log": [],
            "error": "Task parsing failed",
        }

        # Store temporarily
        original_results = dict(pipeline_results)
        pipeline_results.clear()
        pipeline_results[exec_id_1] = execution_1
        pipeline_results[exec_id_2] = execution_2
        
        try:
            with patch("src.api.get_orchestrator") as mock_get_orch:
                mock_orch = MagicMock()
                mock_get_orch.return_value = mock_orch
                mock_orch.get_summary.side_effect = [
                    {"status": "success", "overall_score": 0.873},
                    {"status": "failed", "overall_score": 0.0},
                ]

                response = client.get("/pipelines")

                assert response.status_code == 200
                data = response.json()
                assert data["total"] == 2
                assert data["pipelines"][0]["story_title"] == "Successful Pipeline"
                assert data["pipelines"][1]["story_title"] == "Failed Pipeline"
        finally:
            # Restore original results
            pipeline_results.clear()
            pipeline_results.update(original_results)


class TestPipelineInputModels:
    """Test suite for input/output models."""

    def test_user_story_input_minimal(self):
        """Test UserStoryInput with minimal fields."""
        from src.api import UserStoryInput

        story = UserStoryInput(
            title="Simple Pipeline",
            description="A simple ETL pipeline",
        )

        assert story.title == "Simple Pipeline"
        assert story.description == "A simple ETL pipeline"
        assert story.source_system is None
        assert story.target_system is None
        assert story.data_quality_rules is None

    def test_user_story_input_complete(self):
        """Test UserStoryInput with all fields."""
        from src.api import UserStoryInput

        story = UserStoryInput(
            title="Complete Pipeline",
            description="Full ETL pipeline",
            source_system="Postgres",
            target_system="BigQuery",
            data_quality_rules=["No nulls", "Valid dates"],
            performance_requirements={"timeout": 300},
        )

        assert story.title == "Complete Pipeline"
        assert story.source_system == "Postgres"
        assert story.target_system == "BigQuery"
        assert len(story.data_quality_rules) == 2
        assert story.performance_requirements["timeout"] == 300

    def test_pipeline_response_model(self):
        """Test PipelineResponse model."""
        from src.api import PipelineResponse

        response = PipelineResponse(
            execution_id="test-uuid",
            status="success",
            message="Pipeline created successfully",
            task_confidence=0.95,
            code_quality=0.88,
            test_quality=0.85,
            pr_quality=0.89,
            overall_quality=0.87,
            execution_log=["Step 1", "Step 2"],
            error=None,
        )

        assert response.execution_id == "test-uuid"
        assert response.status == "success"
        assert response.overall_quality == 0.87
        assert len(response.execution_log) == 2
