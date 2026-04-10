import logging
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json, sum as spark_sum, count, window
from pyspark.sql.types import StructType, StructField, StringType, TimestampType
from pyspark.sql.utils import AnalysisException
from pyspark.sql.streaming import DataStreamWriter

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Define schemas
user_events_schema = StructType([
    StructField('event_id', StringType(), nullable=False),
    StructField('event_payload', StringType(), nullable=False),
    StructField('event_timestamp', TimestampType(), nullable=False)
])

users_schema = StructType([
    StructField('user_id', StringType(), nullable=False),
    StructField('subscription_tier', StringType(), nullable=False),
    StructField('country', StringType(), nullable=True)
])


def main() -> None:
    """
    Main function to execute the user behavior analytics pipeline.
    """
    try:
        spark = SparkSession.builder \
            .appName('UserBehaviorAnalytics') \
            .config('spark.sql.extensions', 'io.delta.sql.DeltaSparkSessionExtension') \
            .config('spark.sql.catalog.spark_catalog', 'org.apache.spark.sql.delta.catalog.DeltaCatalog') \
            .getOrCreate()

        # Read user events from Kafka
        user_events = read_user_events(spark)

        # Read users data from PostgreSQL
        users = read_users_data(spark)

        # Process pipeline
        user_engagement_metrics = process_pipeline(user_events, users)

        # Write results to BigQuery
        write_to_bigquery(user_engagement_metrics)

    except Exception as e:
        logger.error(f"Pipeline execution failed: {e}")
    finally:
        spark.stop()


def read_user_events(spark: SparkSession) -> DataFrame:
    """
    Read user events from Kafka.

    :param spark: SparkSession instance
    :return: DataFrame containing user events
    """
    try:
        return spark.readStream \
            .format('kafka') \
            .option('kafka.bootstrap.servers', 'localhost:9092') \
            .option('subscribe', 'kafka.topic.user_events') \
            .load() \
            .selectExpr('CAST(value AS STRING) as json') \
            .select(from_json(col('json'), user_events_schema).alias('data')) \
            .select('data.*')
    except AnalysisException as e:
        logger.error(f"Error reading user events from Kafka: {e}")
        raise


def read_users_data(spark: SparkSession) -> DataFrame:
    """
    Read users data from PostgreSQL.

    :param spark: SparkSession instance
    :return: DataFrame containing users data
    """
    try:
        return spark.read \
            .format('jdbc') \
            .option('url', 'jdbc:postgresql://localhost:5432/mydb') \
            .option('dbtable', 'public.users') \
            .option('user', 'username') \
            .option('password', 'password') \
            .load()
    except AnalysisException as e:
        logger.error(f"Error reading users data from PostgreSQL: {e}")
        raise


def process_pipeline(user_events: DataFrame, users: DataFrame) -> DataFrame:
    """
    Process the pipeline to compute user engagement metrics.

    :param user_events: DataFrame of user events
    :param users: DataFrame of users
    :return: DataFrame with user engagement metrics
    """
    # Step 1: Parse event_payload
    parsed_events = parse_event_payload(user_events)

    # Step 2: Deduplicate events
    deduplicated_events = deduplicate_events(parsed_events)

    # Step 3: Join with users
    enriched_events = join_with_users(deduplicated_events, users)

    # Step 4: Filter by subscription tier
    filtered_events = filter_by_subscription(enriched_events)

    # Step 5: Aggregate metrics
    return aggregate_metrics(filtered_events)


def parse_event_payload(events: DataFrame) -> DataFrame:
    """
    Parse event_payload to extract page_url, session_id, and user_id.

    :param events: DataFrame of user events
    :return: DataFrame with parsed fields
    """
    return events.withColumn('page_url', col('event_payload.page_url')) \
                 .withColumn('session_id', col('event_payload.session_id')) \
                 .withColumn('user_id', col('event_payload.user_id'))


def deduplicate_events(events: DataFrame) -> DataFrame:
    """
    Deduplicate events on event_id within a 1-hour window.

    :param events: DataFrame of parsed events
    :return: DataFrame of deduplicated events
    """
    return events.withWatermark('event_timestamp', '1 hour') \
                 .dropDuplicates(['event_id'])


def join_with_users(events: DataFrame, users: DataFrame) -> DataFrame:
    """
    Join deduplicated events with users table on user_id.

    :param events: DataFrame of deduplicated events
    :param users: DataFrame of users
    :return: DataFrame of enriched events
    """
    return events.join(users, on='user_id', how='inner')


def filter_by_subscription(events: DataFrame) -> DataFrame:
    """
    Filter for premium and enterprise subscription tiers only.

    :param events: DataFrame of enriched events
    :return: DataFrame of filtered events
    """
    return events.filter(col('subscription_tier').isin('premium', 'enterprise'))


def aggregate_metrics(events: DataFrame) -> DataFrame:
    """
    Aggregate session duration and page view count per user per day.

    :param events: DataFrame of filtered events
    :return: DataFrame of user engagement metrics
    """
    return events.groupBy('user_id', window('event_timestamp', '1 day').alias('event_date')) \
                 .agg(
                     spark_sum('session_duration').alias('session_duration'),
                     count('page_url').alias('page_view_count')
                 )


def write_to_bigquery(metrics: DataFrame) -> None:
    """
    Write daily user engagement metrics to BigQuery table.

    :param metrics: DataFrame of user engagement metrics
    """
    try:
        metrics.write \
            .format('bigquery') \
            .option('table', 'analytics.user_engagement_daily') \
            .option('partitionField', 'event_date') \
            .mode('overwrite') \
            .save()
    except Exception as e:
        logger.error(f"Error writing to BigQuery: {e}")
        raise


if __name__ == '__main__':
    main()