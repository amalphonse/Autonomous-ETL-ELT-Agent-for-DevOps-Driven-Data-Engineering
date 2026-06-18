import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, avg, sum as spark_sum, row_number
from pyspark.sql.window import Window
from pyspark.sql.utils import AnalysisException
from pyspark.sql.types import StructType, StructField, StringType, TimestampType, FloatType

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spark session
spark = SparkSession.builder \
    .appName('DailySalesRevenueReport') \
    .config('spark.jars.packages', 'io.delta:delta-core_2.12:1.0.0') \
    .getOrCreate()

# Define schemas
sales_transactions_schema = StructType([
    StructField('transaction_id', StringType(), False),
    StructField('store_id', StringType(), False),
    StructField('transaction_date', TimestampType(), False),
    StructField('amount', FloatType(), False)
])

store_locations_schema = StructType([
    StructField('store_id', StringType(), False),
    StructField('region', StringType(), False)
])


def load_sales_transactions() -> DataFrame:
    """
    Load sales transactions from S3 Parquet files.
    Returns:
        DataFrame: Spark DataFrame containing sales transactions.
    """
    try:
        df = spark.read.schema(sales_transactions_schema).parquet('s3://bucket-name/path/to/sales_transactions')
        logger.info('Sales transactions loaded successfully.')
        return df
    except Exception as e:
        logger.error(f'Error loading sales transactions: {e}')
        raise


def load_store_locations() -> DataFrame:
    """
    Load store locations from PostgreSQL.
    Returns:
        DataFrame: Spark DataFrame containing store locations.
    """
    try:
        df = spark.read.format('jdbc') \
            .option('url', 'jdbc:postgresql://your-postgres-url') \
            .option('dbtable', 'public.store_locations') \
            .option('user', 'your-username') \
            .option('password', 'your-password') \
            .load()
        logger.info('Store locations loaded successfully.')
        return df
    except Exception as e:
        logger.error(f'Error loading store locations: {e}')
        raise


def deduplicate_transactions(df: DataFrame) -> DataFrame:
    """
    Deduplicate transactions based on transaction_id.
    Args:
        df (DataFrame): Input DataFrame with sales transactions.
    Returns:
        DataFrame: Deduplicated DataFrame.
    """
    deduped_df = df.dropDuplicates(['transaction_id'])
    logger.info('Transactions deduplicated.')
    return deduped_df


def join_with_store_locations(transactions_df: DataFrame, locations_df: DataFrame) -> DataFrame:
    """
    Join sales transactions with store locations to get region info.
    Args:
        transactions_df (DataFrame): Sales transactions DataFrame.
        locations_df (DataFrame): Store locations DataFrame.
    Returns:
        DataFrame: Joined DataFrame with region info.
    """
    joined_df = transactions_df.join(locations_df, on='store_id', how='inner')
    logger.info('Joined transactions with store locations.')
    return joined_df


def calculate_moving_average(df: DataFrame) -> DataFrame:
    """
    Calculate 7-day moving average revenue per region.
    Args:
        df (DataFrame): Joined DataFrame with region info.
    Returns:
        DataFrame: DataFrame with moving average revenue per region.
    """
    window_spec = Window.partitionBy('region').orderBy('transaction_date').rowsBetween(-6, 0)
    df_with_moving_avg = df.withColumn('moving_avg_revenue', avg('amount').over(window_spec))
    logger.info('Calculated 7-day moving average revenue.')
    return df_with_moving_avg


def filter_regions(df: DataFrame) -> DataFrame:
    """
    Filter for regions with moving_avg_revenue above $10000.
    Args:
        df (DataFrame): DataFrame with moving average revenue.
    Returns:
        DataFrame: Filtered DataFrame.
    """
    filtered_df = df.filter(col('moving_avg_revenue') > 10000)
    logger.info('Filtered regions with moving average revenue above $10000.')
    return filtered_df


def rank_stores(df: DataFrame) -> DataFrame:
    """
    Rank stores within each region by total daily sales.
    Args:
        df (DataFrame): Filtered DataFrame.
    Returns:
        DataFrame: DataFrame with ranked stores.
    """
    daily_sales_df = df.groupBy('region', 'store_id').agg(spark_sum('amount').alias('total_daily_sales'))
    window_spec = Window.partitionBy('region').orderBy(col('total_daily_sales').desc())
    ranked_df = daily_sales_df.withColumn('rank_within_region', row_number().over(window_spec))
    logger.info('Ranked stores within each region.')
    return ranked_df


def write_to_redshift(df: DataFrame) -> None:
    """
    Write the top-ranked stores per region to Redshift.
    Args:
        df (DataFrame): DataFrame with ranked stores.
    """
    try:
        df.write \
            .format('jdbc') \
            .option('url', 'jdbc:redshift://your-redshift-url') \
            .option('dbtable', 'reporting.daily_sales_summary') \
            .option('user', 'your-username') \
            .option('password', 'your-password') \
            .mode('overwrite') \
            .save()
        logger.info('Data written to Redshift successfully.')
    except Exception as e:
        logger.error(f'Error writing to Redshift: {e}')
        raise


def main() -> None:
    """
    Main function to execute the pipeline.
    """
    try:
        sales_transactions_df = load_sales_transactions()
        store_locations_df = load_store_locations()

        deduped_transactions_df = deduplicate_transactions(sales_transactions_df)
        joined_df = join_with_store_locations(deduped_transactions_df, store_locations_df)
        moving_avg_df = calculate_moving_average(joined_df)
        filtered_df = filter_regions(moving_avg_df)
        ranked_stores_df = rank_stores(filtered_df)

        write_to_redshift(ranked_stores_df)
    except AnalysisException as ae:
        logger.error(f'AnalysisException occurred: {ae}')
    except Exception as e:
        logger.error(f'An unexpected error occurred: {e}')
    finally:
        spark.stop()


if __name__ == '__main__':
    main()