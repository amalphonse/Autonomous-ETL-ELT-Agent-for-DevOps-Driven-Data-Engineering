"""Coding Agent implementation for generating PySpark code and Pydantic models."""

import json
import logging
import re
from typing import Optional, Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

from src.config import get_settings
from src.types import Agent, AgentType, AgentStatus, AgentInput, AgentOutput
from src.agents.task_agent.schemas import ParsedRequirements
from src.agents.coding_agent.schemas import (
    CodingAgentInput,
    CodingAgentOutput,
    GeneratedCode,
    PydanticModel,
    CodeFile,
    CodeConfiguration,
)

logger = logging.getLogger(__name__)


class CodingAgent(Agent):
    """Coding Agent: Generates PySpark code and Pydantic models from requirements.

    This agent takes structured requirements from the Task Agent and generates:
    - Production-ready PySpark code using Delta Lake patterns
    - Pydantic models for input/output schema validation
    - Supporting utilities and configurations
    - Modular, testable code structure
    """

    def __init__(self):
        """Initialize the Coding Agent with LangChain components."""
        super().__init__(AgentType.CODING)
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """Set up LangChain prompts for code generation."""
        self.code_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert PySpark developer. Your task is to generate production-ready
PySpark code based on transformation requirements.

## EXAMPLE OUTPUT:

For requirements like "Load orders and products, join on product_id, aggregate by product_category":

{{
  "main_pipeline_code": "from pyspark.sql import SparkSession\\nfrom pyspark.sql.functions import col, count, sum as spark_sum\\n\\ndef main():\\n    spark = SparkSession.builder.appName('OrderAnalysis').getOrCreate()\\n    orders = spark.read.delta('s3://data/orders')\\n    products = spark.read.delta('s3://data/products')\\n    joined = orders.join(products, on='product_id')\\n    result = joined.groupBy('product_category').agg(count('order_id').alias('order_count'), spark_sum('amount').alias('total_revenue'))\\n    result.write.delta('s3://output/results', mode='overwrite')",
  "input_schema_model": {{
    "model_name": "OrderInput",
    "module_name": "models.input_schema",
    "code": "from pydantic import BaseModel, Field\\nfrom typing import Optional\\nfrom datetime import datetime\\n\\nclass OrderInput(BaseModel):\\n    order_id: str = Field(..., description='Unique order identifier')\\n    product_id: str = Field(..., description='Product identifier')\\n    amount: float = Field(..., description='Order amount')\\n    order_date: datetime = Field(..., description='Order date')",
    "fields": [
      {{"name": "order_id", "type": "str", "description": "Unique order identifier"}},
      {{"name": "amount", "type": "float", "description": "Order amount"}}
    ]
  }},
  "output_schema_model": {{
    "model_name": "OrderAnalysisOutput",
    "module_name": "models.output_schema",
    "code": "from pydantic import BaseModel, Field\\n\\nclass OrderAnalysisOutput(BaseModel):\\n    product_category: str = Field(..., description='Product category')\\n    order_count: int = Field(..., description='Total number of orders')\\n    total_revenue: float = Field(..., description='Total revenue for category')",
    "fields": [
      {{"name": "product_category", "type": "str", "description": "Product category"}},
      {{"name": "order_count", "type": "int", "description": "Total number of orders"}}
    ]
  }}
}}

---

## ACTUAL REQUIREMENTS TO IMPLEMENT:

Requirements:
{requirements}

Config:
- Spark Version: {spark_version}
- Use Delta Lake: {use_delta_lake}
- Include Type Hints: {include_type_hints}
- Include Docstrings: {include_docstrings}
- Include Logging: {include_logging}
- Include Error Handling: {include_error_handling}

Generate the following JSON response with complete code:
{{
  "main_pipeline_code": "Full PySpark pipeline implementation as a string",
  "input_schema_model": {{
    "model_name": "InputSchema",
    "module_name": "models.input_schema",
    "description": "Input data validation model",
    "code": "Complete Pydantic model Python code as a string",
    "fields": [
      {{"name": "field_name", "type": "field_type", "description": "field description"}}
    ]
  }},
  "output_schema_model": {{
    "model_name": "OutputSchema",
    "module_name": "models.output_schema",
    "description": "Output data validation model",
    "code": "Complete Pydantic model Python code as a string",
    "fields": [
      {{"name": "field_name", "type": "field_type", "description": "field description"}}
    ]
  }},
  "additional_models": [],
  "additional_files": [
    {{
      "file_name": "utils.py",
      "file_path": "src/utils.py",
      "description": "Utility functions and helpers",
      "code": "Python code as a string",
      "imports": ["from pyspark.sql import SparkSession"]
    }}
  ],
  "imports": ["from pyspark.sql import SparkSession", ...]
}}

Requirements for the code:
1. Use PySpark APIs (DataFrame, SQL)
2. Implement each transformation step as a function
3. Use Delta Lake format for reads/writes
4. Include comprehensive error handling
5. Add logging for debugging
6. Use type hints for all functions
7. Include docstrings for all functions and classes
8. Follow PEP 8 style guidelines
9. Make code modular and reusable
10. Include proper schema validation

The generated code should be production-ready and fully functional."""
        )

        self.pydantic_prompt = ChatPromptTemplate.from_template(
            """You are an expert Python developer specializing in data validation.
Generate complete, valid Pydantic v2 model code based on this schema:

Schema:
{schema}

The generated code should:
1. Be valid, importable Python code
2. Use Pydantic v2 BaseModel and Field
3. Include type hints
4. Include field descriptions
5. Include validators if needed
6. Have a proper docstring

