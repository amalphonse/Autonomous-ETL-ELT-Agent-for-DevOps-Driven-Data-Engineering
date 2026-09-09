"""Coding Agent implementation for generating PySpark code and Pydantic models."""

import json
import logging
import re
from typing import Optional, Dict, Any, List
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
    OptimizationAnalysis,
    PartitioningRecommendation,
    CachingRecommendation,
    JoinOptimization,
    OptimizationRule,
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

            # Step 5: Analyze optimizations
            logger.debug("Analyzing pipeline optimizations...")
            optimization_analysis = self._analyze_optimizations(
                coding_input.requirements, generated_code
            )

            # Step 6: Add optimization comments to code
            optimized_code = self._add_optimization_comments(
                generated_code, optimization_analysis
            )

            # Step 7: Create output
            coding_output = CodingAgentOutput(
                generated_code=optimized_code,
                code_quality_score=quality_score,
                optimization_analysis=optimization_analysis,
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

    def _analyze_optimizations(
        self, requirements: ParsedRequirements, generated_code: GeneratedCode
    ) -> OptimizationAnalysis:
        """Analyze code for optimization opportunities.

        Args:
            requirements: Original requirements.
            generated_code: Generated code to analyze.

        Returns:
            OptimizationAnalysis with recommendations.
        """
        partitioning_recs = self._recommend_partitioning(requirements)
        caching_recs = self._recommend_caching(requirements, generated_code)
        join_opts = self._optimize_joins(requirements)
        general_rules = self._generate_optimization_rules(requirements, generated_code)

        # Calculate overall optimization score
        base_score = 0.6
        if partitioning_recs:
            base_score += 0.1
        if caching_recs:
            base_score += 0.1
        if join_opts:
            base_score += 0.15
        if len(general_rules) >= 3:
            base_score += 0.05

        # Estimate cost reduction
        cost_reduction = self._estimate_cost_reduction(
            partitioning_recs, caching_recs, join_opts
        )

        return OptimizationAnalysis(
            overall_score=min(base_score, 1.0),
            partitioning_recommendations=partitioning_recs,
            caching_recommendations=caching_recs,
            join_optimizations=join_opts,
            optimization_rules=general_rules,
            estimated_cost_reduction=cost_reduction,
            notes="Apply these optimizations based on your data volume and cluster size.",
        )

    def _recommend_partitioning(
        self, requirements: ParsedRequirements
    ) -> List[PartitioningRecommendation]:
        """Generate partitioning recommendations.

        Args:
            requirements: Parsed requirements.

        Returns:
            List of partitioning recommendations.
        """
        recommendations = []

        # Check for date/time columns in sources
        for source in requirements.input_sources:
            date_columns = [
                col.name
                for col in source.schema
                if "date" in col.data_type.lower() or "timestamp" in col.data_type.lower()
            ]
            if date_columns:
                recommendations.append(
                    PartitioningRecommendation(
                        columns=date_columns[:2],  # Max 2 partition columns
                        reason=f"Source '{source.name}' contains temporal data, partitioning by date improves query performance",
                        estimated_benefit="30-60% faster queries with date filters",
                        partition_type="range",
                        num_partitions=None,
                    )
                )

        # Check for high-cardinality grouping columns
        for step in requirements.transformation_steps:
            if step.transformation_type.lower() in ["aggregate", "group_by", "groupby"]:
                group_cols = step.parameters.get("group_by_columns", [])
                if group_cols:
                    recommendations.append(
                        PartitioningRecommendation(
                            columns=group_cols[:2],
                            reason=f"Aggregation on {', '.join(group_cols)} benefits from hash partitioning",
                            estimated_benefit="20-40% faster aggregations, reduced shuffle",
                            partition_type="hash",
                            num_partitions=200,
                        )
                    )
                break  # One recommendation is enough

        return recommendations

    def _recommend_caching(
        self, requirements: ParsedRequirements, generated_code: GeneratedCode
    ) -> List[CachingRecommendation]:
        """Generate caching recommendations.

        Args:
            requirements: Parsed requirements.
            generated_code: Generated code.

        Returns:
            List of caching recommendations.
        """
        recommendations = []
        code_text = generated_code.main_pipeline_code.lower()

        # Check for multiple joins (reused intermediate results)
        join_count = code_text.count(".join(")
        if join_count >= 2:
            recommendations.append(
                CachingRecommendation(
                    dataframe_name="joined_data or intermediate_df",
                    reason="Multiple joins detected - cache intermediate results to avoid recomputation",
                    storage_level="MEMORY_AND_DISK",
                    estimated_reuse_count=join_count,
                )
            )

        # Check for multiple aggregations
        agg_count = code_text.count(".agg(") + code_text.count(".groupby(")
        if agg_count >= 2:
            recommendations.append(
                CachingRecommendation(
                    dataframe_name="aggregated_data",
                    reason="Multiple aggregations detected - cache base aggregation to avoid recomputation",
                    storage_level="MEMORY_AND_DISK",
                    estimated_reuse_count=agg_count,
                )
            )

        # Check for dimension tables (small lookup tables)
        for source in requirements.input_sources:
            if "dim" in source.name.lower() or "lookup" in source.name.lower():
                recommendations.append(
                    CachingRecommendation(
                        dataframe_name=f"{source.name}_df",
                        reason=f"Dimension table '{source.name}' is small and frequently joined - cache in memory",
                        storage_level="MEMORY_ONLY",
                        estimated_reuse_count=3,
                    )
                )

        return recommendations

    def _optimize_joins(
        self, requirements: ParsedRequirements
    ) -> List[JoinOptimization]:
        """Generate join optimization recommendations.

        Args:
            requirements: Parsed requirements.

        Returns:
            List of join optimizations.
        """
        optimizations = []

        for step in requirements.transformation_steps:
            if step.transformation_type.lower() == "join":
                join_type = step.parameters.get("join_type", "inner")
                left_source = step.inputs[0] if len(step.inputs) > 0 else "unknown"
                right_source = step.inputs[1] if len(step.inputs) > 1 else "unknown"

                # Check if it's a dimension table join (broadcast candidate)
                if (
                    "dim" in right_source.lower()
                    or "lookup" in right_source.lower()
                    or "small" in right_source.lower()
                ):
                    optimizations.append(
                        JoinOptimization(
                            join_description=f"{join_type} join between {left_source} and {right_source}",
                            optimization_type="broadcast",
                            reason=f"'{right_source}' appears to be a dimension/lookup table - use broadcast join",
                            estimated_data_size="< 10MB for dimension table",
                            broadcast_threshold="10MB",
                        )
                    )
                else:
                    # Large table join - use sort-merge
                    optimizations.append(
                        JoinOptimization(
                            join_description=f"{join_type} join between {left_source} and {right_source}",
                            optimization_type="sort_merge",
                            reason="Large table join - use sort-merge join with proper partitioning",
                            estimated_data_size="> 100MB",
                            broadcast_threshold=None,
                        )
                    )

        return optimizations

    def _generate_optimization_rules(
        self, requirements: ParsedRequirements, generated_code: GeneratedCode
    ) -> List[OptimizationRule]:
        """Generate general optimization rules.

        Args:
            requirements: Parsed requirements.
            generated_code: Generated code.

        Returns:
            List of optimization rules.
        """
        rules = []
        code_text = generated_code.main_pipeline_code.lower()

        # Filter pushdown
        if ".filter(" in code_text or ".where(" in code_text:
            rules.append(
                OptimizationRule(
                    rule_id="opt-001",
                    category="filter_pushdown",
                    priority="high",
                    title="Apply filters early",
                    description="Move filter operations as early as possible in the pipeline to reduce data volume",
                    code_location="After data read operations",
                    estimated_impact="40-70% reduction in data processed",
                )
            )

        # Column pruning
        if ".select(" in code_text:
            rules.append(
                OptimizationRule(
                    rule_id="opt-002",
                    category="shuffle",
                    priority="medium",
                    title="Select only required columns",
                    description="Use .select() to keep only necessary columns before expensive operations",
                    code_location="Before joins and aggregations",
                    estimated_impact="20-30% memory reduction",
                )
            )

        # Repartitioning before shuffle operations
        if ".join(" in code_text or ".groupby(" in code_text:
            rules.append(
                OptimizationRule(
                    rule_id="opt-003",
                    category="shuffle",
                    priority="high",
                    title="Repartition before shuffle operations",
                    description="Use .repartition() on join keys before joins to optimize shuffle",
                    code_location="Before join operations",
                    estimated_impact="30-50% faster joins",
                )
            )

        # Broadcast hint
        if ".join(" in code_text:
            rules.append(
                OptimizationRule(
                    rule_id="opt-004",
                    category="broadcast",
                    priority="high",
                    title="Use broadcast joins for small tables",
                    description="Use broadcast() hint for tables < 10MB to avoid shuffle",
                    code_location="Join operations with dimension tables",
                    estimated_impact="60-80% faster joins with small tables",
                )
            )

        # Coalesce after filter
        if ".filter(" in code_text or ".where(" in code_text:
            rules.append(
                OptimizationRule(
                    rule_id="opt-005",
                    category="spill",
                    priority="medium",
                    title="Coalesce after filtering",
                    description="Use .coalesce() after aggressive filtering to reduce partition count",
                    code_location="After filter operations that significantly reduce data",
                    estimated_impact="15-25% faster downstream operations",
                )
            )

        return rules

    def _estimate_cost_reduction(
        self,
        partitioning_recs: List[PartitioningRecommendation],
        caching_recs: List[CachingRecommendation],
        join_opts: List[JoinOptimization],
    ) -> str:
        """Estimate overall cost reduction.

        Args:
            partitioning_recs: Partitioning recommendations.
            caching_recs: Caching recommendations.
            join_opts: Join optimizations.

        Returns:
            Cost reduction estimate string.
        """
        total_score = 0

        if partitioning_recs:
            total_score += len(partitioning_recs) * 15
        if caching_recs:
            total_score += len(caching_recs) * 10
        if join_opts:
            total_score += len(join_opts) * 20

        if total_score >= 50:
            return "40-60% reduction in compute costs"
        elif total_score >= 30:
            return "25-40% reduction in compute costs"
        elif total_score >= 15:
            return "15-25% reduction in compute costs"
        else:
            return "10-15% reduction in compute costs"

    def _add_optimization_comments(
        self, generated_code: GeneratedCode, optimization_analysis: OptimizationAnalysis
    ) -> GeneratedCode:
        """Add optimization hints as comments to generated code.

        Args:
            generated_code: Original generated code.
            optimization_analysis: Optimization analysis.

        Returns:
            Updated GeneratedCode with optimization comments.
        """
        code = generated_code.main_pipeline_code

        # Add optimization header comment
        optimization_header = "\n".join([
            "# ============================================",
            "# PERFORMANCE OPTIMIZATION RECOMMENDATIONS",
            "# ============================================",
            f"# Overall Optimization Score: {optimization_analysis.overall_score:.2f}",
            f"# Estimated Cost Reduction: {optimization_analysis.estimated_cost_reduction or 'N/A'}",
            "#",
        ])

        # Add partitioning recommendations
        if optimization_analysis.partitioning_recommendations:
            optimization_header += "# PARTITIONING:\n"
            for rec in optimization_analysis.partitioning_recommendations:
                optimization_header += f"#   - Partition by {', '.join(rec.columns)} ({rec.partition_type})\n"
                optimization_header += f"#     Reason: {rec.reason}\n"
                optimization_header += f"#     Benefit: {rec.estimated_benefit}\n"
            optimization_header += "#\n"

        # Add caching recommendations
        if optimization_analysis.caching_recommendations:
            optimization_header += "# CACHING:\n"
            for rec in optimization_analysis.caching_recommendations:
                optimization_header += f"#   - Cache '{rec.dataframe_name}' ({rec.storage_level})\n"
                optimization_header += f"#     Reason: {rec.reason}\n"
            optimization_header += "#\n"

        # Add join optimizations
        if optimization_analysis.join_optimizations:
            optimization_header += "# JOIN OPTIMIZATIONS:\n"
            for opt in optimization_analysis.join_optimizations:
                optimization_header += f"#   - {opt.join_description}\n"
                optimization_header += f"#     Strategy: {opt.optimization_type}\n"
                optimization_header += f"#     Reason: {opt.reason}\n"
            optimization_header += "#\n"

        # Add top priority rules
        high_priority_rules = [
            r for r in optimization_analysis.optimization_rules if r.priority == "high"
        ]
        if high_priority_rules:
            optimization_header += "# HIGH PRIORITY OPTIMIZATIONS:\n"
            for rule in high_priority_rules[:3]:  # Top 3
                optimization_header += f"#   - {rule.title}\n"
                optimization_header += f"#     {rule.description}\n"
                optimization_header += f"#     Impact: {rule.estimated_impact}\n"
            optimization_header += "#\n"

        optimization_header += "# ============================================\n\n"

        # Prepend to code
        updated_code = optimization_header + code

        # Update the generated code object
        generated_code.main_pipeline_code = updated_code

        return generated_code

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
