"""Schemas and data models for the Coding Agent.

The Coding Agent is responsible for generating PySpark code and Pydantic models
from parsed requirements extracted by the Task Agent.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field
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


class CodingAgentOutput(BaseModel):
    """Output from the Coding Agent."""

    generated_code: GeneratedCode = Field(
        ..., description="Complete generated code with models and pipeline"
    )
    code_quality_score: float = Field(
        ..., description="Quality score of generated code (0-1)"
    )
    generation_notes: Optional[str] = Field(
        None, description="Notes or warnings about code generation"
    )
    raw_generation: Optional[Dict[str, Any]] = Field(
        None, description="Raw LLM generation output for debugging"
    )
