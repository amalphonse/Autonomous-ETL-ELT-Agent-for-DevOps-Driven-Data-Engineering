import pytest
from pyspark.sql import SparkSession
from pyspark.sql import Row
from pyspark.sql.utils import AnalysisException
from unittest.mock import patch

@pytest.fixture(scope='module')
def spark():
    """Fixture for creating a Spark session for testing."""
    return SparkSession.builder.master('local').appName('test').getOrCreate()

@pytest.fixture
def sample_sales_data(spark):
    """Fixture for creating sample sales data."""
    return spark.createDataFrame([
        Row(transaction_id='1', store_id='A', transaction_date='2023-10-01', amount=150.0),
        Row(transaction_id='2', store_id='B', transaction_date='2023-10-01', amount=250.0),
        Row(transaction_id='3', store_id='A', transaction_date='2023-10-02', amount=300.0),
        Row(transaction_id='4', store_id='B', transaction_date='2023-10-02', amount=400.0),
        Row(transaction_id='5', store_id='A', transaction_date='2023-10-03', amount=500.0),
        Row(transaction_id='6', store_id='B', transaction_date='2023-10-03', amount=600.0)
    ])

@pytest.fixture
def sample_store_locations(spark):
    """Fixture for creating sample store locations data."""
    return spark.createDataFrame([
        Row(store_id='A', region='North'),
        Row(store_id='B', region='South')
    ])

@pytest.mark.unit
def test_deduplication(sample_sales_data):
    """Test deduplication step to ensure unique transaction_id."""
    deduped_df = sample_sales_data.dropDuplicates(['transaction_id'])
    assert deduped_df.count() == sample_sales_data.count()

@pytest.mark.unit
def test_join_with_store_locations(spark, sample_sales_data, sample_store_locations):
    """Test joining sales data with store locations."""
    joined_df = sample_sales_data.join(sample_store_locations, on='store_id', how='inner')
    assert 'region' in joined_df.columns
    assert joined_df.count() == sample_sales_data.count()

@pytest.mark.integration
def test_pipeline_flow(spark, sample_sales_data, sample_store_locations):
    """Integration test for the entire pipeline flow."""
    # Deduplication
    deduped_df = sample_sales_data.dropDuplicates(['transaction_id'])
    # Join with store locations
    joined_df = deduped_df.join(sample_store_locations, on='store_id', how='inner')
    # Further steps would go here...
    assert joined_df.count() == deduped_df.count()

@pytest.mark.validation
def test_transaction_id_uniqueness(sample_sales_data):
    """Validate uniqueness of transaction_id after deduplication."""
    deduped_df = sample_sales_data.dropDuplicates(['transaction_id'])
    assert deduped_df.count() == sample_sales_data.count()

@pytest.mark.validation
def test_amount_not_null(sample_sales_data):
    """Validate that transaction amount is not null."""
    assert sample_sales_data.filter(sample_sales_data.amount.isNull()).count() == 0

@pytest.mark.parametrize('transaction_id,expected', [
    ('1', True),
    ('7', False)
])
def test_transaction_id_existence(sample_sales_data, transaction_id, expected):
    """Test for existence of specific transaction_id."""
    assert (sample_sales_data.filter(sample_sales_data.transaction_id == transaction_id).count() > 0) == expected

@pytest.mark.unit
def test_error_handling(spark):
    """Test error handling for invalid operations."""
    with pytest.raises(AnalysisException):
        spark.sql("SELECT * FROM non_existent_table")
