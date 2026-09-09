"""Schemas and data models for the Coding Agent.

The Coding Agent is responsible for generating PySpark code and Pydantic models
from parsed requirements extracted by the Task Agent.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field, field_validator
from src.agents.task_agent.schemas import ParsedRequirements


class PydanticModel(BaseModel):
    """Generated Pydantic model definition."""

    model_name: str = Field(..., description="Name of the Pydantic model class")
    module_name: str = Field(..., description="Module path for the model (e.g., 'models.input_schema')")
    description: str = Field(..., description="Docstring description of the model")
    code: str = Field(..., description="Full Python code for the Pydantic model")
    fields: List[Dict[str, Any]] = Field(
        default_factory=list, description="Metadata about model fields"
    )


class CodeFile(BaseModel):
    """Generated code file."""

    file_name: str = Field(..., description="Name of the file (e.g., 'pipeline.py')")
    file_path: str = Field(..., description="Relative path where file should be created")
    description: str = Field(..., description="Purpose of this file")
    code: str = Field(..., description="Full Python code content")
    imports: List[str] = Field(
        default_factory=list, description="Required imports for this file"
    )


class GeneratedCode(BaseModel):
    """Complete generated code output."""

    main_pipeline_code: str = Field(
        ..., description="Main PySpark pipeline implementation"
    )
    input_schema_model: PydanticModel = Field(
        ..., description="Pydantic model for input data validation"
    )
    output_schema_model: PydanticModel = Field(
        ..., description="Pydantic model for output data validation"
    )
    additional_models: List[PydanticModel] = Field(
        default_factory=list, description="Additional Pydantic models for intermediate steps"
    )
    additional_files: List[CodeFile] = Field(
        default_factory=list, description="Additional code files (utilities, config, etc.)"
    )
    imports: List[str] = Field(
        default_factory=list, description="All required imports"
    )


class CodeConfiguration(BaseModel):
    """Configuration for code generation."""

    target_spark_version: str = Field(
        default="3.5.0", description="Target PySpark version"
    )
    use_delta_lake: bool = Field(
        default=True, description="Whether to use Delta Lake format"
    )
    enable_type_hints: bool = Field(
        default=True, description="Whether to include type hints in generated code"
    )
    code_style: Literal["standard", "mlflow", "dbt"] = Field(
        default="standard", description="Code style/framework to follow"
    )
    include_docstrings: bool = Field(
        default=True, description="Whether to include docstrings"
    )
    include_logging: bool = Field(
        default=True, description="Whether to include logging statements"
    )
    include_error_handling: bool = Field(
        default=True, description="Whether to include error handling"
    )


class CodingAgentInput(BaseModel):
    """Input to the Coding Agent."""

    requirements: ParsedRequirements = Field(
        ..., description="Parsed requirements from the Task Agent"
    )
    config: CodeConfiguration = Field(
        default_factory=CodeConfiguration, description="Code generation configuration"
    )


class PartitioningRecommendation(BaseModel):
    """Recommendation for data partitioning strategy."""

    columns: List[str] = Field(..., description="Columns to partition by")
    reason: str = Field(..., description="Rationale for this partitioning strategy")
    estimated_benefit: str = Field(..., description="Expected performance benefit")
    partition_type: Literal["hash", "range", "list"] = Field(
        default="hash", description="Type of partitioning to use"
    )
    num_partitions: Optional[int] = Field(None, description="Recommended number of partitions")


class CachingRecommendation(BaseModel):
    """Recommendation for DataFrame caching."""

    dataframe_name: str = Field(..., description="Name/identifier of DataFrame to cache")
    reason: str = Field(..., description="Why this DataFrame should be cached")
    storage_level: Literal["MEMORY_ONLY", "MEMORY_AND_DISK", "DISK_ONLY", "MEMORY_ONLY_SER"] = Field(
        default="MEMORY_AND_DISK", description="Storage level for caching"
    )
    estimated_reuse_count: int = Field(..., description="Estimated number of times this DataFrame will be reused")


class JoinOptimization(BaseModel):
    """Optimization recommendation for join operations."""

    join_description: str = Field(..., description="Description of the join operation")
    optimization_type: Literal["broadcast", "sort_merge", "shuffle_hash", "bucketed"] = Field(
        ..., description="Recommended join strategy"
    )
    reason: str = Field(..., description="Rationale for this join optimization")
    estimated_data_size: Optional[str] = Field(None, description="Estimated size of data being joined")
    broadcast_threshold: Optional[str] = Field(None, description="Broadcast threshold if using broadcast join")


class OptimizationRule(BaseModel):
    """Single optimization recommendation."""

    rule_id: str = Field(..., description="Unique identifier for this optimization rule")
    category: Literal["partitioning", "caching", "join", "shuffle", "spill", "broadcast", "filter_pushdown"] = Field(
        ..., description="Category of optimization"
    )
    priority: Literal["high", "medium", "low"] = Field(..., description="Priority/impact of this optimization")
    title: str = Field(..., description="Short title for the optimization")
    description: str = Field(..., description="Detailed description of the optimization")
    code_location: Optional[str] = Field(None, description="Where in the code this applies")
    estimated_impact: str = Field(..., description="Estimated performance impact (e.g., '30% faster', 'reduce memory by 2x')")


class OptimizationAnalysis(BaseModel):
    """Complete optimization analysis for generated code."""

    overall_score: float = Field(..., description="Overall optimization score (0-1)", ge=0.0, le=1.0)
    partitioning_recommendations: List[PartitioningRecommendation] = Field(
        default_factory=list, description="Partitioning strategy recommendations"
    )
    caching_recommendations: List[CachingRecommendation] = Field(
        default_factory=list, description="Caching strategy recommendations"
    )
    join_optimizations: List[JoinOptimization] = Field(
        default_factory=list, description="Join optimization recommendations"
    )
    optimization_rules: List[OptimizationRule] = Field(
        default_factory=list, description="General optimization rules and recommendations"
    )
    estimated_cost_reduction: Optional[str] = Field(
        None, description="Estimated cost reduction from applying optimizations"
    )
    notes: Optional[str] = Field(None, description="Additional notes about optimizations")


class CodingAgentOutput(BaseModel):
    """Output from the Coding Agent."""

    generated_code: GeneratedCode = Field(
        ..., description="Complete generated code with models and pipeline"
    )
    code_quality_score: float = Field(
        ..., description="Quality score of generated code (0-1)"
    )
    optimization_analysis: Optional[OptimizationAnalysis] = Field(
        None, description="Performance optimization analysis and recommendations"
    )
    generation_notes: Optional[str] = Field(
        None, description="Notes or warnings about code generation"
    )
    raw_generation: Optional[Dict[str, Any]] = Field(
        None, description="Raw LLM generation output for debugging"
    )
