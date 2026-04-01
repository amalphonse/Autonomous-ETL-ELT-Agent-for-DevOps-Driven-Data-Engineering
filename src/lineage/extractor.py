"""Lineage extraction from generated PySpark code."""

import re
import logging
from typing import Dict, List, Set, Tuple, Optional, Any
from src.lineage.models import Dataset, Transformation, PipelineLineage, DatasetField

logger = logging.getLogger(__name__)


class LineageExtractor:
    """Extracts data lineage from PySpark code."""
    
    # Regex patterns for PySpark operations
    PATTERNS = {
        # read operations: spark.read.format(...).load(path)
        "read": r"(?:spark\.read|df_\w+\s*=.*?spark\.read)\.(?:csv|parquet|json|orc|delta)\s*\(.*?['\"]([^'\"]+)['\"]",
        
        # write operations: df.write.format(...).save(path)
        "write": r"\.write\.(?:format|mode)\s*\(['\"]([^'\"]+)['\"].*?\.save\s*\(['\"]([^'\"]+)['\"]",
        
        # DataFrame assignments
        "assignment": r"(\w+)\s*=\s*spark\.read\.(?:csv|parquet|json|orc|delta)\s*\(.*?['\"]([^'\"]+)['\"]",
        
        # Filter operations
        "filter": r"(\w+)\s*=\s*(\w+)\.filter\s*\(['\"](.+?)['\"]",
        
        # Select operations
        "select": r"(\w+)\s*=\s*(\w+)\.select\s*\((.*?)\)",
        
        # Join operations
        "join": r"(\w+)\s*=\s*(\w+)\.join\s*\((\w+).*?on\s*=\s*['\"](.+?)['\"]",
        
        # Aggregate operations
        "aggregate": r"(\w+)\s*=\s*(\w+)\.groupBy\s*\((.*?)\)\.agg\s*\(",
        
        # Union operations
        "union": r"(\w+)\s*=\s*(\w+)\.union\s*\((\w+)",
    }
    
    def __init__(self, execution_id: str, pipeline_name: str = "spark_pipeline"):
        """Initialize the lineage extractor.
        
        Args:
            execution_id: Unique ID for this pipeline execution
            pipeline_name: Name of the pipeline
        """
        self.execution_id = execution_id
        self.pipeline_name = pipeline_name
        self.lineage = PipelineLineage(
            execution_id=execution_id,
            pipeline_name=pipeline_name,
        )
        self.dataframe_map: Dict[str, str] = {}  # dataframe_name -> dataset_path
    
    def extract(self, code: str) -> PipelineLineage:
        """Extract lineage from PySpark code.
        
        Args:
            code: Generated PySpark code
            
        Returns:
            PipelineLineage object with extracted information
        """
        logger.info(f"Extracting lineage from {len(code)} characters of code")
        
        try:
            # Extract read operations (sources)
            self._extract_reads(code)
            
            # Extract write operations (targets)
            self._extract_writes(code)
            
            # Extract transformations
            self._extract_transformations(code)
            
            logger.info(
                f"Extracted {len(self.lineage.datasets)} datasets, "
                f"{len(self.lineage.transformations)} transformations"
            )
        except Exception as e:
            logger.error(f"Error extracting lineage: {e}")
            # Continue gracefully even if extraction partially fails
        
        return self.lineage
    
    def _extract_reads(self, code: str) -> None:
        """Extract source datasets from read operations."""
        # Simple pattern: look for spark.read.* operations
        read_pattern = r"spark\.read\.(?:csv|parquet|json|orc|delta)\s*\(\s*['\"]([^'\"]+)['\"]"
        matches = re.finditer(read_pattern, code, re.IGNORECASE)
        
        for match in matches:
            path = match.group(1)
            dataset_name = self._extract_name_from_path(path)
            
            dataset = Dataset(
                name=dataset_name,
                namespace="input",
                location=path,
                source_type="parquet" if ".parquet" in path else "csv",
            )
            
            self.lineage.datasets[dataset_name] = dataset
            self.lineage.sources.append(dataset_name)
            logger.debug(f"Found source dataset: {dataset_name} at {path}")
    
    def _extract_writes(self, code: str) -> None:
        """Extract target datasets from write operations."""
        # Pattern for write operations
        write_pattern = r"(\w+)\.write\.(?:mode\s*\(\s*['\"]([^'\"]+)['\"])?\s*\.(?:format\s*\(\s*['\"]([^'\"]+)['\"])?\s*\.save\s*\(\s*['\"]([^'\"]+)['\"]"
        matches = re.finditer(write_pattern, code, re.IGNORECASE)
        
        for match in matches:
            df_name = match.group(1)
            save_mode = match.group(2) or "overwrite"
            format_type = match.group(3) or "parquet"
            path = match.group(4)
            
            dataset_name = self._extract_name_from_path(path)
            
            dataset = Dataset(
                name=dataset_name,
                namespace="output",
                location=path,
                source_type=format_type,
            )
            
            self.lineage.datasets[dataset_name] = dataset
            self.lineage.targets.append(dataset_name)
            logger.debug(f"Found target dataset: {dataset_name} at {path}")
    
    def _extract_transformations(self, code: str) -> None:
        """Extract transformations (filters, joins, aggregates, etc.)."""
        # Extract filter operations
        filter_pattern = r"(\w+)\s*=\s*(\w+)\.filter\s*\((.*?)\)"
        for match in re.finditer(filter_pattern, code, re.DOTALL):
            output_df = match.group(1)
            input_df = match.group(2)
            condition = match.group(3).strip()
            
            self._add_transformation(
                name=f"filter_{output_df}",
                operation="filter",
                inputs=[input_df],
                outputs=[output_df],
                details={"condition": condition},
            )
        
        # Extract select operations
        select_pattern = r"(\w+)\s*=\s*(\w+)\.select\s*\((.*?)\)"
        for match in re.finditer(select_pattern, code, re.DOTALL):
            output_df = match.group(1)
            input_df = match.group(2)
            columns = match.group(3).strip()
            
            self._add_transformation(
                name=f"select_{output_df}",
                operation="select",
                inputs=[input_df],
                outputs=[output_df],
                details={"columns": columns},
            )
        
        # Extract join operations
        join_pattern = r"(\w+)\s*=\s*(\w+)\.join\s*\((\w+)[^)]*?on\s*=\s*['\"]([^'\"]+)['\"]"
        for match in re.finditer(join_pattern, code, re.IGNORECASE):
            output_df = match.group(1)
            left_df = match.group(2)
            right_df = match.group(3)
            join_key = match.group(4)
            
            self._add_transformation(
                name=f"join_{output_df}",
                operation="join",
                inputs=[left_df, right_df],
                outputs=[output_df],
                details={"join_key": join_key},
            )
        
        # Extract groupBy operations
        groupby_pattern = r"(\w+)\s*=\s*(\w+)\.groupBy\s*\((.*?)\)\.agg\s*\("
        for match in re.finditer(groupby_pattern, code, re.DOTALL):
            output_df = match.group(1)
            input_df = match.group(2)
            group_columns = match.group(3).strip()
            
            self._add_transformation(
                name=f"aggregate_{output_df}",
                operation="aggregate",
                inputs=[input_df],
                outputs=[output_df],
                details={"group_by": group_columns},
            )
    
    def _add_transformation(
        self,
        name: str,
        operation: str,
        inputs: List[str],
        outputs: List[str],
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a transformation to the lineage."""
        transformation = Transformation(
            name=name,
            operation=operation,
            inputs=inputs,
            outputs=outputs,
            details=details or {},
        )
        self.lineage.transformations.append(transformation)
        logger.debug(f"Added transformation: {name} ({operation})")
    
    @staticmethod
    def _extract_name_from_path(path: str) -> str:
        """Extract dataset name from file path.
        
        Args:
            path: File path (e.g., 's3://bucket/data/customers.parquet')
            
        Returns:
            Extracted name (e.g., 'customers')
        """
        # Remove protocol and extension
        name = path.split("/")[-1]  # Get last part
        name = name.split(".")[0]   # Remove extension
        return name or "dataset"
