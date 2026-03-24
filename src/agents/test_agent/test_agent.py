"""Test Agent implementation for generating pytest suites and validating code."""

import json
import logging
import re
from typing import Optional, Dict, Any, List
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.config import get_settings
from src.types import Agent, AgentType, AgentStatus, AgentInput, AgentOutput
from src.agents.coding_agent.schemas import GeneratedCode
from src.agents.task_agent.schemas import ParsedRequirements
from src.agents.test_agent.schemas import (
    TestAgentInput,
    TestAgentOutput,
    GeneratedTests,
    TestCase,
    ValidationSuite,
    TestCoverageMetrics,
)

logger = logging.getLogger(__name__)


class TestAgent(Agent):
    """Test Agent: Generates comprehensive pytest suites and validates code.

    This agent takes generated code from the Coding Agent and creates:
    - Unit tests for individual functions
    - Integration tests for pipeline flows
    - Data quality validation tests
    - Performance tests (optional)
    - Coverage metrics and quality scores
    """

    def __init__(self):
        """Initialize the Test Agent with LangChain components."""
        super().__init__(AgentType.TEST)
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """Set up LangChain prompts for test generation."""
        self.test_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert pytest developer. Your task is to generate comprehensive,
production-ready test suites for PySpark pipelines.

Generated Code:
{generated_code}

Requirements:
{requirements}

Configuration:
- Include Integration Tests: {include_integration_tests}
- Include Performance Tests: {include_performance_tests}
- Mock External Dependencies: {mock_external_dependencies}
- Target Coverage: {target_coverage}%

Generate a comprehensive pytest suite as valid JSON with the following structure:
{{
  "test_file_name": "test_pipeline.py",
  "test_file_path": "tests/test_pipeline.py",
  "test_code": "Complete test file Python code as a string",
  "test_cases": [
    {{
      "test_name": "test_function_name",
      "test_type": "unit|integration|validation|performance",
      "description": "what this test validates",
      "test_code": "def test_function_name(): ...",
      "input_data": {{}},
      "expected_output": {{}},
      "assertions": ["assertion_expression"]
    }}
  ],
  "validation_suites": [
    {{
      "rule_id": "val_1",
      "rule_type": "null_check|schema|uniqueness|range|pattern|custom",
      "column": "column_name_or_null",
      "test_code": "def test_validation_rule(): ...",
      "description": "what this validates"
    }}
  ],
  "imports": ["import pytest", "from pyspark.sql import SparkSession"],
  "fixtures": {{
    "spark": "def spark(): return SparkSession.builder.appName('test').getOrCreate()",
    "sample_data": "def sample_data(spark): ..."
  }},
  "conftest_code": "Optional conftest.py content if needed"
}}

Requirements for the tests:
1. Include unit tests for each function
2. Include integration tests for pipeline flows
3. Include data quality validation tests based on requirements
4. Use pytest fixtures for common setup
5. Mock PySpark where appropriate for unit tests
6. Use real Spark for integration tests
7. Include edge case and error handling tests
8. Use @pytest.mark decorators for categorization
9. Include parametrized tests for multiple scenarios
10. Add docstrings to all test functions
11. Ensure tests are independent and can run in any order
12. Include performance assertions if performance tests enabled

The generated tests should be production-ready, comprehensive, and achieve at least
the target coverage percentage."""
        )

        self.validation_prompt = ChatPromptTemplate.from_template(
            """You are an expert data engineer. Based on these data quality rules,
generate pytest assertions that validate the data:

Data Quality Rules:
{quality_rules}

Generate a JSON array of validation tests:
[
  {{
    "rule_id": "rule_id",
    "rule_type": "null_check|schema|uniqueness|range|pattern|custom",
    "column": "column_name",
    "test_code": "pytest assertion code",
    "description": "what is validated"
  }}
]

