"""End-to-end tests for data lineage extraction and tracking."""

import pytest
import json
from src.lineage.extractor import LineageExtractor
from src.lineage.emitter import LineageEmitter
from src.lineage.models import Dataset, Transformation, PipelineLineage


class TestLineageExtractor:
    """Test LineageExtractor functionality."""

    def test_extract_read_operations(self):
        """Test extraction of read operations (source datasets)."""
        code = """
spark.read.csv("s3://data-bucket/customers.csv").show()
df_orders = spark.read.parquet("s3://data-bucket/orders.parquet")
"""
        extractor = LineageExtractor(execution_id="test-123", pipeline_name="test_pipeline")
        lineage = extractor.extract(code)

        assert len(lineage.sources) == 2
        assert "customers" in lineage.sources
        assert "orders" in lineage.sources

    def test_extract_write_operations(self):
        """Test extraction of write operations (target datasets)."""
        code = """
df.write.format("parquet").mode("overwrite").save("s3://data-lake/output.parquet")
result_df.write.format("csv").save("s3://output/results.csv")
"""
        extractor = LineageExtractor(execution_id="test-124", pipeline_name="test_pipeline")
        lineage = extractor.extract(code)

        assert len(lineage.targets) >= 1
        assert any("output" in t for t in lineage.targets)

    def test_extract_filter_transformation(self):
        """Test extraction of filter operations."""
        code = """
df_customers = spark.read.parquet("s3://data/customers.parquet")
df_filtered = df_customers.filter("age > 18")
"""
        extractor = LineageExtractor(execution_id="test-125", pipeline_name="test_pipeline")
        lineage = extractor.extract(code)

        # Should have 1 source and 1 transformation
        assert len(lineage.sources) >= 1
        assert len(lineage.transformations) >= 1

        # Check transformation details
        filter_trans = [t for t in lineage.transformations if t.operation == "filter"]
        assert len(filter_trans) > 0

    def test_extract_join_transformation(self):
        """Test extraction of join operations."""
        code = """
df_customers = spark.read.parquet("s3://data/customers.parquet")
df_orders = spark.read.parquet("s3://data/orders.parquet")
df_joined = df_customers.join(df_orders, on="customer_id")
"""
        extractor = LineageExtractor(execution_id="test-126", pipeline_name="test_pipeline")
        lineage = extractor.extract(code)

        # Should have 2 sources
        assert len(lineage.sources) >= 2

        # Should have join transformation
        join_trans = [t for t in lineage.transformations if t.operation == "join"]
        assert len(join_trans) > 0
        
        if join_trans:
            assert len(join_trans[0].inputs) == 2  # Two inputs to join

    def test_extract_aggregate_transformation(self):
        """Test extraction of aggregate operations."""
        code = """
df_orders = spark.read.parquet("s3://data/orders.parquet")
df_aggregated = df_orders.groupBy("customer_id").agg(sum("amount"))
"""
        extractor = LineageExtractor(execution_id="test-127", pipeline_name="test_pipeline")
        lineage = extractor.extract(code)

        # Should have aggregation transformation
        agg_trans = [t for t in lineage.transformations if t.operation == "aggregate"]
        assert len(agg_trans) > 0

    def test_extract_complete_pipeline(self):
        """Test extraction from a complete multi-step pipeline."""
        code = """
# Load data
df_customers = spark.read.parquet("s3://data/customers.parquet")
df_orders = spark.read.parquet("s3://data/orders.parquet")

# Transform: Filter
df_customers_filtered = df_customers.filter("status = 'active'")

# Transform: Join
df_joined = df_customers_filtered.join(df_orders, on="customer_id")

# Transform: Aggregate
df_summary = df_joined.groupBy("customer_id").agg({"amount": "sum"})

# Write results
df_summary.write.format("parquet").mode("overwrite").save("s3://output/customer_summary.parquet")
"""
        extractor = LineageExtractor(execution_id="test-128", pipeline_name="customer_summary")
        lineage = extractor.extract(code)

        # Verify sources extracted
        assert len(lineage.sources) >= 2
        assert "customers" in lineage.sources
        assert "orders" in lineage.sources

        # Verify targets extracted
        assert len(lineage.targets) >= 1
        assert any("customer_summary" in t for t in lineage.targets)

        # Verify transformations extracted
        assert len(lineage.transformations) >= 3


