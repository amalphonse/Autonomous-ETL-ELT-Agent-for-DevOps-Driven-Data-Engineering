"""Unit tests for the Task Agent."""

import pytest
import json
from unittest.mock import patch, MagicMock, AsyncMock

from src.agents.task_agent import TaskAgent, UserStory, ParsedRequirements
from src.types import AgentStatus, AgentType


@pytest.fixture
def task_agent():
    """Fixture for TaskAgent instance."""
    with patch("src.agents.task_agent.task_agent.ChatOpenAI"):
        return TaskAgent()


@pytest.fixture
def sample_user_story():
    """Fixture for a sample user story."""
    return UserStory(
        user_id="user123",
        request_id="req456",
        story="I need to filter orders from the last 30 days where total amount > 1000, "
        "join with customer data, and aggregate by customer region. "
        "Output should be written to the analytics table.",
        format="text",
    )


@pytest.fixture
def mock_llm_response():
    """Fixture for mock LLM response."""
    return """{
        "story_id": "req456",
        "title": "Filter and aggregate orders by region",
        "description": "Filter orders from the last 30 days with amount > 1000, join with customer data, and aggregate by region",
        "input_sources": [
            {
                "name": "orders",
                "location": "data/orders",
                "format": "parquet",
                "schema": [
                    {"name": "order_id", "data_type": "string", "nullable": false, "description": "Order ID"},
                    {"name": "customer_id", "data_type": "string", "nullable": false, "description": "Customer ID"},
                    {"name": "amount", "data_type": "double", "nullable": false, "description": "Order amount"},
                    {"name": "order_date", "data_type": "date", "nullable": false, "description": "Order date"}
                ],
                "is_streaming": false
            },
            {
                "name": "customers",
                "location": "data/customers",
                "format": "parquet",
                "schema": [
                    {"name": "customer_id", "data_type": "string", "nullable": false, "description": "Customer ID"},
                    {"name": "region", "data_type": "string", "nullable": false, "description": "Customer region"}
                ],
                "is_streaming": false
            }
        ],
        "output_schema": [
            {"name": "region", "data_type": "string", "nullable": false, "description": "Customer region"},
            {"name": "total_amount", "data_type": "double", "nullable": false, "description": "Total order amount"},
            {"name": "order_count", "data_type": "integer", "nullable": false, "description": "Number of orders"}
        ],
        "output_location": "analytics/orders_by_region",
        "transformation_steps": [
            {
                "step_id": "step1",
                "transformation_type": "filter",
                "description": "Filter orders from last 30 days with amount > 1000",
                "inputs": ["orders"],
                "outputs": ["filtered_orders"],
                "parameters": {"days": 30, "min_amount": 1000},
                "sql_snippet": null
            },
            {
                "step_id": "step2",
                "transformation_type": "join",
                "description": "Join with customer data",
                "inputs": ["filtered_orders", "customers"],
                "outputs": ["orders_with_region"],
                "parameters": {"join_type": "inner", "on": "customer_id"},
                "sql_snippet": null
            },
            {
                "step_id": "step3",
                "transformation_type": "aggregate",
                "description": "Group by region and sum amounts",
                "inputs": ["orders_with_region"],
                "outputs": ["result"],
                "parameters": {"group_by": ["region"], "aggregations": {"total_amount": "sum(amount)", "order_count": "count(*)"}},
                "sql_snippet": null
            }
        ],
        "quality_rules": [
            {
                "rule_id": "rule1",
                "rule_type": "null_check",
                "column": "total_amount",
                "description": "Verify no null amounts in output",
                "parameters": {}
            }
        ],
        "frequency": "daily",
        "sla_hours": 4.0,
        "dependencies": [],
        "metadata": {}
    }"""


