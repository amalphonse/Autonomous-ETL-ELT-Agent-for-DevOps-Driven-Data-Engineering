"""Data models for data lineage tracking."""

from typing import Optional, List, Dict, Any
from datetime import datetime
from dataclasses import dataclass, field


@dataclass
class DatasetField:
    """Represents a field/column in a dataset."""
    name: str
    type: str
    description: Optional[str] = None


@dataclass
class Dataset:
    """Represents a dataset in the pipeline."""
    name: str
    namespace: str = "default"
    location: Optional[str] = None
    source_type: str = "dataset"  # dataset, database, file, etc.
    fields: List[DatasetField] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @property
    def qualified_name(self) -> str:
        """Get the fully qualified name of the dataset."""
        return f"{self.namespace}.{self.name}"


@dataclass
class Transformation:
    """Represents a transformation in the pipeline."""
    name: str
    operation: str  # filter, join, aggregate, select, etc.
    description: Optional[str] = None
    inputs: List[str] = field(default_factory=list)  # Dataset names
    outputs: List[str] = field(default_factory=list)  # Dataset names
    details: Dict[str, Any] = field(default_factory=dict)  # Operation-specific details


@dataclass
class PipelineLineage:
    """Complete lineage information for a pipeline."""
    execution_id: str
    pipeline_name: str
    datasets: Dict[str, Dataset] = field(default_factory=dict)  # name -> Dataset
    transformations: List[Transformation] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)  # Input dataset names
    targets: List[str] = field(default_factory=list)  # Output dataset names
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API response."""
        return {
            "execution_id": self.execution_id,
            "pipeline_name": self.pipeline_name,
            "datasets": {
                name: {
                    "name": ds.name,
                    "namespace": ds.namespace,
                    "location": ds.location,
                    "source_type": ds.source_type,
                    "fields": [
                        {"name": f.name, "type": f.type, "description": f.description}
                        for f in ds.fields
                    ],
                }
                for name, ds in self.datasets.items()
            },
            "transformations": [
                {
                    "name": t.name,
                    "operation": t.operation,
                    "description": t.description,
                    "inputs": t.inputs,
                    "outputs": t.outputs,
                    "details": t.details,
                }
                for t in self.transformations
            ],
            "sources": self.sources,
            "targets": self.targets,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class OpenLineageEvent:
    """Represents an OpenLineage event for emission."""
    event_type: str  # START, COMPLETE, FAIL, ABORT
    execution_id: str
    pipeline_name: str
    producer: str = "etl-agent"
    inputs: List[str] = field(default_factory=list)
    outputs: List[str] = field(default_factory=list)
    started_at: Optional[datetime] = None
    ended_at: Optional[datetime] = None
    status: Optional[str] = None  # success, failed, aborted
    
    def to_openlineage_dict(self) -> Dict[str, Any]:
        """Convert to OpenLineage event format."""
        return {
            "eventType": self.event_type,
            "eventTime": (self.ended_at or datetime.utcnow()).isoformat(),
            "producer": self.producer,
            "schemaURL": "https://openlineage.io/spec/facets",
            "run": {
                "runId": self.execution_id,
                "facets": {}
            },
            "job": {
                "namespace": "etl-agent",
                "name": self.pipeline_name,
            },
            "inputs": [
                {
                    "namespace": "dataset",
                    "name": input_name
                }
                for input_name in self.inputs
            ],
            "outputs": [
                {
                    "namespace": "dataset",
                    "name": output_name
                }
                for output_name in self.outputs
            ],
        }