Return ONLY the Python code as a string, no markdown wrapping."""
        )

    async def execute(self, agent_input: AgentInput) -> AgentOutput:
        """Execute the Coding Agent to generate code from requirements.

        Args:
            agent_input: Should be CodingAgentInput with parsed requirements.

        Returns:
            AgentOutput with generated code and quality score.
        """
        try:
            # Validate input
            if not self.validate_input(agent_input):
                return self._error_output("Invalid input format. Expected CodingAgentInput.")

            # Convert to dict if needed and then to CodingAgentInput
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()
            
            coding_input = CodingAgentInput(**agent_input_dict)
            config = coding_input.config

            logger.info(
                f"Coding Agent processing requirements for story: {coding_input.requirements.story_id}"
            )

            # Step 1: Prepare requirements and configuration
            requirements_json = self._format_requirements(coding_input.requirements)

            # Step 2: Generate main pipeline code
            logger.debug("Generating main pipeline code...")
            pipeline_response = self._generate_pipeline_code(
                requirements_json, config
            )

            # Step 3: Parse and validate generated code
            logger.debug("Parsing generated code...")
            generated_code = self._parse_code_response(pipeline_response)

            # Step 4: Calculate quality score
            quality_score = self._calculate_quality_score(
                coding_input.requirements, generated_code
            )

            # Step 5: Create output
            coding_output = CodingAgentOutput(
                generated_code=generated_code,
                code_quality_score=quality_score,
                generation_notes=None,
                raw_generation=pipeline_response,
            )

            logger.info(
                f"Coding Agent completed with quality score: {quality_score:.2f}"
            )

            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.SUCCESS,
                data=coding_output.model_dump(),
            )

        except Exception as e:
            logger.error(f"Coding Agent execution failed: {str(e)}")
            return self._error_output(f"Coding Agent failed: {str(e)}")

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate that the input contains valid requirements.

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

            # Check for requirements
            if "requirements" not in agent_input_dict:
                logger.warning("Missing 'requirements' in agent input")
                return False

            # Try to validate as ParsedRequirements
            ParsedRequirements(**agent_input_dict["requirements"])
            return True

        except Exception as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return False

    def _format_requirements(self, requirements: ParsedRequirements) -> str:
        """Format requirements as JSON string for LLM.

        Args:
            requirements: The ParsedRequirements object.

        Returns:
            Formatted JSON string.
        """
        return json.dumps(requirements.model_dump(), indent=2)

    def _generate_pipeline_code(
        self, requirements_json: str, config: CodeConfiguration
    ) -> Dict[str, Any]:
        """Generate main pipeline code using LLM.

        Args:
            requirements_json: Formatted requirements.
            config: Code generation configuration.

        Returns:
            Generated code data.
        """
        chain = self.code_generation_prompt | self.llm

        response = chain.invoke(
            {
                "requirements": requirements_json,
                "spark_version": config.target_spark_version,
                "use_delta_lake": config.use_delta_lake,
                "include_type_hints": config.enable_type_hints,
                "include_docstrings": config.include_docstrings,
                "include_logging": config.include_logging,
                "include_error_handling": config.include_error_handling,
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

    def _parse_code_response(self, response_data: Dict[str, Any]) -> GeneratedCode:
        """Parse LLM response into GeneratedCode object.

        Args:
            response_data: Parsed JSON response from LLM.

        Returns:
            GeneratedCode object with validated data.
        """
        # Parse input schema model
        input_schema = self._create_pydantic_model(
            response_data.get("input_schema_model", {})
        )

        # Parse output schema model
        output_schema = self._create_pydantic_model(
            response_data.get("output_schema_model", {})
        )

        # Parse additional models
        additional_models = [
            self._create_pydantic_model(model)
            for model in response_data.get("additional_models", [])
        ]

        # Parse additional files
        additional_files = [
            CodeFile(**file) for file in response_data.get("additional_files", [])
        ]

        return GeneratedCode(
            main_pipeline_code=response_data.get("main_pipeline_code", ""),
            input_schema_model=input_schema,
            output_schema_model=output_schema,
            additional_models=additional_models,
            additional_files=additional_files,
            imports=response_data.get("imports", []),
        )

    def _create_pydantic_model(self, model_data: Dict[str, Any]) -> PydanticModel:
        """Create a PydanticModel from response data.

        Args:
            model_data: Model data from LLM response.

        Returns:
            PydanticModel object.
        """
        return PydanticModel(
            model_name=model_data.get("model_name", ""),
            module_name=model_data.get("module_name", ""),
            description=model_data.get("description", ""),
            code=model_data.get("code", ""),
            fields=model_data.get("fields", []),
        )

    def _calculate_quality_score(
        self, requirements: ParsedRequirements, generated_code: GeneratedCode
    ) -> float:
        """Calculate quality score for generated code.

        Args:
            requirements: Original requirements.
            generated_code: Generated code.

        Returns:
            Quality score between 0 and 1.
        """
        score = 0.7  # Base score

        # Check code completeness
        if generated_code.main_pipeline_code and len(generated_code.main_pipeline_code) > 500:
            score += 0.1
        if generated_code.input_schema_model.code:
            score += 0.05
        if generated_code.output_schema_model.code:
            score += 0.05
        if generated_code.imports:
            score += 0.03

        # Check if all transformations are likely covered
        if len(requirements.transformation_steps) > 0:
            # Check if code mentions key transformation types
            code_text = (
                generated_code.main_pipeline_code
                + " ".join([f.code for f in generated_code.additional_files])
            ).lower()

            transformation_keywords = {
                "filter": "where",
                "join": "join",
                "aggregate": "groupby|agg",
                "window": "window",
                "union": "union|unionbyname",
            }

            for trans_type, keywords in transformation_keywords.items():
                if any(re.search(keyword, code_text) for keyword in keywords.split("|")):
                    score += 0.02

        # Cap at 1.0
        return min(score, 1.0)

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
