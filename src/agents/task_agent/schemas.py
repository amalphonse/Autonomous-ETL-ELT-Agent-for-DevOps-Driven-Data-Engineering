"""Schema and data models for the Task Agent.

The Task Agent is responsible for parsing user stories and extracting
transformation intent into structured requirements.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field

# Using plain str instead of Enum so the LLM can use any reasonable
# transformation or type name without validation errors.
TransformationType = str
DataType = str


class ColumnDefinition(BaseModel):
    """Definition of a data column."""

    name: str = Field(..., description="Column name")
    data_type: DataType = Field(..., description="Data type of the column")
    nullable: bool = Field(default=True, description="Whether the column can be null")
    description: Optional[str] = Field(None, description="Column description")


class DataSource(BaseModel):
    """Input data source specification."""

    name: str = Field(..., description="Name/identifier of the data source")
    location: str = Field(..., description="Path or connection string to the data source")
    format: str = Field(
        ..., description="Format of the data source (e.g. csv, parquet, json, delta, sql, kafka)"
    )
    schema: List[ColumnDefinition] = Field(
        ..., description="Schema definition for the data source"
    )
    is_streaming: bool = Field(default=False, description="Whether this is a streaming source")


class TransformationStep(BaseModel):
    """A single transformation step in the pipeline."""

    step_id: str = Field(..., description="Unique identifier for this step")
    transformation_type: TransformationType = Field(
        ..., description="Type of transformation"
    )
    description: str = Field(..., description="Human-readable description of what this step does")
    inputs: List[str] = Field(..., description="Input column/stage names")
    outputs: List[str] = Field(..., description="Output column/stage names")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Transformation-specific parameters (e.g., join conditions, aggregation functions)"
    )
    sql_snippet: Optional[str] = Field(None, description="Optional SQL snippet for advanced transformations")


class DataQualityRule(BaseModel):
    """Data quality rule for validation."""

    rule_id: str = Field(..., description="Unique identifier for the rule")
    rule_type: Literal["null_check", "schema", "uniqueness", "range", "pattern", "custom"] = Field(
        ..., description="Type of validation rule"
    )
    column: Optional[str] = Field(None, description="Column to apply rule to")
    description: str = Field(..., description="Description of the rule")
    parameters: Dict[str, Any] = Field(
        default_factory=dict, description="Rule-specific parameters"
    )


class ParsedRequirements(BaseModel):
    """Parsed and structured requirements extracted from a user story."""

    story_id: str = Field(..., description="Unique identifier for this user story")
    title: str = Field(..., description="Title/summary of the requirement")
    description: str = Field(..., description="Detailed description of what needs to be built")
    input_sources: List[DataSource] = Field(
        ..., description="Input data sources for the pipeline"
    )
    output_schema: List[ColumnDefinition] = Field(
        ..., description="Expected output schema"
    )
    output_location: str = Field(
        ..., description="Where the output should be written (path or table name)"
    )
    transformation_steps: List[TransformationStep] = Field(
        ..., description="Sequence of transformation steps"
    )
    quality_rules: List[DataQualityRule] = Field(
        default_factory=list, description="Data quality validation rules"
    )
    frequency: Literal["once", "hourly", "daily", "weekly", "monthly"] = Field(
        default="once", description="Execution frequency for the pipeline"
    )
    sla_hours: Optional[float] = Field(
        None, description="Service level agreement (SLA) in hours"
    )
    dependencies: List[str] = Field(
        default_factory=list, description="Upstream pipeline dependencies"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class UserStory(BaseModel):
    """Raw user story input from DevOps."""

    user_id: str = Field(..., description="ID of user submitting the request")
    request_id: str = Field(..., description="Unique request identifier")
    story: str = Field(..., description="Raw user story text or structured description")
    format: Literal["text", "json", "yaml"] = Field(
        default="text", description="Format of the user story"
    )
    attachments: Optional[Dict[str, Any]] = Field(
        None, description="Additional data (schema samples, sample data, etc.)"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class TaskAgentInput(BaseModel):
    """Input to the Task Agent."""

    user_story: UserStory = Field(..., description="The user story to parse")


class TaskAgentOutput(BaseModel):
    """Output from the Task Agent."""

    requirements: ParsedRequirements = Field(..., description="Parsed and structured requirements")
    confidence_score: float = Field(
        ..., description="Confidence score of the parsing (0-1)"
    )
    parsing_notes: Optional[str] = Field(
        None, description="Notes or warnings about the parsing"
    )
    raw_analysis: Optional[Dict[str, Any]] = Field(
        None, description="Raw LLM analysis output for debugging"
    )