Make sure each test:
1. Is a valid pytest assertion
2. Tests the specific data quality rule
3. Has clear error messages
4. Can be parameterized if needed"""
        )

    async def execute(self, agent_input: AgentInput) -> AgentOutput:
        """Execute the Test Agent to generate tests from code.

        Args:
            agent_input: Should be TestAgentInput with generated code.

        Returns:
            AgentOutput with generated tests and quality metrics.
        """
        try:
            # Validate input
            if not self.validate_input(agent_input):
                return self._error_output("Invalid input format. Expected TestAgentInput.")

            # Convert to dict if needed and then to TestAgentInput
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()
            
            test_input = TestAgentInput(**agent_input_dict)

            logger.info(
                f"Test Agent processing code for story: {test_input.requirements.story_id}"
            )

            # Step 1: Format generated code for LLM
            code_summary = self._format_generated_code(test_input.generated_code)
            requirements_json = test_input.requirements.model_dump()

            # Step 2: Generate test suite
            logger.debug("Generating test suite...")
            test_response = self._generate_test_suite(
                code_summary, requirements_json, test_input
            )

            # Step 3: Parse and validate generated tests
            logger.debug("Parsing generated tests...")
            generated_tests = self._parse_test_response(test_response)

            # Step 4: Generate validation tests if quality rules exist
            if test_input.requirements.quality_rules:
                logger.debug("Generating validation tests...")
                validation_tests = self._generate_validation_tests(
                    test_input.requirements.quality_rules
                )
                generated_tests.validation_suites.extend(validation_tests)

            # Step 5: Calculate coverage metrics
            coverage_metrics = self._calculate_coverage_metrics(
                generated_tests, test_input.requirements
            )

            # Step 6: Calculate quality score
            quality_score = self._calculate_quality_score(
                generated_tests, coverage_metrics, test_input.target_coverage
            )

            # Step 7: Create output
            test_output = TestAgentOutput(
                generated_tests=generated_tests,
                coverage_metrics=coverage_metrics,
                test_quality_score=quality_score,
                validation_notes=None,
                raw_generation=test_response,
            )

            logger.info(f"Test Agent completed with quality score: {quality_score:.2f}")

            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.SUCCESS,
                data=test_output.model_dump(),
            )

        except Exception as e:
            logger.error(f"Test Agent execution failed: {str(e)}", exc_info=True)
            return self._error_output(f"Test Agent failed: {str(e)}")

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate that the input contains valid generated code.

        Args:
            agent_input: Input to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()

            # Check for required fields
            if "generated_code" not in agent_input_dict:
                logger.warning("Missing 'generated_code' in agent input")
                return False

            if "requirements" not in agent_input_dict:
                logger.warning("Missing 'requirements' in agent input")
                return False

            # Try to validate both
            GeneratedCode(**agent_input_dict["generated_code"])
            ParsedRequirements(**agent_input_dict["requirements"])
            return True

        except Exception as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return False

    def _format_generated_code(self, generated_code: GeneratedCode) -> str:
        """Format generated code for LLM processing.

        Args:
            generated_code: The GeneratedCode object.

        Returns:
            Formatted string summary of the code.
        """
        summary = f"""
Main Pipeline Code (first 500 chars):
{generated_code.main_pipeline_code[:500]}...

Input Schema Model:
- Name: {generated_code.input_schema_model.model_name}
- Code: {generated_code.input_schema_model.code[:300]}...

Output Schema Model:
- Name: {generated_code.output_schema_model.model_name}
- Code: {generated_code.output_schema_model.code[:300]}...

