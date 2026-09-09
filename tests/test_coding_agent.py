"""Unit tests for the Coding Agent."""

import pytest
import json
from unittest.mock import patch, MagicMock

from src.agents.coding_agent import CodingAgent, CodingAgentInput, CodingAgentOutput, CodeFile
from src.agents.coding_agent.schemas import (
    OptimizationAnalysis,
    PartitioningRecommendation,
    CachingRecommendation,
    JoinOptimization,
    OptimizationRule,
    GeneratedCode,
    PydanticModel,
)
from src.agents.task_agent.schemas import (
    ParsedRequirements,
    DataSource,
    ColumnDefinition,
    DataType,
    TransformationStep,
    TransformationType,
)
from src.types import AgentStatus, AgentType


@pytest.fixture
def coding_agent():
    """Fixture for CodingAgent instance."""
    with patch("src.agents.coding_agent.coding_agent.ChatOpenAI"):
        with patch("src.agents.coding_agent.coding_agent.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"
            mock_settings.return_value.openai_model = "gpt-4o"
            mock_settings.return_value.openai_temperature = 0.3
            return CodingAgent()


@pytest.fixture
def sample_parsed_requirements():
    """Fixture for sample parsed requirements from Task Agent."""
    return ParsedRequirements(
        story_id="req456",
        title="Filter and aggregate orders by region",
        description="Filter orders from the last 30 days with amount > 1000, join with customer data, and aggregate by region",
        input_sources=[
            DataSource(
                name="orders",
                location="data/orders",
                format="parquet",
                schema=[
                    ColumnDefinition(
                        name="order_id",
                        data_type="string",
                        nullable=False,
                        description="Order ID",
                    ),
                    ColumnDefinition(
                        name="customer_id",
                        data_type="string",
                        nullable=False,
                        description="Customer ID",
                    ),
                    ColumnDefinition(
                        name="amount",
                        data_type="double",
                        nullable=False,
                        description="Order amount",
                    ),
                    ColumnDefinition(
                        name="order_date",
                        data_type="date",
                        nullable=False,
                        description="Order date",
                    ),
                ],
                is_streaming=False,
            ),
            DataSource(
                name="customers",
                location="data/customers",
                format="parquet",
                schema=[
                    ColumnDefinition(
                        name="customer_id",
                        data_type="string",
                        nullable=False,
                        description="Customer ID",
                    ),
                    ColumnDefinition(
                        name="region",
                        data_type="string",
                        nullable=False,
                        description="Customer region",
                    ),
                ],
                is_streaming=False,
            ),
        ],
        output_schema=[
            ColumnDefinition(
                name="region",
                data_type="string",
                nullable=False,
                description="Customer region",
            ),
            ColumnDefinition(
                name="total_amount",
                data_type="double",
                nullable=False,
                description="Total order amount",
            ),
            ColumnDefinition(
                name="order_count",
                data_type="integer",
                nullable=False,
                description="Number of orders",
            ),
        ],
        output_location="analytics/orders_by_region",
        transformation_steps=[
            TransformationStep(
                step_id="step1",
                transformation_type="filter",
                description="Filter orders from last 30 days with amount > 1000",
                inputs=["orders"],
                outputs=["filtered_orders"],
                parameters={"days": 30, "min_amount": 1000},
            ),
            TransformationStep(
                step_id="step2",
                transformation_type="join",
                description="Join with customer data",
                inputs=["filtered_orders", "customers"],
                outputs=["orders_with_region"],
                parameters={"join_type": "inner", "on": "customer_id"},
            ),
            TransformationStep(
                step_id="step3",
                transformation_type="aggregate",
                description="Group by region and sum amounts",
                inputs=["orders_with_region"],
                outputs=["result"],
                parameters={
                    "group_by": ["region"],
                    "aggregations": {
                        "total_amount": "sum(amount)",
                        "order_count": "count(*)",
                    },
                },
            ),
        ],
        quality_rules=[],
        frequency="daily",
        sla_hours=2,
        dependencies=[],
        metadata={},
    )


@pytest.fixture
def mock_llm_code_response():
    """Fixture for mock LLM code generation response."""
    return """{
  "main_pipeline_code": "from pyspark.sql import SparkSession\\nfrom pyspark.sql.functions import col, sum, count\\nfrom datetime import datetime, timedelta\\n\\ndef create_spark_session():\\n    return SparkSession.builder.appName('OrderAggregation').getOrCreate()\\n\\ndef main():\\n    spark = create_spark_session()\\n    \\n    # Read input sources\\n    orders_df = spark.read.format('parquet').load('data/orders')\\n    customers_df = spark.read.format('parquet').load('data/customers')\\n    \\n    # Filter step\\n    thirty_days_ago = datetime.now() - timedelta(days=30)\\n    filtered_orders = orders_df.where((col('amount') > 1000) & (col('order_date') >= thirty_days_ago))\\n    \\n    # Join step\\n    orders_with_region = filtered_orders.join(customers_df, 'customer_id', 'inner')\\n    \\n    # Aggregate step\\n    result = orders_with_region.groupBy('region').agg(\\n        sum('amount').alias('total_amount'),\\n        count('*').alias('order_count')\\n    )\\n    \\n    # Write output\\n    result.write.format('delta').mode('overwrite').save('analytics/orders_by_region')\\n",
  "input_schema_model": {
    "model_name": "OrdersInputSchema",
    "module_name": "models.input_schema",
    "description": "Validation schema for input orders data",
    "code": "from pydantic import BaseModel, Field\\nfrom typing import Optional\\nfrom datetime import date\\n\\nclass OrdersInputSchema(BaseModel):\\n    order_id: str = Field(..., description='Order ID')\\n    customer_id: str = Field(..., description='Customer ID')\\n    amount: float = Field(..., description='Order amount')\\n    order_date: date = Field(..., description='Order date')\\n",
    "fields": [
      {"name": "order_id", "type": "str", "description": "Order ID"},
      {"name": "customer_id", "type": "str", "description": "Customer ID"},
      {"name": "amount", "type": "float", "description": "Order amount"},
      {"name": "order_date", "type": "date", "description": "Order date"}
    ]
  },
  "output_schema_model": {
    "model_name": "OutputSchema",
    "module_name": "models.output_schema",
    "description": "Validation schema for output aggregated data",
    "code": "from pydantic import BaseModel, Field\\n\\nclass OutputSchema(BaseModel):\\n    region: str = Field(..., description='Customer region')\\n    total_amount: float = Field(..., description='Total order amount')\\n    order_count: int = Field(..., description='Number of orders')\\n",
    "fields": [
      {"name": "region", "type": "str", "description": "Customer region"},
      {"name": "total_amount", "type": "float", "description": "Total order amount"},
      {"name": "order_count", "type": "int", "description": "Number of orders"}
    ]
  },
  "additional_models": [],
  "additional_files": [
    {
      "file_name": "pipeline.py",
      "file_path": "src/pipeline.py",
      "description": "Main pipeline orchestration",
      "code": "import logging\\nfrom typing import Optional\\nfrom pyspark.sql import SparkSession, DataFrame\\n\\nlogger = logging.getLogger(__name__)\\n\\nclass Pipeline:\\n    def __init__(self, spark: SparkSession):\\n        self.spark = spark\\n    \\n    def execute(self) -> DataFrame:\\n        logger.info('Starting pipeline execution')\\n        # ... pipeline code ...\\n        logger.info('Pipeline completed successfully')\\n",
      "imports": ["from pyspark.sql import SparkSession, DataFrame"]
    }
  ],
  "imports": ["from pyspark.sql import SparkSession", "from pyspark.sql.functions import col, sum, count", "from datetime import datetime, timedelta"]
}"""


class TestCodingAgentInitialization:
    """Tests for Coding Agent initialization."""

    def test_agent_initialization(self, coding_agent):
        """Test that Coding Agent initializes correctly."""
        assert coding_agent.agent_type == AgentType.CODING
        assert coding_agent.llm is not None
        assert coding_agent.code_generation_prompt is not None

    def test_agent_has_methods(self, coding_agent):
        """Test that Coding Agent has all required methods."""
        assert hasattr(coding_agent, "execute")
        assert hasattr(coding_agent, "validate_input")
        assert hasattr(coding_agent, "_extract_json")
        assert hasattr(coding_agent, "_parse_code_response")


class TestInputValidation:
    """Tests for Coding Agent input validation."""

    def test_valid_input(self, coding_agent, sample_parsed_requirements):
        """Test validation of valid input."""
        valid_input = {"requirements": sample_parsed_requirements.dict()}
        assert coding_agent.validate_input(valid_input) is True

    def test_missing_requirements(self, coding_agent):
        """Test validation fails without requirements."""
        invalid_input = {}
        assert coding_agent.validate_input(invalid_input) is False

    def test_invalid_requirements_data(self, coding_agent):
        """Test validation fails with invalid requirements data."""
        invalid_input = {"requirements": {"invalid": "data"}}
        assert coding_agent.validate_input(invalid_input) is False


class TestJSONExtraction:
    """Tests for JSON extraction from LLM responses."""

    def test_extract_clean_json(self, coding_agent):
        """Test extraction of clean JSON."""
        json_str = '{"key": "value", "number": 42}'
        result = coding_agent._extract_json(json_str)
        assert json.loads(result) == {"key": "value", "number": 42}

    def test_extract_wrapped_json(self, coding_agent):
        """Test extraction of JSON wrapped in markdown or text."""
        response = """Here's the generated code:

```json
{"key": "value", "number": 42}
```

This is the complete code."""
        result = coding_agent._extract_json(response)
        assert json.loads(result) == {"key": "value", "number": 42}

    def test_extract_json_with_explanation(self, coding_agent):
        """Test extraction of JSON with surrounding explanation."""
        response = (
            "Based on requirements, here's the code: "
            '{"main_pipeline_code": "code here", "imports": []} More explanation.'
        )
        result = coding_agent._extract_json(response)
        parsed = json.loads(result)
        assert "main_pipeline_code" in parsed
        assert "imports" in parsed


class TestCodeQualityScoring:
    """Tests for code quality scoring."""

    def test_quality_score_range(self, coding_agent, sample_parsed_requirements):
        """Test that quality scores are in valid range."""
        from src.agents.coding_agent.schemas import GeneratedCode, PydanticModel

        generated_code = GeneratedCode(
            main_pipeline_code="def process(): pass",
            input_schema_model=PydanticModel(
                model_name="Input",
                module_name="models.input",
                description="Input model",
                code="class Input: pass",
            ),
            output_schema_model=PydanticModel(
                model_name="Output",
                module_name="models.output",
                description="Output model",
                code="class Output: pass",
            ),
        )

        score = coding_agent._calculate_quality_score(
            sample_parsed_requirements, generated_code
        )

        assert 0.0 <= score <= 1.0

    def test_quality_score_increases_with_completeness(
        self, coding_agent, sample_parsed_requirements
    ):
        """Test that quality score improves with more complete code."""
        from src.agents.coding_agent.schemas import GeneratedCode, PydanticModel, CodeFile

        minimal_code = GeneratedCode(
            main_pipeline_code="",
            input_schema_model=PydanticModel(
                model_name="Input",
                module_name="models.input",
                description="",
                code="",
            ),
            output_schema_model=PydanticModel(
                model_name="Output",
                module_name="models.output",
                description="",
                code="",
            ),
        )

        complete_code = GeneratedCode(
            main_pipeline_code="x" * 1000,
            input_schema_model=PydanticModel(
                model_name="Input",
                module_name="models.input",
                description="desc",
                code="code" * 100,
                fields=[{"name": "field", "type": "str"}],
            ),
            output_schema_model=PydanticModel(
                model_name="Output",
                module_name="models.output",
                description="desc",
                code="code" * 100,
                fields=[{"name": "field", "type": "str"}],
            ),
            imports=["import x"],
            additional_files=[
                CodeFile(
                    file_name="util.py",
                    file_path="src/util.py",
                    description="utils",
                    code="code",
                )
            ],
        )

        minimal_score = coding_agent._calculate_quality_score(
            sample_parsed_requirements, minimal_code
        )
        complete_score = coding_agent._calculate_quality_score(
            sample_parsed_requirements, complete_code
        )

        assert complete_score > minimal_score


class TestCodeParsing:
    """Tests for code response parsing."""

    def test_parse_valid_code_response(self, coding_agent, mock_llm_code_response):
        """Test parsing of valid LLM code response."""
        response_data = json.loads(mock_llm_code_response)
        generated_code = coding_agent._parse_code_response(response_data)

        assert generated_code.main_pipeline_code
        assert generated_code.input_schema_model.model_name == "OrdersInputSchema"
        assert generated_code.output_schema_model.model_name == "OutputSchema"
        assert len(generated_code.imports) > 0

    def test_parse_partial_response(self, coding_agent):
        """Test parsing when some optional fields are missing."""
        minimal_response = {
            "main_pipeline_code": "def process(): pass",
            "input_schema_model": {
                "model_name": "Input",
                "module_name": "models.input",
                "description": "Input",
                "code": "code",
            },
            "output_schema_model": {
                "model_name": "Output",
                "module_name": "models.output",
                "description": "Output",
                "code": "code",
            },
        }

        generated_code = coding_agent._parse_code_response(minimal_response)

        assert generated_code.main_pipeline_code
        assert generated_code.input_schema_model.model_name == "Input"
        assert generated_code.additional_models == []
        assert generated_code.additional_files == []


class TestCodingAgentOutput:
    """Tests for Coding Agent output structure."""

    @pytest.mark.asyncio
    async def test_successful_execution(
        self, coding_agent, sample_parsed_requirements, mock_llm_code_response
    ):
        """Test successful execution of Coding Agent."""
        with patch.object(
            coding_agent, "_generate_pipeline_code"
        ) as mock_generate:
            mock_generate.return_value = json.loads(mock_llm_code_response)

            agent_input = {
                "requirements": sample_parsed_requirements.dict()
            }

            output = await coding_agent.execute(agent_input)

            assert output.status == AgentStatus.SUCCESS
            assert output.agent_type == AgentType.CODING
            assert "generated_code" in output.data
            assert "code_quality_score" in output.data

    @pytest.mark.asyncio
    async def test_invalid_input_execution(self, coding_agent):
        """Test execution with invalid input."""
        invalid_input = {"invalid": "data"}

        output = await coding_agent.execute(invalid_input)

        assert output.status == AgentStatus.FAILED
        assert output.error is not None

    @pytest.mark.asyncio
    async def test_error_handling_on_llm_failure(
        self, coding_agent, sample_parsed_requirements
    ):
        """Test error handling when LLM fails."""
        with patch.object(
            coding_agent, "_generate_pipeline_code"
        ) as mock_generate:
            mock_generate.side_effect = Exception("LLM error")

            agent_input = {
                "requirements": sample_parsed_requirements.dict()
            }

            output = await coding_agent.execute(agent_input)

            assert output.status == AgentStatus.FAILED
            assert "LLM error" in output.error

class TestOptimizationAnalysis:
    """Tests for pipeline optimization analysis."""

    def test_partitioning_recommendations_for_date_columns(
        self, coding_agent, sample_parsed_requirements
    ):
        """Test that partitioning recommendations are generated for date columns."""
        recommendations = coding_agent._recommend_partitioning(sample_parsed_requirements)
        
        assert len(recommendations) > 0
        date_rec = recommendations[0]
        assert "order_date" in date_rec.columns
        assert date_rec.partition_type == "range"
        assert "temporal" in date_rec.reason.lower() or "date" in date_rec.reason.lower()

    def test_partitioning_recommendations_for_aggregations(self, coding_agent):
        """Test that partitioning recommendations are generated for group-by operations."""
        requirements = ParsedRequirements(
            story_id="test-123",
            title="Test aggregation",
            description="Test",
            input_sources=[
                DataSource(
                    name="sales",
                    location="data/sales",
                    format="parquet",
                    schema=[
                        ColumnDefinition(name="product_id", data_type="string", nullable=False),
                        ColumnDefinition(name="amount", data_type="double", nullable=False),
                    ],
                )
            ],
            output_schema=[],
            output_location="data/output",
            transformation_steps=[
                TransformationStep(
                    step_id="step1",
                    transformation_type="aggregate",
                    description="Group by product",
                    inputs=["sales"],
                    outputs=["aggregated"],
                    parameters={"group_by_columns": ["product_id", "category"]},
                )
            ],
            quality_rules=[],
        )
        
        recommendations = coding_agent._recommend_partitioning(requirements)
        
        assert len(recommendations) > 0
        agg_rec = [r for r in recommendations if r.partition_type == "hash"]
        assert len(agg_rec) > 0
        assert "product_id" in agg_rec[0].columns or "category" in agg_rec[0].columns

    def test_caching_recommendations_for_joins(self, coding_agent, sample_parsed_requirements):
        """Test that caching recommendations are generated for multiple joins."""
        generated_code = GeneratedCode(
            main_pipeline_code="""
df1 = spark.read.parquet('data')
df2 = spark.read.parquet('lookup')
joined1 = df1.join(df2, on='id')
joined2 = joined1.join(df2, on='key')
joined3 = joined2.join(df2, on='category')
            """,
            input_schema_model=PydanticModel(
                model_name="Input", module_name="models", description="", code=""
            ),
            output_schema_model=PydanticModel(
                model_name="Output", module_name="models", description="", code=""
            ),
        )
        
        recommendations = coding_agent._recommend_caching(sample_parsed_requirements, generated_code)
        
        assert len(recommendations) > 0
        assert any("join" in rec.reason.lower() for rec in recommendations)

    def test_caching_recommendations_for_dimension_tables(self, coding_agent):
        """Test that dimension tables get caching recommendations."""
        requirements = ParsedRequirements(
            story_id="test-123",
            title="Test dimension join",
            description="Test",
            input_sources=[
                DataSource(
                    name="dim_products",
                    location="data/dim_products",
                    format="parquet",
                    schema=[
                        ColumnDefinition(name="product_id", data_type="string", nullable=False),
                    ],
                )
            ],
            output_schema=[],
            output_location="data/output",
            transformation_steps=[],
            quality_rules=[],
        )
        
        generated_code = GeneratedCode(
            main_pipeline_code="df = spark.read.parquet('data')",
            input_schema_model=PydanticModel(
                model_name="Input", module_name="models", description="", code=""
            ),
            output_schema_model=PydanticModel(
                model_name="Output", module_name="models", description="", code=""
            ),
        )
        
        recommendations = coding_agent._recommend_caching(requirements, generated_code)
        
        dim_recs = [r for r in recommendations if "dim" in r.dataframe_name.lower()]
        assert len(dim_recs) > 0
        assert dim_recs[0].storage_level == "MEMORY_ONLY"

    def test_join_optimization_broadcast_for_dimension_tables(self, coding_agent):
        """Test that broadcast join is recommended for dimension tables."""
        requirements = ParsedRequirements(
            story_id="test-123",
            title="Test join optimization",
            description="Test",
            input_sources=[],
            output_schema=[],
            output_location="data/output",
            transformation_steps=[
                TransformationStep(
                    step_id="step1",
                    transformation_type="join",
                    description="Join with dimension",
                    inputs=["orders", "dim_customers"],
                    outputs=["joined"],
                    parameters={"join_type": "inner"},
                )
            ],
            quality_rules=[],
        )
        
        optimizations = coding_agent._optimize_joins(requirements)
        
        assert len(optimizations) > 0
        assert optimizations[0].optimization_type == "broadcast"
        assert "dim" in optimizations[0].join_description.lower() or "dimension" in optimizations[0].reason.lower()

    def test_join_optimization_sort_merge_for_large_tables(self, coding_agent):
        """Test that sort-merge join is recommended for large tables."""
        requirements = ParsedRequirements(
            story_id="test-123",
            title="Test join optimization",
            description="Test",
            input_sources=[],
            output_schema=[],
            output_location="data/output",
            transformation_steps=[
                TransformationStep(
                    step_id="step1",
                    transformation_type="join",
                    description="Join large tables",
                    inputs=["orders", "transactions"],
                    outputs=["joined"],
                    parameters={"join_type": "inner"},
                )
            ],
            quality_rules=[],
        )
        
        optimizations = coding_agent._optimize_joins(requirements)
        
        assert len(optimizations) > 0
        assert optimizations[0].optimization_type == "sort_merge"

    def test_optimization_rules_generation(self, coding_agent, sample_parsed_requirements):
        """Test that general optimization rules are generated."""
        generated_code = GeneratedCode(
            main_pipeline_code="""
df = spark.read.parquet('data')
filtered = df.filter(col('amount') > 100)
selected = filtered.select('id', 'amount')
joined = selected.join(other, on='id')
grouped = joined.groupBy('category').agg(sum('amount'))
            """,
            input_schema_model=PydanticModel(
                model_name="Input", module_name="models", description="", code=""
            ),
            output_schema_model=PydanticModel(
                model_name="Output", module_name="models", description="", code=""
            ),
        )
        
        rules = coding_agent._generate_optimization_rules(sample_parsed_requirements, generated_code)
        
        assert len(rules) > 0
        
        # Check for filter pushdown rule
        filter_rules = [r for r in rules if r.category == "filter_pushdown"]
        assert len(filter_rules) > 0
        
        # Check for broadcast rule
        broadcast_rules = [r for r in rules if r.category == "broadcast"]
        assert len(broadcast_rules) > 0
        
        # Check for shuffle rule
        shuffle_rules = [r for r in rules if r.category == "shuffle"]
        assert len(shuffle_rules) > 0

    def test_cost_reduction_estimation(self, coding_agent):
        """Test cost reduction estimation based on optimizations."""
        # High optimization potential
        partitioning_recs = [
            PartitioningRecommendation(
                columns=["date"],
                reason="Test",
                estimated_benefit="30%",
                partition_type="range",
            )
        ]
        caching_recs = [
            CachingRecommendation(
                dataframe_name="df",
                reason="Test",
                storage_level="MEMORY_AND_DISK",
                estimated_reuse_count=3,
            )
        ]
        join_opts = [
            JoinOptimization(
                join_description="Test join",
                optimization_type="broadcast",
                reason="Small table",
            )
        ]
        
        cost_reduction = coding_agent._estimate_cost_reduction(
            partitioning_recs, caching_recs, join_opts
        )
        
        assert "%" in cost_reduction
        assert "reduction" in cost_reduction.lower()

    def test_optimization_comments_added_to_code(self, coding_agent, sample_parsed_requirements):
        """Test that optimization comments are added to generated code."""
        generated_code = GeneratedCode(
            main_pipeline_code="def process(): pass",
            input_schema_model=PydanticModel(
                model_name="Input", module_name="models", description="", code=""
            ),
            output_schema_model=PydanticModel(
                model_name="Output", module_name="models", description="", code=""
            ),
        )
        
        optimization_analysis = OptimizationAnalysis(
            overall_score=0.85,
            partitioning_recommendations=[
                PartitioningRecommendation(
                    columns=["date"],
                    reason="Temporal partitioning",
                    estimated_benefit="30% faster",
                    partition_type="range",
                )
            ],
            caching_recommendations=[
                CachingRecommendation(
                    dataframe_name="df",
                    reason="Multiple reuses",
                    storage_level="MEMORY_AND_DISK",
                    estimated_reuse_count=3,
                )
            ],
            join_optimizations=[],
            optimization_rules=[
                OptimizationRule(
                    rule_id="opt-001",
                    category="filter_pushdown",
                    priority="high",
                    title="Apply filters early",
                    description="Move filters early",
                    estimated_impact="40% faster",
                )
            ],
            estimated_cost_reduction="40-60% reduction",
        )
        
        optimized_code = coding_agent._add_optimization_comments(generated_code, optimization_analysis)
        
        assert "PERFORMANCE OPTIMIZATION RECOMMENDATIONS" in optimized_code.main_pipeline_code
        assert "Overall Optimization Score" in optimized_code.main_pipeline_code
        assert "PARTITIONING" in optimized_code.main_pipeline_code
        assert "CACHING" in optimized_code.main_pipeline_code
        assert "HIGH PRIORITY OPTIMIZATIONS" in optimized_code.main_pipeline_code
        assert "date" in optimized_code.main_pipeline_code  # Partitioning column

    def test_full_optimization_analysis_flow(self, coding_agent, sample_parsed_requirements):
        """Test complete optimization analysis workflow."""
        generated_code = GeneratedCode(
            main_pipeline_code="""
df = spark.read.parquet('data')
filtered = df.filter(col('order_date') > '2024-01-01')
joined = filtered.join(dim_products, on='product_id')
grouped = joined.groupBy('category').agg(sum('amount'))
            """,
            input_schema_model=PydanticModel(
                model_name="Input", module_name="models", description="", code=""
            ),
            output_schema_model=PydanticModel(
                model_name="Output", module_name="models", description="", code=""
            ),
        )
        
        optimization_analysis = coding_agent._analyze_optimizations(
            sample_parsed_requirements, generated_code
        )
        
        assert optimization_analysis is not None
        assert isinstance(optimization_analysis, OptimizationAnalysis)
        assert 0.0 <= optimization_analysis.overall_score <= 1.0
        assert optimization_analysis.estimated_cost_reduction is not None
        assert optimization_analysis.notes is not None