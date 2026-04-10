import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, when, sum as spark_sum
from pyspark.sql.types import BooleanType
from models.input_schema import InputSchema
from models.output_schema import OutputSchema
from utils import validate_schema

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:
    """
    Main function to execute the product inventory sync pipeline.
    """
    try:
        spark = SparkSession.builder \
            .appName('ProductInventorySync') \
            .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension') \
            .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog') \
            .getOrCreate()

        inventory_snapshots = load_inventory_snapshots(spark)
        supplier_catalog = load_supplier_catalog(spark)

        enriched_inventory = join_inventory_with_catalog(inventory_snapshots, supplier_catalog)
        active_inventory = filter_inactive_products(enriched_inventory)
        inventory_with_reorder_flag = calculate_reorder_flag(active_inventory)
        warehouse_inventory_summary = aggregate_inventory_value(inventory_with_reorder_flag)

        save_to_snowflake(warehouse_inventory_summary)

    except Exception as e:
        logger.error(f"Error in main pipeline: {e}")
        raise


def load_inventory_snapshots(spark: SparkSession) -> DataFrame:
    """
    Load inventory snapshots from PostgreSQL.
    """
    logger.info("Loading inventory snapshots from PostgreSQL")
    # Placeholder for actual data loading logic
    return spark.read.format('jdbc').options(
        url='jdbc:postgresql://your_postgres_url',
        dbtable='public.inventory_snapshots',
        user='your_username',
        password='your_password'
    ).load()


def load_supplier_catalog(spark: SparkSession) -> DataFrame:
    """
    Load supplier catalog from PostgreSQL.
    """
    logger.info("Loading supplier catalog from PostgreSQL")
    # Placeholder for actual data loading logic
    return spark.read.format('jdbc').options(
        url='jdbc:postgresql://your_postgres_url',
        dbtable='public.supplier_catalog',
        user='your_username',
        password='your_password'
    ).load()


def join_inventory_with_catalog(inventory_snapshots: DataFrame, supplier_catalog: DataFrame) -> DataFrame:
    """
    Join inventory snapshots with supplier catalog on supplier_id.
    """
    logger.info("Joining inventory snapshots with supplier catalog")
    return inventory_snapshots.join(supplier_catalog, on='supplier_id', how='inner')


def filter_inactive_products(enriched_inventory: DataFrame) -> DataFrame:
    """
    Filter out inactive products.
    """
    logger.info("Filtering out inactive products")
    return enriched_inventory.filter(col('status') != 'inactive')


def calculate_reorder_flag(active_inventory: DataFrame) -> DataFrame:
    """
    Calculate reorder flag for products.
    """
    logger.info("Calculating reorder flags")
    return active_inventory.withColumn('reorder_flag', (col('quantity_on_hand') < col('reorder_threshold')).cast(BooleanType()))


def aggregate_inventory_value(inventory_with_reorder_flag: DataFrame) -> DataFrame:
    """
    Aggregate total inventory value per warehouse.
    """
    logger.info("Aggregating total inventory value per warehouse")
    return inventory_with_reorder_flag.groupBy('warehouse_id').agg(
        spark_sum(col('quantity_on_hand') * col('unit_cost')).alias('total_inventory_value')
    )


def save_to_snowflake(df: DataFrame) -> None:
    """
    Save the result to Snowflake.
    """
    logger.info("Saving results to Snowflake")
    # Placeholder for actual Snowflake saving logic
    df.write.format('snowflake').options(
        sfURL='your_snowflake_url',
        sfDatabase='analytics',
        sfSchema='public',
        sfWarehouse='your_warehouse',
        sfRole='your_role',
        sfUser='your_user',
        sfPassword='your_password',
        dbtable='warehouse_inventory_summary'
    ).mode('overwrite').save()


if __name__ == '__main__':
    main()