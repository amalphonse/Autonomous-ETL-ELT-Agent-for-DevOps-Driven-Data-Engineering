"""Schemas and data models for the Test Agent.

The Test Agent is responsible for generating comprehensive pytest suites
and validating generated code from the Coding Agent.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
from src.agents.coding_agent.schemas import GeneratedCode
from src.agents.task_agent.schemas import ParsedRequirements


class TestCase(BaseModel):
    """A single test case in the generated test suite."""

    test_name: str = Field(..., description="Name of the test function")
    test_type: Literal["unit", "integration", "validation", "performance"] = Field(
        ..., description="Type of test"
    )
    description: str = Field(..., description="What this test validates")
    test_code: str = Field(..., description="The actual test function code")
    input_data: Optional[Dict[str, Any]] = Field(
        None, description="Sample input data for this test"
    )
    expected_output: Optional[Dict[str, Any]] = Field(
        None, description="Expected output for this test"
    )
    assertions: List[str] = Field(
        default_factory=list, description="List of assertions"
    )


class ValidationSuite(BaseModel):
    """Data quality and schema validation tests."""

    rule_id: str = Field(..., description="Unique validator ID")
    rule_type: Literal[
        "null_check", "schema", "uniqueness", "range", "pattern", "custom"
    ] = Field(..., description="Type of validation")
    column: Optional[str] = Field(None, description="Column being validated")
    test_code: str = Field(..., description="Pytest compatible test code")
    description: str = Field(..., description="What this validation checks")


class GeneratedTests(BaseModel):
    """Complete generated test suite."""

    test_file_name: str = Field(
        default="test_pipeline.py", description="Name of the test file"
    )
    test_file_path: str = Field(
        default="tests/test_pipeline.py", description="Relative path for test file"
    )
    test_code: str = Field(..., description="Complete test file code")
    test_cases: List[TestCase] = Field(
        ..., description="Individual test cases"
    )
    validation_suites: List[ValidationSuite] = Field(
        default_factory=list, description="Data quality validation tests"
    )
    imports: List[str] = Field(
        default_factory=list, description="Required imports for tests"
    )
    fixtures: Dict[str, str] = Field(
        default_factory=dict, description="Pytest fixtures (name -> code)"
    )
    conftest_code: Optional[str] = Field(
        None, description="Content for conftest.py if needed"
    )


class TestCoverageMetrics(BaseModel):
    """Code coverage and quality metrics."""

    line_coverage_percent: float = Field(..., description="Percentage of lines covered")
    branch_coverage_percent: float = Field(
        ..., description="Percentage of branches covered"
    )
    function_coverage_percent: float = Field(
        ..., description="Percentage of functions covered"
    )
    test_count: int = Field(..., description="Number of test cases generated")
    assertions_count: int = Field(..., description="Total number of assertions")
    estimated_quality_score: float = Field(
        ..., description="Estimated code quality score (0-1)"
    )


class TestAgentInput(BaseModel):
    """Input to the Test Agent."""

    generated_code: GeneratedCode = Field(
        ..., description="Generated code from Coding Agent"
    )
    requirements: ParsedRequirements = Field(
        ..., description="Original requirements from Task Agent"
    )
    include_integration_tests: bool = Field(
        default=True, description="Whether to generate integration tests"
    )
    include_performance_tests: bool = Field(
        default=False, description="Whether to generate performance tests"
    )
    mock_external_dependencies: bool = Field(
        default=True, description="Whether to mock external dependencies"
    )
    target_coverage: float = Field(
        default=0.85, description="Target code coverage percentage"
    )


class TestAgentOutput(BaseModel):
    """Output from the Test Agent."""

    generated_tests: GeneratedTests = Field(
        ..., description="Generated test suite"
    )
    coverage_metrics: TestCoverageMetrics = Field(
        ..., description="Code coverage and quality metrics"
    )
    test_quality_score: float = Field(
        ..., description="Quality score of generated tests (0-1)"
    )
    validation_notes: Optional[str] = Field(
        None, description="Notes or warnings about test generation"
    )
    raw_generation: Optional[Dict[str, Any]] = Field(
        None, description="Raw LLM generation output for debugging"
    )
