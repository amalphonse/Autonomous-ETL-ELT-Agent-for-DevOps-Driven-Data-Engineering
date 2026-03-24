"""Configuration module for the Autonomous ETL/ELT Agent system."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # OpenAI Configuration
    openai_api_key: str
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.3

    # GitHub Configuration
    github_token: str
    github_repo_owner: str
    github_repo_name: str

    # Google Cloud Configuration
    gcp_project_id: str
    gcp_credentials_path: str = ""
    bq_dataset: str = "etl_automation"
    bq_table_prefix: str = "pipeline_"

    # Application Configuration
    log_level: str = "INFO"
    app_env: str = "development"
    app_host: str = "0.0.0.0"
    app_port: int = 8000

    # Data Processing
    spark_master: str = "local[*]"
    delta_lake_path: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
