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
    openai_api_key: Optional[str] = Field(None, description="OpenAI API key")
    openai_model: str = "gpt-4o"
    openai_temperature: float = 0.3

    # GitHub Configuration
    github_token: Optional[str] = Field(None, description="GitHub personal access token")
    github_repo_owner: Optional[str] = Field(None, description="GitHub repository owner")
    github_repo_name: Optional[str] = Field(None, description="GitHub repository name")

    # Google Cloud Configuration
    gcp_project_id: Optional[str] = Field(None, description="GCP project ID")
    gcp_credentials_path: str = ""
    bq_dataset: str = "etl_automation"
    bq_table_prefix: str = "pipeline_"

    # Application Configuration
    app_host: str = "0.0.0.0"
    app_port: int = Field(
        default=8000,
        description="Application port (Cloud Run sets PORT env var, defaults to 8000)"
    )
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
    def validate_openai_key(cls, v: str, info) -> Optional[str]:
        """Validate OpenAI API key format."""
        # Allow None in development
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError('OPENAI_API_KEY must be a string')
        if not v.startswith('sk-'):
            raise ValueError('Invalid OpenAI API key format (must start with sk-)')
        return v

    @field_validator('github_token', mode='before')
    @classmethod
    def validate_github_token(cls, v: str, info) -> Optional[str]:
        """Validate GitHub token format."""
        # Allow None in development
        if v is None:
            return None
        if not isinstance(v, str):
            raise ValueError('GITHUB_TOKEN must be a string')
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
        
        # In production, require all critical keys
        if not self.openai_api_key:
            raise ValueError('OPENAI_API_KEY is required in production')
        if not self.github_token:
            raise ValueError('GITHUB_TOKEN is required in production')
        if not self.github_repo_owner:
            raise ValueError('GITHUB_REPO_OWNER is required in production')
        if not self.github_repo_name:
            raise ValueError('GITHUB_REPO_NAME is required in production')
        if not self.gcp_project_id:
            raise ValueError('GCP_PROJECT_ID is required in production')
            
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
            # Use /app/data/ if available (Cloud Run writable dir), else current dir
            import os as _os
            if _os.path.isdir('/app/data') and _os.access('/app/data', _os.W_OK):
                db_path = "sqlite:////app/data/etl_agent.db"
            else:
                db_path = "sqlite:///./etl_agent.db"
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
    """Get cached settings instance.
    
    Note: Production validation happens asynchronously after app starts,
    to prevent Cloud Run startup failures from configuration issues.
    """
    settings = Settings()
    
    # Log production configuration warnings (non-blocking)
    if settings.is_production:
        logger = logging.getLogger(__name__)
        missing_configs = []
        
        if not settings.openai_api_key:
            missing_configs.append("OPENAI_API_KEY")
        if not settings.github_token:
            missing_configs.append("GITHUB_TOKEN")
        if not settings.github_repo_owner:
            missing_configs.append("GITHUB_REPO_OWNER")
        if not settings.github_repo_name:
            missing_configs.append("GITHUB_REPO_NAME")
        if not settings.gcp_project_id:
            missing_configs.append("GCP_PROJECT_ID")
        if not settings.api_key:
            missing_configs.append("API_KEY")
        if settings.db_driver == "sqlite":
            missing_configs.append("PostgreSQL (SQLite not allowed)")
        
        if missing_configs:
            logger.warning(f"Production config incomplete (app still starting): {', '.join(missing_configs)}")
            logger.warning("Some features may not work until environment variables are configured")
    
    return settings
