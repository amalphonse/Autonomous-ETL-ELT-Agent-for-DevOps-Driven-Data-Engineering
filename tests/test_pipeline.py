
import pytest
from pyspark.sql import SparkSession
from pyspark.sql import Row
from pyspark.sql.functions import col
from unittest.mock import MagicMock
from main_pipeline import create_spark_session, filter_completed_orders, join_with_product_catalog, aggregate_by_product_category

@pytest.fixture(scope='module')
def spark():
    """
    Fixture for creating a Spark session for testing.
    """
    return SparkSession.builder.master('local').appName('test').getOrCreate()

@pytest.fixture
def sample_orders_data(spark):
    """
    Fixture for creating sample orders data.
    """
    data = [
        Row(order_id='1', product_id='101', order_amount=100.0, order_status='completed', order_date='2022-01-01'),
        Row(order_id='2', product_id='102', order_amount=200.0, order_status='pending', order_date='2022-06-01'),
        Row(order_id='3', product_id='101', order_amount=150.0, order_status='completed', order_date='2023-01-01')
    ]
    return spark.createDataFrame(data)

@pytest.fixture
def sample_product_catalog_data(spark):
    """
    Fixture for creating sample product catalog data.
    """
    data = [
        Row(product_id='101', product_category='Electronics'),
        Row(product_id='102', product_category='Books')
    ]
    return spark.createDataFrame(data)

@pytest.mark.unit
def test_create_spark_session():
    """
    Test Spark session creation.
    """
    spark = create_spark_session()
    assert isinstance(spark, SparkSession)

@pytest.mark.unit
def test_filter_completed_orders(spark, sample_orders_data):
    """
    Test filtering of completed orders from the last 12 months.
    """
    filtered_df = filter_completed_orders(sample_orders_data)
    assert filtered_df.count() == 2
    assert all(row['order_status'] == 'completed' for row in filtered_df.collect())

@pytest.mark.unit
def test_join_with_product_catalog(spark, sample_orders_data, sample_product_catalog_data):
    """
    Test joining orders with product catalog.
    """
    filtered_orders = filter_completed_orders(sample_orders_data)
    joined_df = join_with_product_catalog(filtered_orders, sample_product_catalog_data)
    assert joined_df.count() == 2
    assert 'product_category' in joined_df.columns

@pytest.mark.unit
def test_aggregate_by_product_category(spark, sample_orders_data, sample_product_catalog_data):
    """
    Test aggregation by product category.
    """
    filtered_orders = filter_completed_orders(sample_orders_data)
    joined_df = join_with_product_catalog(filtered_orders, sample_product_catalog_data)
    aggregated_df = aggregate_by_product_category(joined_df)
    assert aggregated_df.count() == 1
    assert aggregated_df.filter(col('product_category') == 'Electronics').count() == 1

@pytest.mark.integration
def test_pipeline_integration(spark, sample_orders_data, sample_product_catalog_data):
    """
    Integration test for the entire pipeline.
    """
    filtered_orders = filter_completed_orders(sample_orders_data)
    joined_df = join_with_product_catalog(filtered_orders, sample_product_catalog_data)
    aggregated_df = aggregate_by_product_category(joined_df)
    assert aggregated_df.count() == 1
    assert aggregated_df.filter(col('product_category') == 'Electronics').count() == 1

@pytest.mark.validation
def test_null_check_order_id(spark, sample_orders_data):
    """
    Validation test to ensure order_id is not null.
    """
    assert sample_orders_data.filter(col('order_id').isNull()).count() == 0

@pytest.mark.validation
def test_null_check_product_id(spark, sample_orders_data):
    """
    Validation test to ensure product_id is not null.
    """
    assert sample_orders_data.filter(col('product_id').isNull()).count() == 0

@pytest.mark.validation
def test_order_amount_positive(spark, sample_orders_data):
    """
    Validation test to ensure order_amount is greater than 0.
    """
    assert sample_orders_data.filter(col('order_amount') <= 0).count() == 0
