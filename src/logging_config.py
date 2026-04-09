"""Structured logging configuration for the ETL agent system."""

import sys
import logging
from pathlib import Path
from loguru import logger
from src.config import get_settings

# Get settings
settings = get_settings()

# Create logs directory if it doesn't exist (use absolute path for Cloud Run)
log_dir = Path("/app/logs") if Path("/app").exists() else Path("logs")
log_dir.mkdir(parents=True, exist_ok=True)

# Remove default handler
logger.remove()

# Log format
log_format = (
    "<level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
    "<level>{message}</level>"
)

# JSON format for structured logging
json_format = (
    '{"timestamp": "{time:YYYY-MM-DD HH:mm:ss}", '
    '"level": "{level}", '
    '"logger": "{name}", '
    '"function": "{function}", '
    '"line": "{line}", '
    '"message": "{message}"}'
)

# Log level
log_level = settings.log_level.upper()

# Console handler (always on, for development)
if settings.is_development:
    logger.add(
        sys.stdout,
        format=log_format,
        level=log_level,
        colorize=True,
    )
else:
    # Production: JSON format to stdout
    logger.add(
        sys.stdout,
        format=json_format,
        level=log_level,
        colorize=False,
    )

# File handler (always on) — use absolute path so it works in Cloud Run
logger.add(
    str(log_dir / f"etl_agent_{settings.environment}.log"),
    format=json_format if not settings.is_development else log_format,
    level=log_level,
    rotation="500 MB",  # Rotate when file reaches 500MB
    retention="10 days",  # Keep logs for 10 days
    compression="zip",  # Compress rotated logs
)

# Error log file (separate)
logger.add(
    str(log_dir / f"etl_agent_errors_{settings.environment}.log"),
    format=json_format if not settings.is_development else log_format,
    level="ERROR",
    rotation="500 MB",
    retention="30 days",
    compression="zip",
)

# Integration with Python's standard logging module
class InterceptHandler(logging.Handler):
    """Intercept standard logging calls and route to loguru."""

    def emit(self, record: logging.LogRecord) -> None:
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where the logged message originated
        frame, depth = logging.currentframe(), 0
        while frame and (frame.f_code.co_filename == logging.__file__ or
                         frame.f_code.co_filename == __file__):
            frame = frame.f_back
            depth += 1

        # Use logger.opt() for depth/exception — do NOT pass kwargs to .log()
        # because any kwargs would be used to .format() the message string,
        # which breaks when messages contain JSON like {"title": "..."}.
        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


# Replace standard logging with loguru
logging.basicConfig(handlers=[InterceptHandler()], level=0)

# Suppress noisy loggers
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
logging.getLogger("langchain").setLevel(logging.WARNING)
logging.getLogger("urllib3").setLevel(logging.WARNING)

logger.info(f"Logging initialized - Environment: {settings.environment}, Level: {log_level}")
