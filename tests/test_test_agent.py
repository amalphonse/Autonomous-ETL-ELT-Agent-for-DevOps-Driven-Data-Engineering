"""Unit tests for the Test Agent."""

import pytest
import json
from unittest.mock import patch, MagicMock

from src.agents.test_agent import TestAgent, TestAgentInput, TestAgentOutput
from src.agents.coding_agent.schemas import (
    GeneratedCode,
    PydanticModel,
    CodeFile,
)
from src.agents.task_agent.schemas import (
    ParsedRequirements,
    DataSource,
    ColumnDefinition,
    DataType,
    TransformationStep,
    TransformationType,
    DataQualityRule,
)
from src.types import AgentStatus, AgentType


@pytest.fixture
def test_agent():
    """Fixture for TestAgent instance."""
    with patch("src.agents.test_agent.test_agent.ChatOpenAI"):
        with patch("src.agents.test_agent.test_agent.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"
            mock_settings.return_value.openai_model = "gpt-4o"
            mock_settings.return_value.openai_temperature = 0.3
            return TestAgent()


@pytest.fixture
def sample_generated_code():
    """Fixture for sample generated code."""
    return GeneratedCode(
        main_pipeline_code="""
from pyspark.sql import SparkSession
from pyspark.sql.functions import col, sum, count

def process_orders(spark):
    df = spark.read.parquet('data/orders')
    return df.groupBy('region').agg(sum('amount'))
""",
        input_schema_model=PydanticModel(
            model_name="OrdersInputSchema",
            module_name="models.input_schema",
            description="Input schema for orders",
            code="class OrdersInputSchema: pass",
            fields=[],
        ),
        output_schema_model=PydanticModel(
            model_name="OutputSchema",
            module_name="models.output_schema",
            description="Output schema",
            code="class OutputSchema: pass",
            fields=[],
        ),
    )


@pytest.fixture
def sample_requirements():
    """Fixture for sample requirements."""
    return ParsedRequirements(
        story_id="req789",
        title="Process orders by region",
        description="Group orders by region and calculate totals",
        input_sources=[
            DataSource(
                name="orders",
                location="data/orders",
                format="parquet",
                schema=[
                    ColumnDefinition(
                        name="region",
                        data_type=DataType.STRING,
                        nullable=False,
                    ),
                    ColumnDefinition(
                        name="amount",
                        data_type=DataType.DOUBLE,
                        nullable=False,
                    ),
                ],
                is_streaming=False,
            )
        ],
        output_schema=[
            ColumnDefinition(
                name="region",
                data_type=DataType.STRING,
                nullable=False,
            ),
            ColumnDefinition(
                name="total",
                data_type=DataType.DOUBLE,
                nullable=False,
            ),
        ],
        output_location="analytics/orders_summary",
        transformation_steps=[
            TransformationStep(
                step_id="step1",
                transformation_type=TransformationType.AGGREGATE,
                description="Sum amounts by region",
                inputs=["orders"],
                outputs=["result"],
                parameters={"group_by": ["region"]},
            )
        ],
        quality_rules=[
            DataQualityRule(
                rule_id="rule1",
                rule_type="null_check",
                column="region",
                description="Region must not be null",
                parameters={},
            )
        ],
        frequency="daily",
        sla_hours=2,
        dependencies=[],
        metadata={},
    )


@pytest.fixture
def mock_llm_test_response():
    """Fixture for mock LLM test generation response."""
    return """{
  "test_file_name": "test_pipeline.py",
  "test_file_path": "tests/test_pipeline.py",
  "test_code": "import pytest\\nfrom pyspark.sql import SparkSession\\n\\ndef test_process_orders(spark):\\n    result = process_orders(spark)\\n    assert result.count() > 0\\n",
  "test_cases": [
    {
      "test_name": "test_process_orders",
      "test_type": "unit",
      "description": "Test order processing function",
      "test_code": "def test_process_orders(spark): pass",
      "input_data": {},
      "expected_output": {},
      "assertions": ["assert result.count() > 0"]
    },
    {
      "test_name": "test_orders_aggregation",
      "test_type": "integration",
      "description": "Test orders aggregation with sample data",
      "test_code": "def test_orders_aggregation(spark): pass",
      "input_data": {"region": "US", "amount": 100},
      "expected_output": {"region": "US", "total": 100},
      "assertions": ["assert result['total'] == 100"]
    }
  ],
  "validation_suites": [],
  "imports": [
    "import pytest",
    "from pyspark.sql import SparkSession"
  ],
  "fixtures": {
    "spark": "def spark(): return SparkSession.builder.getOrCreate()"
  },
  "conftest_code": null
}"""


class TestTestAgentInitialization:
    """Tests for Test Agent initialization."""

    def test_agent_initialization(self, test_agent):
        """Test that Test Agent initializes correctly."""
        assert test_agent.agent_type == AgentType.TEST
        assert test_agent.llm is not None
        assert test_agent.test_generation_prompt is not None

    def test_agent_has_methods(self, test_agent):
        """Test that Test Agent has all required methods."""
        assert hasattr(test_agent, "execute")
        assert hasattr(test_agent, "validate_input")
        assert hasattr(test_agent, "_generate_test_suite")
        assert hasattr(test_agent, "_generate_validation_tests")


class TestInputValidation:
    """Tests for Test Agent input validation."""

    def test_valid_input(self, test_agent, sample_generated_code, sample_requirements):
        """Test validation of valid input."""
        valid_input = {
            "generated_code": sample_generated_code.model_dump(),
            "requirements": sample_requirements.model_dump(),
        }
        assert test_agent.validate_input(valid_input) is True

    def test_missing_generated_code(self, test_agent, sample_requirements):
        """Test validation fails without generated code."""
        invalid_input = {"requirements": sample_requirements.model_dump()}
        assert test_agent.validate_input(invalid_input) is False

    def test_missing_requirements(self, test_agent, sample_generated_code):
        """Test validation fails without requirements."""
        invalid_input = {"generated_code": sample_generated_code.model_dump()}
        assert test_agent.validate_input(invalid_input) is False


class TestJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_clean_json(self, test_agent):
        """Test extraction of clean JSON."""
        json_str = '{"test_cases": [], "imports": []}'
        result = test_agent._extract_json(json_str)
        assert json.loads(result) == {"test_cases": [], "imports": []}

    def test_extract_wrapped_json(self, test_agent):
        """Test extraction of JSON wrapped in markdown or text."""
        response = """Here's the generated tests:

```json
{"test_cases": [], "imports": []}
```

This is the complete test suite."""
        result = test_agent._extract_json(response)
        assert json.loads(result) == {"test_cases": [], "imports": []}


class TestCoverageMetrics:
    """Tests for coverage metrics calculation."""

    def test_coverage_calculation(
        self, test_agent, sample_requirements
    ):
        """Test that coverage metrics are calculated correctly."""
        from src.agents.test_agent.schemas import GeneratedTests, TestCase

        test_cases = [
            TestCase(
                test_name="test1",
                test_type="unit",
                description="Test 1",
                test_code="def test1(): pass",
                assertions=["assert True"],
            ),
            TestCase(
                test_name="test2",
                test_type="integration",
                description="Test 2",
                test_code="def test2(): pass",
                assertions=["assert True", "assert False"],
            ),
        ]

        generated_tests = GeneratedTests(
            test_code="code",
            test_cases=test_cases,
        )

        metrics = test_agent._calculate_coverage_metrics(
            generated_tests, sample_requirements
        )

        assert 0.0 <= metrics.line_coverage_percent <= 1.0
        assert 0.0 <= metrics.branch_coverage_percent <= 1.0
        assert 0.0 <= metrics.function_coverage_percent <= 1.0
        assert metrics.test_count == 2
        assert metrics.assertions_count >= 2

    def test_quality_score_range(self, test_agent):
        """Test that quality scores are in valid range."""
        from src.agents.test_agent.schemas import GeneratedTests, TestCoverageMetrics

        generated_tests = GeneratedTests(test_code="code", test_cases=[])
        metrics = TestCoverageMetrics(
            line_coverage_percent=0.8,
            branch_coverage_percent=0.7,
            function_coverage_percent=0.9,
            test_count=5,
            assertions_count=10,
            estimated_quality_score=0.8,
        )

        score = test_agent._calculate_quality_score(
            generated_tests, metrics, target_coverage=0.85
        )

        assert 0.0 <= score <= 1.0


class TestCodeFormatting:
    """Tests for code formatting."""

    def test_format_generated_code(self, test_agent, sample_generated_code):
        """Test formatting of generated code."""
        formatted = test_agent._format_generated_code(sample_generated_code)

        assert "InputSchema" in formatted
        assert "OutputSchema" in formatted
        assert "main_pipeline_code" not in formatted  # Truncated


class TestTestAgentOutput:
    """Tests for Test Agent output structure."""

    @pytest.mark.asyncio
    async def test_successful_execution(
        self,
        test_agent,
        sample_generated_code,
        sample_requirements,
        mock_llm_test_response,
    ):
        """Test successful execution of Test Agent."""
        with patch.object(
            test_agent, "_generate_test_suite"
        ) as mock_generate:
            mock_generate.return_value = json.loads(mock_llm_test_response)

            agent_input = {
                "generated_code": sample_generated_code.model_dump(),
                "requirements": sample_requirements.model_dump(),
            }

            output = await test_agent.execute(agent_input)

            assert output.status == AgentStatus.SUCCESS
            assert output.agent_type == AgentType.TEST
            assert "generated_tests" in output.data
            assert "coverage_metrics" in output.data
            assert "test_quality_score" in output.data

    @pytest.mark.asyncio
    async def test_invalid_input_execution(self, test_agent):
        """Test execution with invalid input."""
        invalid_input = {"invalid": "data"}

        output = await test_agent.execute(invalid_input)

        assert output.status == AgentStatus.FAILED
        assert output.error is not None

    @pytest.mark.asyncio
    async def test_error_handling(self, test_agent, sample_generated_code, sample_requirements):
        """Test error handling when code generation fails."""
        with patch.object(
            test_agent, "_generate_test_suite"
        ) as mock_generate:
            mock_generate.side_effect = Exception("LLM error")

            agent_input = {
                "generated_code": sample_generated_code.model_dump(),
                "requirements": sample_requirements.model_dump(),
            }

            output = await test_agent.execute(agent_input)

            assert output.status == AgentStatus.FAILED
            assert "LLM error" in output.error