class TestLineageEmitter:
    """Test LineageEmitter functionality."""

    def test_emit_start_event(self):
        """Test emitting START events."""
        emitter = LineageEmitter(execution_id="test-exec-1", backend="local")
        emitter.emit_start(
            pipeline_name="test_pipeline",
            inputs=["customers", "orders"]
        )

        assert len(emitter.events) == 1
        assert emitter.events[0].event_type == "START"
        assert emitter.events[0].execution_id == "test-exec-1"

    def test_emit_complete_event(self):
        """Test emitting COMPLETE events."""
        emitter = LineageEmitter(execution_id="test-exec-2", backend="local")
        emitter.emit_complete(
            pipeline_name="test_pipeline",
            inputs=["customers", "orders"],
            outputs=["customer_summary"],
            status="success"
        )

        assert len(emitter.events) == 1
        assert emitter.events[0].event_type == "COMPLETE"
        assert emitter.events[0].status == "success"

    def test_openlineage_event_format(self):
        """Test OpenLineage event format."""
        emitter = LineageEmitter(execution_id="test-exec-3", backend="local")
        emitter.emit_complete(
            pipeline_name="etl_pipeline",
            inputs=["input_data"],
            outputs=["output_data"],
            status="success"
        )

        event_dict = emitter.get_emitted_events()[0]

        # Verify OpenLineage schema compliance
        assert "eventType" in event_dict
        assert "eventTime" in event_dict
        assert "producer" in event_dict
        assert "run" in event_dict
        assert "job" in event_dict
        assert "inputs" in event_dict
        assert "outputs" in event_dict

        assert event_dict["eventType"] == "COMPLETE"
        assert event_dict["producer"] == "etl-agent"
        assert len(event_dict["inputs"]) == 1
        assert len(event_dict["outputs"]) == 1


class TestLineageModels:
    """Test serialization and model functionality."""

    def test_pipeline_lineage_to_dict(self):
        """Test PipelineLineage serialization."""
        lineage = PipelineLineage(
            execution_id="test-1",
            pipeline_name="test_pipeline"
        )

        # Add datasets
        customers = Dataset(
            name="customers",
            namespace="input",
            location="s3://data/customers.parquet",
            source_type="parquet"
        )
        lineage.datasets["customers"] = customers
        lineage.sources.append("customers")

        # Add transformation
        trans = Transformation(
            name="filter_active",
            operation="filter",
            inputs=["customers"],
            outputs=["active_customers"]
        )
        lineage.transformations.append(trans)

        # Serialize
        lineage_dict = lineage.to_dict()

        assert lineage_dict["execution_id"] == "test-1"
        assert lineage_dict["pipeline_name"] == "test_pipeline"
        assert "customers" in lineage_dict["datasets"]
        assert len(lineage_dict["transformations"]) == 1
        assert lineage_dict["sources"] == ["customers"]

    def test_pipeline_lineage_json_serializable(self):
        """Test that lineage can be JSON serialized."""
        lineage = PipelineLineage(
            execution_id="test-2",
            pipeline_name="test_pipeline"
        )

        customers = Dataset(
            name="customers",
            namespace="input",
            location="s3://data/customers.parquet"
        )
        lineage.datasets["customers"] = customers
        lineage.sources.append("customers")

        # Should be JSON serializable
        lineage_dict = lineage.to_dict()
        json_str = json.dumps(lineage_dict, default=str)
        
        assert len(json_str) > 0
        parsed = json.loads(json_str)
        assert parsed["execution_id"] == "test-2"


class TestLineageIntegration:
    """Integration tests for lineage extraction and emission."""

    def test_extract_and_emit_complete_pipeline(self):
        """Test full lineage extraction and emission workflow."""
        # Sample PySpark code
        code = """
from pyspark.sql import SparkSession

spark = SparkSession.builder.appName("etl_pipeline").getOrCreate()

# Read source data
df_customers = spark.read.parquet("s3://data-bucket/customers.parquet")
df_transactions = spark.read.parquet("s3://data-bucket/transactions.parquet")

# Filter active customers
df_active = df_customers.filter("status = 'active'")

# Join with transactions
df_joined = df_active.join(df_transactions, on="customer_id")

# Calculate totals
df_summary = df_joined.groupBy("customer_id", "region").agg({
    "amount": "sum",
    "transaction_count": "count"
})

# Write output
df_summary.write.format("parquet").mode("overwrite").save("s3://output-bucket/customer_summary.parquet")
"""

        # Extract lineage
        extractor = LineageExtractor(
            execution_id="integration-test-1",
            pipeline_name="customer_analytics"
        )
        lineage = extractor.extract(code)

        # Verify extraction
        assert len(lineage.sources) >= 2
        assert len(lineage.targets) >= 1
        assert len(lineage.transformations) >= 2

        # Emit lineage
        emitter = LineageEmitter(
            execution_id="integration-test-1",
            backend="local"
        )
        emitter.emit_start(
            pipeline_name="customer_analytics",
            inputs=lineage.sources
        )
        emitter.emit_lineage(lineage)
        emitter.emit_complete(
            pipeline_name="customer_analytics",
            inputs=lineage.sources,
            outputs=lineage.targets,
            status="success"
        )

        # Verify emission
        events = emitter.get_emitted_events()
        assert len(events) >= 2  # At least START and COMPLETE


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
