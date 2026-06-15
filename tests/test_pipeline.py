import pytest
from pyspark.sql import SparkSession
from pyspark.sql import DataFrame
from unittest.mock import MagicMock

@pytest.fixture(scope='module')
def spark():
    """Fixture for creating a Spark session for testing."""
    return SparkSession.builder.appName('test').getOrCreate()

@pytest.fixture
def sample_data(spark):
    """Fixture for creating sample data for testing."""
    data = [
        ('prod_1', 'supp_1', 10, 5, 'active', 'wh_1'),
        ('prod_2', 'supp_2', 3, 5, 'inactive', 'wh_2'),
        ('prod_3', 'supp_1', 0, 2, 'active', 'wh_1')
    ]
    schema = ['product_id', 'supplier_id', 'quantity_on_hand', 'reorder_threshold', 'status', 'warehouse_id']
    return spark.createDataFrame(data, schema)

@pytest.mark.unit
def test_create_spark_session():
    """Test the creation of a Spark session."""
    spark = create_spark_session()
    assert spark is not None
    assert isinstance(spark, SparkSession)

@pytest.mark.unit
def test_join_data(sample_data, spark):
    """Test the join operation between inventory snapshots and supplier catalog."""
    supplier_data = [('supp_1', 2, 10.0), ('supp_2', 3, 15.0)]
    supplier_schema = ['supplier_id', 'lead_time', 'unit_cost']
    supplier_df = spark.createDataFrame(supplier_data, supplier_schema)

    # Mock join operation
    joined_data = sample_data.join(supplier_df, on='supplier_id', how='inner')
    assert joined_data.count() == 2

@pytest.mark.integration
def test_pipeline_flow(sample_data, spark):
    """Integration test for the entire pipeline flow."""
    # Assume pipeline function is defined
    result_df = pipeline_function(sample_data)
    assert result_df.count() > 0
    assert 'total_inventory_value' in result_df.columns

@pytest.mark.validation
def test_null_check_product_id(sample_data):
    """Validation test to ensure no NULL values in product_id."""
    null_count = sample_data.filter(sample_data.product_id.isNull()).count()
    assert null_count == 0

@pytest.mark.validation
def test_null_check_supplier_id(sample_data):
    """Validation test to ensure no NULL values in supplier_id."""
    null_count = sample_data.filter(sample_data.supplier_id.isNull()).count()
    assert null_count == 0