Additional Files: {len(generated_code.additional_files)}
Imports: {', '.join(generated_code.imports[:10])}
"""
        return summary

    def _generate_test_suite(
        self,
        code_summary: str,
        requirements_json: Dict[str, Any],
        test_input: TestAgentInput,
    ) -> Dict[str, Any]:
        """Generate test suite using LLM.

        Args:
            code_summary: Summary of generated code.
            requirements_json: Requirements as dict.
            test_input: Test agent input configuration.

        Returns:
            Generated test data.
        """
        chain = self.test_generation_prompt | self.llm

        response = chain.invoke(
            {
                "generated_code": code_summary,
                "requirements": json.dumps(requirements_json, indent=2),
                "include_integration_tests": test_input.include_integration_tests,
                "include_performance_tests": test_input.include_performance_tests,
                "mock_external_dependencies": test_input.mock_external_dependencies,
                "target_coverage": int(test_input.target_coverage * 100),
            }
        )

        return json.loads(self._extract_json(response.content))

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling markdown wrapping.

        Args:
            text: Text containing JSON.

        Returns:
            Clean JSON string.
        """
        # Try direct JSON parse
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Try to find JSON in text
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from response: {text}")

    def _parse_test_response(self, response_data: Dict[str, Any]) -> GeneratedTests:
        """Parse LLM response into GeneratedTests object.

        Args:
            response_data: Parsed JSON response from LLM.

        Returns:
            GeneratedTests object with validated data.
        """
        # Parse test cases
        test_cases = [
            TestCase(**case) for case in response_data.get("test_cases", [])
        ]

        # Parse validation suites
        validation_suites = [
            ValidationSuite(**suite)
            for suite in response_data.get("validation_suites", [])
        ]

        return GeneratedTests(
            test_file_name=response_data.get("test_file_name", "test_pipeline.py"),
            test_file_path=response_data.get("test_file_path", "tests/test_pipeline.py"),
            test_code=response_data.get("test_code", ""),
            test_cases=test_cases,
            validation_suites=validation_suites,
            imports=response_data.get("imports", []),
            fixtures=response_data.get("fixtures", {}),
            conftest_code=response_data.get("conftest_code"),
        )

    def _generate_validation_tests(self, quality_rules: List) -> List[ValidationSuite]:
        """Generate validation tests from quality rules.

        Args:
            quality_rules: List of DataQualityRule objects.

        Returns:
            List of ValidationSuite objects.
        """
        validation_suites = []

        # Convert quality rules to dict
        rules_dict = [rule.model_dump() for rule in quality_rules]

        try:
            chain = self.validation_prompt | self.llm
            response = chain.invoke(
                {"quality_rules": json.dumps(rules_dict, indent=2)}
            )

            validation_data = json.loads(self._extract_json(response.content))

            for validation in validation_data:
                validation_suites.append(ValidationSuite(**validation))
        except Exception as e:
            logger.warning(f"Failed to generate validation tests: {str(e)}")

        return validation_suites

    def _calculate_coverage_metrics(
        self,
        generated_tests: GeneratedTests,
        requirements: ParsedRequirements,
    ) -> TestCoverageMetrics:
        """Calculate code coverage and quality metrics.

        Args:
            generated_tests: Generated test suite.
            requirements: Original requirements.

        Returns:
            TestCoverageMetrics object.
        """
        # Count test types
        unit_tests = sum(
            1 for tc in generated_tests.test_cases if tc.test_type == "unit"
        )
        integration_tests = sum(
            1 for tc in generated_tests.test_cases if tc.test_type == "integration"
        )
        validation_tests = len(generated_tests.validation_suites)

        # Estimate coverage based on test count and transformation steps
        num_transformations = len(requirements.transformation_steps)
        estimated_lines_covered = (unit_tests + integration_tests) * 50

        # Calculate percentages (estimation)
        line_coverage = min(
            0.95, 0.3 + (len(generated_tests.test_cases) * 0.08)
        )  # 30-95%
        branch_coverage = line_coverage * 0.85  # Branches are harder to cover
        function_coverage = min(1.0, 0.5 + (num_transformations * 0.1))

        # Count assertions
        total_assertions = sum(
            len(tc.assertions) for tc in generated_tests.test_cases
        ) + len(generated_tests.validation_suites)

        # Estimate quality score
        estimated_quality = min(
            1.0,
            0.5
            + (len(generated_tests.test_cases) * 0.05)
            + (validation_tests * 0.03)
            + (line_coverage * 0.2),
        )

        return TestCoverageMetrics(
            line_coverage_percent=line_coverage,
            branch_coverage_percent=branch_coverage,
            function_coverage_percent=function_coverage,
            test_count=len(generated_tests.test_cases),
            assertions_count=max(1, total_assertions),
            estimated_quality_score=estimated_quality,
        )

    def _calculate_quality_score(
        self,
        generated_tests: GeneratedTests,
        coverage_metrics: TestCoverageMetrics,
        target_coverage: float,
    ) -> float:
        """Calculate overall test quality score.

        Args:
            generated_tests: Generated test suite.
            coverage_metrics: Coverage metrics.
            target_coverage: Target coverage percentage.

        Returns:
            Quality score between 0 and 1.
        """
        score = 0.5  # Base score

        # Coverage alignment
        coverage_achieved = coverage_metrics.line_coverage_percent
        if coverage_achieved >= target_coverage:
            score += 0.3
        else:
            score += (coverage_achieved / target_coverage) * 0.3

        # Test count and variety
        test_count = len(generated_tests.test_cases)
        if test_count >= 10:
            score += 0.15
        elif test_count >= 5:
            score += 0.1
        else:
            score += test_count * 0.015

        # Validation tests
        validation_count = len(generated_tests.validation_suites)
        if validation_count >= 5:
            score += 0.1
        else:
            score += validation_count * 0.02

        # Assertions
        if coverage_metrics.assertions_count >= 20:
            score += 0.05
        else:
            score += (coverage_metrics.assertions_count / 20) * 0.05

        # Test code quality (has fixtures, imports, etc.)
        if generated_tests.fixtures:
            score += 0.05
        if generated_tests.conftest_code:
            score += 0.05

        return min(1.0, score)

    def _error_output(self, error_message: str) -> AgentOutput:
        """Create an error output.

        Args:
            error_message: Error message.

        Returns:
            AgentOutput with error status.
        """
        return AgentOutput(
            agent_type=self.agent_type,
            status=AgentStatus.FAILED,
            error=error_message,
        )
