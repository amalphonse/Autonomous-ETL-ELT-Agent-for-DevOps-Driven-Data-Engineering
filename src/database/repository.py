"""Repository for pipeline execution database operations."""

import logging
from typing import List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import desc, and_

from src.database.models import PipelineExecution

logger = logging.getLogger(__name__)


class PipelineExecutionRepository:
    """Repository for PipelineExecution model operations."""

    @staticmethod
    def create(
        db: Session,
        execution_id: str,
        user_story_title: str,
        user_story_description: str,
        user_story_json: dict = None,
    ) -> PipelineExecution:
        """Create a new pipeline execution record.
        
        Args:
            db: Database session.
            execution_id: Unique execution ID.
            user_story_title: Title of the user story.
            user_story_description: Description of the user story.
            user_story_json: Full user story as JSON (optional).
            
        Returns:
            Created PipelineExecution record.
        """
        execution = PipelineExecution(
            execution_id=execution_id,
            user_story_title=user_story_title,
            user_story_description=user_story_description,
            user_story_json=user_story_json,
            status="initialized",
        )
        db.add(execution)
        db.commit()
        db.refresh(execution)
        logger.info(f"Created pipeline execution record: {execution_id}")
        return execution

    @staticmethod
    def get_by_id(db: Session, execution_id: str) -> Optional[PipelineExecution]:
        """Get execution by ID.
        
        Args:
            db: Database session.
            execution_id: Execution ID to retrieve.
            
        Returns:
            PipelineExecution if found, None otherwise.
        """
        return db.query(PipelineExecution).filter(
            PipelineExecution.execution_id == execution_id
        ).first()

    @staticmethod
    def update(
        db: Session,
        execution_id: str,
        **kwargs
    ) -> Optional[PipelineExecution]:
        """Update an execution record.
        
        Args:
            db: Database session.
            execution_id: ID of execution to update.
            **kwargs: Fields to update.
            
        Returns:
            Updated PipelineExecution or None if not found.
        """
        execution = db.query(PipelineExecution).filter(
            PipelineExecution.execution_id == execution_id
        ).first()
        
        if execution:
            for key, value in kwargs.items():
                if hasattr(execution, key):
                    setattr(execution, key, value)
            execution.updated_at = datetime.utcnow()
            db.commit()
            db.refresh(execution)
            logger.info(f"Updated pipeline execution: {execution_id}")
        
        return execution

    @staticmethod
    def list_all(
        db: Session,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None,
    ) -> List[PipelineExecution]:
        """List all executions with optional filtering.
        
        Args:
            db: Database session.
            limit: Maximum number of results.
            offset: Number of results to skip.
            status: Filter by status (optional).
            
        Returns:
            List of PipelineExecution records.
        """
        query = db.query(PipelineExecution)
        
        if status:
            query = query.filter(PipelineExecution.status == status)
        
        # Order by created_at descending (newest first)
        query = query.order_by(desc(PipelineExecution.created_at))
        
        return query.offset(offset).limit(limit).all()

    @staticmethod
    def get_analytics(db: Session) -> dict:
        """Get analytics about all executions.
        
        Args:
            db: Database session.
            
        Returns:
            Dictionary with analytics metrics.
        """
        all_executions = db.query(PipelineExecution).all()
        successful = [e for e in all_executions if e.status == "success"]
        failed = [e for e in all_executions if e.status == "failed"]
        
        if not all_executions:
            return {
                "total_executions": 0,
                "successful": 0,
                "failed": 0,
                "success_rate": 0.0,
                "average_quality": 0.0,
                "average_task_confidence": 0.0,
                "average_code_quality": 0.0,
                "average_test_quality": 0.0,
                "average_pr_quality": 0.0,
            }
        
        return {
            "total_executions": len(all_executions),
            "successful": len(successful),
            "failed": len(failed),
            "success_rate": len(successful) / len(all_executions),
            "average_quality": sum(e.overall_quality for e in all_executions) / len(all_executions),
            "average_task_confidence": sum(e.task_confidence for e in successful) / len(successful) if successful else 0.0,
            "average_code_quality": sum(e.code_quality for e in successful) / len(successful) if successful else 0.0,
            "average_test_quality": sum(e.test_quality for e in successful) / len(successful) if successful else 0.0,
            "average_pr_quality": sum(e.pr_quality for e in successful) / len(successful) if successful else 0.0,
        }

    @staticmethod
    def get_stats_by_status(db: Session) -> dict:
        """Get execution counts by status.
        
        Args:
            db: Database session.
            
        Returns:
            Dictionary with status counts.
        """
        query = db.query(PipelineExecution.status)
        
        stats = {}
        for execution in db.query(PipelineExecution).all():
            status = execution.status
            stats[status] = stats.get(status, 0) + 1
        
        return stats
