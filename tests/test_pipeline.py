import pytest
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, from_json
from unittest.mock import MagicMock

@pytest.fixture(scope='module')
def spark():
    """Fixture for creating a Spark session"""
    return SparkSession.builder.master('local').appName('test').getOrCreate()

@pytest.fixture
def sample_data(spark):
    """Fixture for creating sample data"""
    data = [
        {'event_id': '1', 'event_payload': '{"user_id": "u1", "page_url": "url1", "session_id": "s1"}', 'event_timestamp': '2023-10-01 10:00:00'},
        {'event_id': '2', 'event_payload': '{"user_id": "u2", "page_url": "url2", "session_id": "s2"}', 'event_timestamp': '2023-10-01 11:00:00'}
    ]
    return spark.createDataFrame(data)

@pytest.mark.unit
def test_parse_event_payload(sample_data):
    """Test parsing of event payload"""
    from main_pipeline import parse_event_payload
    parsed_df = parse_event_payload(sample_data)
    assert 'user_id' in parsed_df.columns
    assert 'page_url' in parsed_df.columns
    assert 'session_id' in parsed_df.columns

@pytest.mark.unit
def test_deduplicate_events(sample_data):
    """Test deduplication of events"""
    from main_pipeline import deduplicate_events
    dedup_df = deduplicate_events(sample_data)
    assert dedup_df.count() == 2

@pytest.mark.integration
def test_pipeline_flow(spark, sample_data):
    """Integration test for the entire pipeline flow"""
    from main_pipeline import run_pipeline
    output_df = run_pipeline(spark, sample_data)
    assert output_df.count() > 0
    assert 'user_id' in output_df.columns
    assert 'event_date' in output_df.columns

@pytest.mark.validation
def test_null_check_user_id(sample_data):
    """Validation test to ensure no NULL values in user_id column"""
    from main_pipeline import validate_no_nulls
    result = validate_no_nulls(sample_data, 'user_id')
    assert result == True

@pytest.mark.parametrize('event_payload, expected_user_id', [
    ('{"user_id": "u1", "page_url": "url1", "session_id": "s1"}', 'u1'),
    ('{"user_id": "u2", "page_url": "url2", "session_id": "s2"}', 'u2')
])
def test_parse_event_payload_parametrized(event_payload, expected_user_id, spark):
    """Parametrized test for parsing event payload"""
    from main_pipeline import parse_event_payload
    data = [{'event_id': '1', 'event_payload': event_payload, 'event_timestamp': '2023-10-01 10:00:00'}]
    df = spark.createDataFrame(data)
    parsed_df = parse_event_payload(df)
    assert parsed_df.filter(col('user_id') == expected_user_id).count() == 1
