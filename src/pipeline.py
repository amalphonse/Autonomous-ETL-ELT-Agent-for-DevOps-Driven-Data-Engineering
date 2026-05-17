import logging
from datetime import datetime, timedelta
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, sum as spark_sum, count
from pyspark.sql.types import StructType, StructField, StringType, FloatType, TimestampType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def create_spark_session() -> SparkSession:
    """
    Create and configure a Spark session.

    Returns:
        SparkSession: Configured Spark session.
    """
    return SparkSession.builder \
        .appName('CustomerOrdersETL') \
        .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension') \
        .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog') \
        .getOrCreate()

def load_data(spark: SparkSession, path: str, schema: StructType) -> DataFrame:
    """
    Load data from a CSV file into a DataFrame.

    Args:
        spark (SparkSession): The Spark session.
        path (str): The path to the CSV file.
        schema (StructType): The schema of the data.

    Returns:
        DataFrame: Loaded DataFrame.
    """
    try:
        df = spark.read.format('csv').schema(schema).option('header', 'true').load(path)
        logger.info(f'Data loaded from {path}')
        return df
    except Exception as e:
        logger.error(f'Error loading data from {path}: {e}')
        raise

def filter_completed_orders(df: DataFrame) -> DataFrame:
    """
    Filter completed orders from the last 12 months.

    Args:
        df (DataFrame): The DataFrame containing customer orders.

    Returns:
        DataFrame: Filtered DataFrame.
    """
    try:
        one_year_ago = datetime.now() - timedelta(days=365)
        filtered_df = df.filter((col('order_status') == 'completed') & (col('order_date') > one_year_ago))
        logger.info('Filtered completed orders from the last 12 months')
        return filtered_df
    except Exception as e:
        logger.error(f'Error filtering completed orders: {e}')
        raise

def join_with_product_catalog(orders_df: DataFrame, products_df: DataFrame) -> DataFrame:
    """
    Join filtered orders with product catalog on product_id.

    Args:
        orders_df (DataFrame): The DataFrame of filtered orders.
        products_df (DataFrame): The DataFrame of product catalog.

    Returns:
        DataFrame: Joined DataFrame.
    """
    try:
        joined_df = orders_df.join(products_df, on='product_id', how='inner')
        logger.info('Joined orders with product catalog')
        return joined_df
    except Exception as e:
        logger.error(f'Error joining data: {e}')
        raise

def aggregate_data(df: DataFrame) -> DataFrame:
    """
    Aggregate data by product category to calculate total revenue and order count.

    Args:
        df (DataFrame): The DataFrame to aggregate.

    Returns:
        DataFrame: Aggregated DataFrame.
    """
    try:
        aggregated_df = df.groupBy('product_category').agg(
            spark_sum('order_amount').alias('total_revenue'),
            count('order_id').alias('order_count')
        )
        logger.info('Aggregated data by product category')
        return aggregated_df
    except Exception as e:
        logger.error(f'Error aggregating data: {e}')
        raise

def write_to_snowflake(df: DataFrame):
    """
    Write the aggregated data to Snowflake.

    Args:
        df (DataFrame): The DataFrame to write.
    """
    try:
        # Placeholder for Snowflake write logic
        df.write.format('snowflake').option('dbtable', 'analytics_summary').mode('overwrite').save()
        logger.info('Data written to Snowflake analytics_summary table')
    except Exception as e:
        logger.error(f'Error writing data to Snowflake: {e}')
        raise

def main():
    """
    Main ETL pipeline execution function.
    """
    spark = create_spark_session()

    # Define schemas
    orders_schema = StructType([
        StructField('order_id', StringType(), False),
        StructField('product_id', StringType(), False),
        StructField('order_amount', FloatType(), False),
        StructField('order_status', StringType(), False),
        StructField('order_date', TimestampType(), False)
    ])

    products_schema = StructType([
        StructField('product_id', StringType(), False),
        StructField('product_category', StringType(), False)
    ])

    # Load data
    orders_df = load_data(spark, 's3://path/to/customer_orders', orders_schema)
    products_df = load_data(spark, 's3://path/to/product_catalog', products_schema)

    # Apply transformations
    filtered_orders_df = filter_completed_orders(orders_df)
    joined_df = join_with_product_catalog(filtered_orders_df, products_df)
    aggregated_df = aggregate_data(joined_df)

    # Write results
    write_to_snowflake(aggregated_df)

    spark.stop()

if __name__ == '__main__':
    main()