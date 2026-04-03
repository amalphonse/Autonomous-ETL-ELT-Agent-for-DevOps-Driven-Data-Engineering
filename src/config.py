"""Configuration module for the Autonomous ETL/ELT Agent system."""

from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"

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
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_key: Optional[str] = None  # Optional API key for authentication

    # Database Configuration
    database_url: Optional[str] = None  # Override with explicit URL if set
    db_driver: str = "sqlite"  # sqlite or postgresql
    db_host: str = "localhost"
    db_port: int = 5432
    db_user: str = "etl_user"
    db_password: str = "etl_password"
    db_name: str = "etl_agent_db"
    db_echo: bool = False  # SQL logging
    
    # Data Processing
    spark_master: str = "local[*]"
    delta_lake_path: str = ""

    class Config:
        env_file = ".env"
        case_sensitive = False

    @property
    def get_database_url(self) -> str:
        """
        Construct database URL based on configuration.
        
        Returns:
            SQLAlchemy database URL string
        """
        # If explicit URL provided, use it
        if self.database_url:
            return self.database_url
        
        # Construct based on driver
        if self.db_driver == "postgresql":
            return (
                f"postgresql+psycopg2://{self.db_user}:{self.db_password}@"
                f"{self.db_host}:{self.db_port}/{self.db_name}"
            )
        else:  # sqlite (default)
            db_path = self.database_url or f"sqlite:///./etl_agent.db"
            return db_path
    
    @property
    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Check if running in development environment."""
        return self.environment.lower() == "development"
    
    @property
    def db_echo_enabled(self) -> bool:
        """SQL query logging should be enabled in development only."""
        return self.db_echo or self.is_development


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
