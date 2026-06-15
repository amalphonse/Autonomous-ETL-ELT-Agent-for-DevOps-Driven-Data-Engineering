from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, expr, sum as spark_sum
import logging
from typing import Tuple

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_spark_session() -> SparkSession:
    """
    Create and return a Spark session.
    """
    try:
        spark = SparkSession.builder \
            .appName('ProductInventorySync') \
            .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension') \
            .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog') \
            .getOrCreate()
        logger.info('Spark session created successfully.')
        return spark
    except Exception as e:
        logger.error(f'Error creating Spark session: {e}')
        raise


def load_data(spark: SparkSession) -> Tuple[DataFrame, DataFrame]:
    """
    Load data from PostgreSQL tables.
    """
    try:
        inventory_snapshots = spark.read.format('jdbc') \
            .option('url', 'jdbc:postgresql://your_postgres_url') \
            .option('dbtable', 'public.inventory_snapshots') \
            .option('user', 'your_user') \
            .option('password', 'your_password') \
            .load()

        supplier_catalog = spark.read.format('jdbc') \
            .option('url', 'jdbc:postgresql://your_postgres_url') \
            .option('dbtable', 'public.supplier_catalog') \
            .option('user', 'your_user') \
            .option('password', 'your_password') \
            .load()

        logger.info('Data loaded successfully from PostgreSQL.')
        return inventory_snapshots, supplier_catalog
    except Exception as e:
        logger.error(f'Error loading data: {e}')
        raise


def join_data(inventory_snapshots: DataFrame, supplier_catalog: DataFrame) -> DataFrame:
    """
    Join inventory snapshots with supplier catalog on supplier_id.
    """
    try:
        joined_data = inventory_snapshots.join(supplier_catalog, on='supplier_id', how='inner')
        logger.info('Data joined successfully.')
        return joined_data
    except Exception as e:
        logger.error(f'Error joining data: {e}')
        raise


def filter_inactive_products(joined_data: DataFrame) -> DataFrame:
    """
    Filter out discontinued products where status = 'inactive'.
    """
    try:
        filtered_data = joined_data.filter(col('status') != 'inactive')
        logger.info('Inactive products filtered out.')
        return filtered_data
    except Exception as e:
        logger.error(f'Error filtering inactive products: {e}')
        raise


def calculate_reorder_flag(filtered_data: DataFrame) -> DataFrame:
    """
    Calculate reorder_flag for items where quantity_on_hand is below reorder_threshold.
    """
    try:
        reorder_flag_data = filtered_data.withColumn('reorder_flag', expr('quantity_on_hand < reorder_threshold'))
        logger.info('Reorder flag calculated.')
        return reorder_flag_data
    except Exception as e:
        logger.error(f'Error calculating reorder flag: {e}')
        raise


def aggregate_inventory_value(reorder_flag_data: DataFrame) -> DataFrame:
    """
    Aggregate total inventory value per warehouse.
    """
    try:
        aggregated_data = reorder_flag_data.groupBy('warehouse_id').agg(
            spark_sum(expr('quantity_on_hand * unit_cost')).alias('total_inventory_value')
        )
        logger.info('Inventory value aggregated per warehouse.')
        return aggregated_data
    except Exception as e:
        logger.error(f'Error aggregating inventory value: {e}')
        raise


def write_data(aggregated_data: DataFrame):
    """
    Write the result to Snowflake.
    """
    try:
        aggregated_data.write.format('snowflake') \
            .option('sfURL', 'your_snowflake_url') \
            .option('sfDatabase', 'analytics') \
            .option('sfSchema', 'public') \
            .option('sfWarehouse', 'your_warehouse') \
            .option('sfRole', 'your_role') \
            .option('sfUser', 'your_user') \
            .option('sfPassword', 'your_password') \
            .option('dbtable', 'warehouse_inventory_summary') \
            .mode('overwrite') \
            .save()
        logger.info('Data written to Snowflake successfully.')
    except Exception as e:
        logger.error(f'Error writing data to Snowflake: {e}')
        raise


def main():
    """
    Main function to execute the pipeline.
    """
    try:
        spark = create_spark_session()
        inventory_snapshots, supplier_catalog = load_data(spark)
        joined_data = join_data(inventory_snapshots, supplier_catalog)
        filtered_data = filter_inactive_products(joined_data)
        reorder_flag_data = calculate_reorder_flag(filtered_data)
        aggregated_data = aggregate_inventory_value(reorder_flag_data)
        write_data(aggregated_data)
    except Exception as e:
        logger.error(f'Pipeline execution failed: {e}')
        raise


if __name__ == '__main__':
    main()