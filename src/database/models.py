"""SQLAlchemy models for pipeline execution persistence."""

from sqlalchemy import Column, String, Float, Text, DateTime, JSON, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime
import json

Base = declarative_base()


class PipelineExecution(Base):
    """Model for storing pipeline execution history and results."""

    __tablename__ = "pipeline_executions"

    # Primary key
    execution_id = Column(String(36), primary_key=True, index=True)

    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Input data
    user_story_title = Column(String(255), index=True)
    user_story_description = Column(Text, nullable=True)
    user_story_json = Column(JSON, nullable=True)

    # Pipeline status
    status = Column(String(50), index=True, default="initialized")  # initialized, running, success, failed
    error_message = Column(Text, nullable=True)

    # Quality metrics
    task_confidence = Column(Float, default=0.0)
    code_quality = Column(Float, default=0.0)
    test_quality = Column(Float, default=0.0)
    pr_quality = Column(Float, default=0.0)
    overall_quality = Column(Float, default=0.0)

    # Agent outputs (as JSON for flexibility)
    parsed_requirements = Column(JSON, nullable=True)
    generated_code = Column(JSON, nullable=True)
    generated_tests = Column(JSON, nullable=True)
    pull_request = Column(JSON, nullable=True)

    # Execution result and lineage
    execution_result = Column(JSON, nullable=True)  # Includes execution logs, lineage, and detailed results

    # Execution metadata
    execution_log = Column(JSON, default=list)  # List of log entries
    duration_seconds = Column(Float, nullable=True)

    def __repr__(self):
        return f"<PipelineExecution(id={self.execution_id}, status={self.status}, quality={self.overall_quality:.2%})>"

    def to_dict(self):
        """Convert model to dictionary."""
        return {
            "execution_id": self.execution_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
            "status": self.status,
            "user_story_title": self.user_story_title,
            "user_story_description": self.user_story_description,
            "task_confidence": self.task_confidence,
            "code_quality": self.code_quality,
            "test_quality": self.test_quality,
            "pr_quality": self.pr_quality,
            "overall_quality": self.overall_quality,
            "error_message": self.error_message,
            "execution_log": self.execution_log or [],
            "duration_seconds": self.duration_seconds,
        }
