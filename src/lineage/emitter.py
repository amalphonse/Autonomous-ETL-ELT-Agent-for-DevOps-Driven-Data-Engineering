"""Emits data lineage events in OpenLineage format."""

import json
import logging
from typing import Optional, List
from datetime import datetime
from src.lineage.models import PipelineLineage, OpenLineageEvent

logger = logging.getLogger(__name__)


class LineageEmitter:
    """Emits OpenLineage events for pipeline execution tracking."""
    
    def __init__(self, execution_id: str, backend: str = "local"):
        """Initialize the lineage emitter.
        
        Args:
            execution_id: Unique execution ID
            backend: Emission backend - 'local' (logging), 'http' (OpenLineage server), 'kafka' (event streaming)
        """
        self.execution_id = execution_id
        self.backend = backend
        self.events: List[OpenLineageEvent] = []
    
    def emit_start(self, pipeline_name: str, inputs: List[str]) -> None:
        """Emit a START event when pipeline execution begins.
        
        Args:
            pipeline_name: Name of the pipeline
            inputs: List of input dataset names
        """
        event = OpenLineageEvent(
            event_type="START",
            execution_id=self.execution_id,
            pipeline_name=pipeline_name,
            inputs=inputs,
            started_at=datetime.utcnow(),
        )
        
        self._emit_event(event)
        self.events.append(event)
        logger.info(f"Emitted START event for {pipeline_name} with {len(inputs)} inputs")
    
    def emit_complete(
        self,
        pipeline_name: str,
        inputs: List[str],
        outputs: List[str],
        status: str = "success",
    ) -> None:
        """Emit a COMPLETE event when pipeline execution finishes.
        
        Args:
            pipeline_name: Name of the pipeline
            inputs: List of input dataset names
            outputs: List of output dataset names
            status: Execution status ('success', 'failed', 'aborted')
        """
        event = OpenLineageEvent(
            event_type="COMPLETE",
            execution_id=self.execution_id,
            pipeline_name=pipeline_name,
            inputs=inputs,
            outputs=outputs,
            ended_at=datetime.utcnow(),
            status=status,
        )
        
        self._emit_event(event)
        self.events.append(event)
        logger.info(f"Emitted COMPLETE event for {pipeline_name} - status: {status}")
    
    def emit_lineage(self, lineage: PipelineLineage) -> None:
        """Emit complete lineage information.
        
        Args:
            lineage: Pipeline lineage object
        """
        logger.info(
            f"Emitting lineage for {lineage.pipeline_name}: "
            f"{len(lineage.sources)} sources, {len(lineage.targets)} targets"
        )
        
        # Log lineage as JSON
        lineage_dict = lineage.to_dict()
        logger.info(f"Lineage: {json.dumps(lineage_dict, indent=2, default=str)}")
    
    def _emit_event(self, event: OpenLineageEvent) -> None:
        """Internal method to emit an OpenLineage event.
        
        Args:
            event: OpenLineageEvent to emit
        """
        if self.backend == "local":
            self._emit_local(event)
        elif self.backend == "http":
            self._emit_http(event)
        elif self.backend == "kafka":
            self._emit_kafka(event)
        else:
            logger.warning(f"Unknown backend: {self.backend}")
    
    def _emit_local(self, event: OpenLineageEvent) -> None:
        """Emit event to local logging (for development/testing).
        
        Args:
            event: OpenLineageEvent to emit
        """
        event_dict = event.to_openlineage_dict()
        logger.debug(f"OpenLineage Event: {json.dumps(event_dict, indent=2, default=str)}")
    
    def _emit_http(self, event: OpenLineageEvent) -> None:
        """Emit event to HTTP backend (OpenLineage server).
        
        Args:
            event: OpenLineageEvent to emit
            
        Note:
            Requires OPENLINEAGE_URL environment variable or configuration
        """
        try:
            import requests
        except ImportError:
            logger.warning("requests library not installed - skipping HTTP emission")
            return
        
        # This would be implemented with actual HTTP client
        # For now, just log as placeholder
        event_dict = event.to_openlineage_dict()
        logger.debug(f"Would emit to HTTP: {json.dumps(event_dict, default=str)}")
    
    def _emit_kafka(self, event: OpenLineageEvent) -> None:
        """Emit event to Kafka topic (event streaming).
        
        Args:
            event: OpenLineageEvent to emit
            
        Note:
            Requires kafka-python or confluent-kafka library
        """
        try:
            from kafka import KafkaProducer
        except ImportError:
            logger.warning("kafka-python not installed - skipping Kafka emission")
            return
        
        # This would be implemented with actual Kafka producer
        # For now, just log as placeholder
        event_dict = event.to_openlineage_dict()
        logger.debug(f"Would emit to Kafka: {json.dumps(event_dict, default=str)}")
    
    def get_emitted_events(self) -> List[dict]:
        """Get all emitted events as dictionaries.
        
        Returns:
            List of OpenLineage event dictionaries
        """
        return [event.to_openlineage_dict() for event in self.events]