class TestTaskAgent:
    """Test suite for TaskAgent."""

    def test_agent_initialization(self, task_agent):
        """Test that TaskAgent initializes correctly."""
        assert task_agent.agent_type == AgentType.TASK
        assert task_agent.llm is not None

    def test_user_story_validation_valid(self, task_agent, sample_user_story):
        """Test that valid user stories pass validation."""
        agent_input = {"user_story": sample_user_story.dict()}
        assert task_agent.validate_input(agent_input) is True

    def test_user_story_validation_missing_field(self, task_agent):
        """Test that user stories with missing fields fail validation."""
        invalid_input = {
            "request_id": "req123",
            # Missing user_story field
        }
        assert task_agent.validate_input(invalid_input) is False

    def test_user_story_validation_invalid_format(self, task_agent):
        """Test that completely invalid input fails validation."""
        assert task_agent.validate_input("not a dict") is False
        assert task_agent.validate_input(None) is False

    def test_parse_llm_response_valid_json(self, task_agent, mock_llm_response):
        """Test parsing valid JSON from LLM response."""
        result = task_agent._parse_llm_response(mock_llm_response)
        assert isinstance(result, dict)
        assert "story_id" in result
        assert result["story_id"] == "req456"

    def test_parse_llm_response_json_in_text(self, task_agent, mock_llm_response):
        """Test parsing JSON embedded in text response."""
        wrapped_response = f"Here's the parsed result:\n{mock_llm_response}\nDone."
        result = task_agent._parse_llm_response(wrapped_response)
        assert isinstance(result, dict)
        assert result["story_id"] == "req456"

    def test_parse_llm_response_invalid(self, task_agent):
        """Test that invalid JSON raises an error."""
        with pytest.raises(ValueError):
            task_agent._parse_llm_response("This is not JSON at all")

    def test_format_user_story(self, task_agent, sample_user_story):
        """Test that user stories are formatted correctly for LLM."""
        formatted = task_agent._format_user_story(sample_user_story)
        assert "user123" in formatted
        assert "req456" in formatted
        assert "filter orders" in formatted

    def test_format_user_story_with_attachments(self, task_agent):
        """Test formatting user story with attachments."""
        story = UserStory(
            user_id="user1",
            request_id="req1",
            story="Process data",
            attachments={"sample_schema": {"col1": "string"}},
        )
        formatted = task_agent._format_user_story(story)
        assert "Attachments:" in formatted
        assert "sample_schema" in formatted

    def test_calculate_confidence_score(self, task_agent, sample_user_story, mock_llm_response):
        """Test confidence score calculation."""
        parsed_dict = json.loads(mock_llm_response)
        requirements = ParsedRequirements(**parsed_dict)

        score = task_agent._calculate_confidence(sample_user_story, requirements)

        assert isinstance(score, float)
        assert 0 <= score <= 1.0
        assert score > 0.8  # Should be high confidence with complete requirements

    def test_error_output(self, task_agent):
        """Test error output creation."""
        output = task_agent._error_output("Test error message")
        assert output.agent_type == AgentType.TASK
        assert output.status == AgentStatus.FAILED
        assert output.error == "Test error message"

    @pytest.mark.asyncio
    async def test_execute_success(self, task_agent, sample_user_story, mock_llm_response):
        """Test successful execution of TaskAgent."""
        # Mock the LLM response
        mock_response = MagicMock()
        mock_response.content = mock_llm_response

        with patch.object(
            task_agent.llm,
            "invoke",
            return_value=mock_response
        ):
            agent_input = {"user_story": sample_user_story.dict()}
            output = await task_agent.execute(agent_input)

            assert output.agent_type == AgentType.TASK
            assert output.status == AgentStatus.SUCCESS
            assert output.error is None
            assert "requirements" in output.data

    @pytest.mark.asyncio
    async def test_execute_invalid_input(self, task_agent):
        """Test execution with invalid input."""
        invalid_input = {"no_user_story": "here"}
        output = await task_agent.execute(invalid_input)

        assert output.status == AgentStatus.FAILED
        assert output.error is not None

    @pytest.mark.asyncio
    async def test_execute_llm_error(self, task_agent, sample_user_story):
        """Test execution when LLM fails."""
        with patch.object(
            task_agent.llm,
            "invoke",
            side_effect=Exception("LLM error")
        ):
            agent_input = {"user_story": sample_user_story.dict()}
            output = await task_agent.execute(agent_input)

            assert output.status == AgentStatus.FAILED
            assert "LLM error" in output.error or "Task Agent failed" in output.error


class TestTaskAgentSchemas:
    """Test suite for Task Agent schemas."""

    def test_user_story_creation(self):
        """Test UserStory creation."""
        story = UserStory(
            user_id="user1",
            request_id="req1",
            story="Transform data",
        )
        assert story.user_id == "user1"
        assert story.format == "text"  # Default

    def test_column_definition(self):
        """Test ColumnDefinition creation."""
        from src.agents.task_agent.schemas import ColumnDefinition, DataType

        col = ColumnDefinition(
            name="user_id",
            data_type=DataType.STRING,
            nullable=False,
            description="User identifier",
        )
        assert col.name == "user_id"
        assert col.data_type == DataType.STRING
        assert col.nullable is False

    def test_transformation_step(self):
        """Test TransformationStep creation."""
        from src.agents.task_agent.schemas import TransformationStep, TransformationType

        step = TransformationStep(
            step_id="step1",
            transformation_type=TransformationType.FILTER,
            description="Filter by date",
            inputs=["orders"],
            outputs=["filtered_orders"],
            parameters={"date_range": "30_days"},
        )
        assert step.step_id == "step1"
        assert step.transformation_type == TransformationType.FILTER

    def test_parsed_requirements(self, mock_llm_response):
        """Test ParsedRequirements creation from parsed data."""
        parsed_dict = json.loads(mock_llm_response)
        requirements = ParsedRequirements(**parsed_dict)

        assert requirements.story_id == "req456"
        assert len(requirements.input_sources) == 2
        assert len(requirements.transformation_steps) == 3
        assert requirements.frequency == "daily"
