import pytest
from pyspark.sql import SparkSession
from pyspark.sql import DataFrame
from pyspark.sql.functions import col
from unittest.mock import patch
from main_pipeline import main
from models.input_schema import InputSchema
from models.output_schema import OutputSchema

@pytest.fixture(scope='module')
def spark():
    """Fixture for creating a SparkSession."""
    return SparkSession.builder.appName('test').getOrCreate()

@pytest.fixture
def sample_data(spark):
    """Fixture for creating sample input data."""
    data = [
        {'product_id': 'P001', 'supplier_id': 'S001', 'quantity_on_hand': 50, 'reorder_threshold': 30, 'status': 'active', 'warehouse_id': 'W001'},
        {'product_id': 'P002', 'supplier_id': 'S002', 'quantity_on_hand': 20, 'reorder_threshold': 25, 'status': 'inactive', 'warehouse_id': 'W002'},
    ]
    return spark.createDataFrame(data)

@pytest.mark.unit
def test_validate_schema(sample_data):
    """Test schema validation function."""
    from utils import validate_schema
    assert validate_schema(sample_data, InputSchema)

@pytest.mark.unit
@patch('main_pipeline.some_function')
def test_some_function(mock_some_function):
    """Test some_function with mocked dependencies."""
    mock_some_function.return_value = 'mocked_result'
    result = some_function()
    assert result == 'mocked_result'

@pytest.mark.integration
def test_pipeline_flow(spark, sample_data):
    """Integration test for the entire pipeline flow."""
    # Assuming main() is the entry point for the pipeline
    main()
    # Add assertions to verify the output
    # This is a placeholder for actual integration test logic

@pytest.mark.validation
def test_null_check_product_id(sample_data):
    """Ensure no NULL values in product_id column."""
    assert sample_data.filter(col('product_id').isNull()).count() == 0

@pytest.mark.validation
def test_null_check_supplier_id(sample_data):
    """Ensure no NULL values in supplier_id column."""
    assert sample_data.filter(col('supplier_id').isNull()).count() == 0

@pytest.mark.parametrize('quantity_on_hand, reorder_threshold, expected_flag', [
    (10, 20, True),
    (30, 20, False),
])
def test_reorder_flag_logic(quantity_on_hand, reorder_threshold, expected_flag):
    """Test reorder flag logic with different scenarios."""
    from pyspark.sql.functions import lit
    df = spark.createDataFrame([
        {'quantity_on_hand': quantity_on_hand, 'reorder_threshold': reorder_threshold}
    ])
    df = df.withColumn('reorder_flag', col('quantity_on_hand') < col('reorder_threshold'))
    assert df.collect()[0]['reorder_flag'] == expected_flag
