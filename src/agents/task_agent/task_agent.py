"""Task Agent implementation for parsing user stories and extracting requirements."""

import json
import logging
from typing import Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

from src.config import get_settings
from src.types import Agent, AgentType, AgentStatus, AgentInput, AgentOutput
from src.agents.task_agent.schemas import (
    TaskAgentInput,
    TaskAgentOutput,
    UserStory,
    ParsedRequirements,
    TransformationStep,
    TransformationType,
    DataSource,
    DataType,
    ColumnDefinition,
)

logger = logging.getLogger(__name__)


class TaskAgent(Agent):
    """Task Agent: Parses user stories and extracts transformation requirements.

    This agent takes raw user stories (in JSON/YAML/text format) and uses NLP
    to extract:
    - Input data sources and schemas
    - Output schema
    - Transformation steps (filters, joins, aggregations, etc.)
    - Data quality rules
    - Scheduling and dependency information
    """

    def __init__(self):
        """Initialize the Task Agent with LangChain components."""
        super().__init__(AgentType.TASK)
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """Set up LangChain prompts for requirement parsing."""
        self.parsing_prompt = ChatPromptTemplate.from_template(
            """You are an expert Data Engineer AI assistant. Your task is to analyze a user story
and extract detailed ETL/ELT transformation requirements.

## EXAMPLES:

### Example 1: Customer RFM Analysis
**Input Story:**
"Load customer transactions from Salesforce, group by customer_id to calculate recency (days since last purchase), 
frequency (total transactions), and monetary value (total spent). Filter for customers with recency < 30 days and 
frequency > 5. Write to Snowflake customer_rfm table."

**Expected Output:**
{{
  "title": "Customer RFM Analysis",
  "input_sources": [{{"name": "salesforce_transactions", "location": "salesforce.public.transactions", 
    "format": "sql", "schema": [{{"name": "transaction_id", "data_type": "string"}}, 
    {{"name": "customer_id", "data_type": "string"}}, {{"name": "amount", "data_type": "float"}}, 
    {{"name": "transaction_date", "data_type": "timestamp"}}]}}],
  "transformation_steps": [
    {{"step_id": "step-1", "transformation_type": "aggregate", "input_table": "transactions",
     "group_by": ["customer_id"], 
     "aggregations": [{{"function": "MAX", "column": "transaction_date", "alias": "last_purchase_date"}},
                      {{"function": "COUNT", "column": "transaction_id", "alias": "purchase_frequency"}},
                      {{"function": "SUM", "column": "amount", "alias": "total_spent"}}]}},
    {{"step_id": "step-2", "transformation_type": "filter", "input_table": "step-1",
     "conditions": [{{"column": "purchase_frequency", "operator": ">", "value": 5}}]}}],
  "data_quality_rules": ["customer_id NOT NULL", "total_spent > 0"],
  "output_location": "snowflake.analytics.customer_rfm"
}}

### Example 2: Product Orders Aggregation
**Input Story:**
"Join orders with product data, filter completed orders from last 12 months, aggregate by product_category
to get total revenue and order count."

**Expected Output:**
{{
  "title": "Product Orders Aggregation",
  "transformation_steps": [
    {{"step_id": "step-1", "transformation_type": "filter", 
     "conditions": [{{"column": "order_status", "operator": "==", "value": "completed"}},
                    {{"column": "order_date", "operator": ">", "value": "last 12 months"}}]}},
    {{"step_id": "step-2", "transformation_type": "join", "left_table": "orders", "right_table": "products",
     "join_keys": [{{"left": "product_id", "right": "product_id"}}], "join_type": "inner"}},
    {{"step_id": "step-3", "transformation_type": "aggregate", "group_by": ["product_category"],
     "aggregations": [{{"function": "SUM", "column": "order_amount", "alias": "total_revenue"}},
                      {{"function": "COUNT", "column": "order_id", "alias": "order_count"}}]}}
  ]
}}

---

## ACTUAL USER STORY TO ANALYZE:

User Story:
{user_story}

Extract and structure the following information:
1. Input data sources (names, locations, formats, schemas)
2. Transformation steps (filters, joins, aggregations, windowing, deduplication, etc.)
3. Output schema and location
4. Data quality validation rules
5. Execution frequency and SLA
6. Dependencies on other pipelines

Return a valid JSON object with the following structure:
{{
  "story_id": "unique-id",
  "title": "short-title",
  "description": "detailed-description",
  "input_sources": [
    {{
      "name": "source-name",
      "location": "path/or/table",
      "format": "csv|parquet|json|delta|sql",
      "schema": [
        {{
          "name": "column-name",
          "data_type": "string|integer|float|double|boolean|date|timestamp|array|struct|decimal",
          "nullable": true,
          "description": "column-description"
        }}
      ],
      "is_streaming": false
    }}
  ],
  "output_schema": [
    {{
      "name": "output-column",
      "data_type": "string|integer|float|double|boolean|date|timestamp|array|struct|decimal",
      "nullable": true,
      "description": "output description"
    }}
  ],
  "output_location": "output-path-or-table",
  "transformation_steps": [
    {{
      "step_id": "step-1",
      "transformation_type": "filter|join|aggregate|window|union|group_by|pivot|flatten|dedup|custom",
      "description": "what-this-step-does",
      "inputs": ["input-column-names"],
      "outputs": ["output-column-names"],
      "parameters": {{}},
      "sql_snippet": null
    }}
  ],
  "quality_rules": [
    {{
      "rule_id": "rule-1",
      "rule_type": "null_check|schema|uniqueness|range|pattern|custom",
      "column": "column-name-or-null",
      "description": "what-is-being-validated",
      "parameters": {{}}
    }}
  ],
  "frequency": "once|hourly|daily|weekly|monthly",
  "sla_hours": null,
  "dependencies": [],
  "metadata": {{}}
}}

Ensure all values are valid and complete. If a field is missing in the user story, 
make a reasonable inference based on common data engineering patterns."""
        )

    async def execute(self, agent_input: AgentInput) -> AgentOutput:
        """Execute the Task Agent to parse a user story.

        Args:
            agent_input: Should be TaskAgentInput with a user story.

        Returns:
            AgentOutput with parsed requirements and confidence score.
        """
        try:
            # Validate input
            if not self.validate_input(agent_input):
                return self._error_output(
                    "Invalid input format. Expected TaskAgentInput."
                )

            # Handle both dict and object inputs
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()
            
            task_input = TaskAgentInput(**agent_input_dict)

            logger.info(
                f"Task Agent processing story: {task_input.user_story.request_id}"
            )

            # Step 1: Format the user story for LLM
            user_story_text = self._format_user_story(task_input.user_story)

            # Step 2: Call LLM to parse requirements
            logger.debug("Invoking LLM for requirement parsing...")
            chain = self.parsing_prompt | self.llm
            response = chain.invoke({"user_story": user_story_text})

            # Step 3: Parse the LLM response
            logger.debug("Parsing LLM response...")
            parsed_response = self._parse_llm_response(response.content)

            # Step 4: Validate and create ParsedRequirements object
            logger.debug("Validating parsed requirements...")
            requirements = ParsedRequirements(**parsed_response)

            # Step 5: Calculate confidence score
            confidence_score = self._calculate_confidence(
                task_input.user_story, requirements
            )

            # Create output
            task_output = TaskAgentOutput(
                requirements=requirements,
                confidence_score=confidence_score,
                parsing_notes=None,
                raw_analysis=parsed_response,
            )

            logger.info(
                f"Task Agent completed with confidence: {confidence_score:.2f}"
            )

            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.SUCCESS,
                data=task_output.dict(),
            )

        except Exception as e:
            logger.error(f"Task Agent execution failed: {str(e)}")
            return self._error_output(f"Task Agent failed: {str(e)}")

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate that the input contains a valid user story.

        Args:
            agent_input: Input to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            if not isinstance(agent_input, dict):
                agent_input = agent_input.dict()

            # Check for user_story key
            if "user_story" not in agent_input:
                logger.warning("Missing 'user_story' in agent input")
                return False

            user_story_data = agent_input["user_story"]

            # Try to validate as UserStory
            UserStory(**user_story_data)
            return True

        except Exception as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return False

    def _format_user_story(self, user_story: UserStory) -> str:
        """Format user story for LLM processing.

        Args:
            user_story: The UserStory object to format.

        Returns:
            Formatted string for LLM.
        """
        formatted = f"""
Request ID: {user_story.request_id}
User ID: {user_story.user_id}

Story (Format: {user_story.format}):
{user_story.story}
"""
        if user_story.attachments:
            formatted += "\n\nAttachments:\n"
            formatted += json.dumps(user_story.attachments, indent=2)

        return formatted

    def _parse_llm_response(self, response_text: str) -> dict:
        """Parse and extract JSON from LLM response.

        Args:
            response_text: Raw LLM response text.

        Returns:
            Parsed dictionary.
        """
        # Try to extract JSON from response
        try:
            # First, try direct JSON parse
            return json.loads(response_text)
        except json.JSONDecodeError:
            # If that fails, try to find JSON in the response
            start_idx = response_text.find("{")
            end_idx = response_text.rfind("}") + 1
            if start_idx != -1 and end_idx > start_idx:
                try:
                    return json.loads(response_text[start_idx:end_idx])
                except json.JSONDecodeError:
                    pass

        raise ValueError(f"Could not parse JSON from LLM response: {response_text}")

    def _calculate_confidence(
        self, user_story: UserStory, requirements: ParsedRequirements
    ) -> float:
        """Calculate confidence score for the parsing.

        Args:
            user_story: Original user story.
            requirements: Parsed requirements.

        Returns:
            Confidence score between 0 and 1.
        """
        score = 0.8  # Base score

        # Check if we have all key components
        if requirements.input_sources:
            score += 0.05
        if requirements.transformation_steps:
            score += 0.05
        if requirements.output_schema:
            score += 0.05
        if requirements.quality_rules:
            score += 0.03

        # Check input quality
        if len(user_story.story) > 500:  # Longer stories often have more detail
            score += 0.02

        # Cap at 1.0
        return min(score, 1.0)

    def _error_output(self, error_message: str) -> AgentOutput:
        """Create an error output.

        Args:
            error_message: The error message.

        Returns:
            AgentOutput with error status.
        """
        return AgentOutput(
            agent_type=self.agent_type,
            status=AgentStatus.FAILED,
            error=error_message,
        )
