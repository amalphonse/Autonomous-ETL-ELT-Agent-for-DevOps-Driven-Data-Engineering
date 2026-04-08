"""Configuration module for the Autonomous ETL/ELT Agent system."""

from pydantic_settings import BaseSettings
from pydantic import field_validator, Field
from functools import lru_cache
from typing import Optional
import os
import logging


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    environment: str = "development"  # development, staging, production
    log_level: str = "INFO"

    # OpenAI Configuration
    openai_api_key: str = Field(..., description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.3

    # GitHub Configuration
    github_token: str = Field(..., description="GitHub personal access token")
    github_repo_owner: str = Field(..., description="GitHub repository owner")
    github_repo_name: str = Field(..., description="GitHub repository name")

    # Google Cloud Configuration
    gcp_project_id: str = Field(..., description="GCP project ID")
    gcp_credentials_path: str = ""
    bq_dataset: str = "etl_automation"
    bq_table_prefix: str = "pipeline_"

    # Application Configuration
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    api_key: Optional[str] = Field(None, description="API key for endpoint authentication")

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

    # Validation
    @field_validator('openai_api_key', mode='before')
    @classmethod
    def validate_openai_key(cls, v: str) -> str:
        """Validate OpenAI API key format."""
        if not v or not isinstance(v, str):
            raise ValueError('OPENAI_API_KEY is required')
        if not v.startswith('sk-'):
            raise ValueError('Invalid OpenAI API key format (must start with sk-)')
        return v

    @field_validator('github_token', mode='before')
    @classmethod
    def validate_github_token(cls, v: str) -> str:
        """Validate GitHub token format."""
        if not v or not isinstance(v, str):
            raise ValueError('GITHUB_TOKEN is required')
        if not v.startswith(('ghp_', 'github_pat_')):
            raise ValueError('Invalid GitHub token format')
        return v

    def validate_production_config(self) -> None:
        """Validate configuration for production environment.
        
        Raises:
            ValueError: If production requirements are not met
        """
        if not self.is_production:
            return
            
        # Require API key in production
        if not self.api_key:
            raise ValueError('API_KEY is required in production environment')
        
        # Require PostgreSQL in production
        if self.db_driver == "sqlite":
            raise ValueError('PostgreSQL required in production (cannot use SQLite)')
        
        # Validate environment is set correctly
        if self.environment != "production":
            raise ValueError('Environmental inconsistency: environment != production')
        
        # Log successful validation
        logger = logging.getLogger(__name__)
        logger.info("Production configuration validated successfully")

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
    """Get cached settings instance with production validation.
    
    Raises:
        ValueError: If production configuration is invalid
    """
    settings = Settings()
    
    # Validate production configuration on startup
    try:
        settings.validate_production_config()
    except ValueError as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Configuration validation failed: {e}")
        raise
    
    return settings
