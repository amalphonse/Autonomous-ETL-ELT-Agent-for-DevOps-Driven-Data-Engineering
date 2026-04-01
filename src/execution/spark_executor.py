"""Spark code executor for running generated transformations."""

import logging
import subprocess
import tempfile
import os
import json
from typing import Dict, Any, Tuple
from datetime import datetime

logger = logging.getLogger(__name__)


class SparkExecutor:
    """Execute generated PySpark code and capture results."""

    def __init__(self):
        """Initialize the Spark executor."""
        self.spark_submit_path = "spark-submit"  # Assumes spark-submit is in PATH
        self.execution_timeout = 300  # 5 minutes timeout

    def execute_code(
        self,
        code: str,
        job_name: str = "etl_job",
        use_local_mode: bool = True,
    ) -> Dict[str, Any]:
        """Execute PySpark code and return results.

        Args:
            code: The PySpark code to execute.
            job_name: Name for the Spark job.
            use_local_mode: Whether to use local[*] mode (no cluster needed).

        Returns:
            Dictionary with execution results, logs, and metrics.
        """
        logger.info(f"Executing PySpark code: {job_name}")
        start_time = datetime.utcnow()

        try:
            # Create temporary Python file with the code
            with tempfile.NamedTemporaryFile(
                mode="w",
                suffix=".py",
                delete=False,
                dir="/tmp"
            ) as f:
                temp_file = f.name
                f.write(self._wrap_code(code, job_name))

            logger.debug(f"Created temporary file: {temp_file}")

            # Build spark-submit command
            cmd = self._build_spark_command(temp_file, job_name, use_local_mode)

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Execute the code
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.execution_timeout,
            )

            # Parse results
            duration = (datetime.utcnow() - start_time).total_seconds()

            if result.returncode == 0:
                logger.info(f"PySpark execution successful in {duration:.2f}s")
                return {
                    "status": "success",
                    "duration_seconds": duration,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_result": self._parse_output(result.stdout),
                    "error": None,
                }
            else:
                logger.error(f"PySpark execution failed: {result.stderr}")
                return {
                    "status": "failed",
                    "duration_seconds": duration,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "execution_result": None,
                    "error": result.stderr,
                }

        except subprocess.TimeoutExpired:
            logger.error(f"PySpark execution timed out after {self.execution_timeout}s")
            duration = (datetime.utcnow() - start_time).total_seconds()
            return {
                "status": "timeout",
                "duration_seconds": duration,
                "stdout": "",
                "stderr": f"Execution timed out after {self.execution_timeout} seconds",
                "execution_result": None,
                "error": "Execution timeout",
            }

        except Exception as e:
            logger.error(f"Error executing PySpark code: {str(e)}", exc_info=True)
            duration = (datetime.utcnow() - start_time).total_seconds()
            return {
                "status": "error",
                "duration_seconds": duration,
                "stdout": "",
                "stderr": str(e),
                "execution_result": None,
                "error": str(e),
            }

        finally:
            # Clean up temporary file
            try:
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                    logger.debug(f"Removed temporary file: {temp_file}")
            except Exception as e:
                logger.warning(f"Failed to remove temporary file: {str(e)}")

    def _wrap_code(self, code: str, job_name: str) -> str:
        """Wrap user code with initialization and cleanup.

        Args:
            code: User's PySpark code.
            job_name: Name for the Spark application.

        Returns:
            Wrapped code with Spark session setup.
        """
        wrapped = f"""
import sys
import json
from pyspark.sql import SparkSession

# Initialize Spark session
spark = SparkSession.builder \\
    .appName('{job_name}') \\
    .master('local[*]') \\
    .config('spark.sql.adaptive.enabled', 'true') \\
    .getOrCreate()

# Set log level to reduce noise
spark.sparkContext.setLogLevel('WARN')

try:
    # User code execution
{self._indent_code(code, 4)}
    
    # Print success message
    print("EXECUTION_SUCCESS: Code executed successfully")
    sys.exit(0)
    
except Exception as e:
    print(f"EXECUTION_ERROR: {{str(e)}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
    
finally:
    spark.stop()
"""
        return wrapped

    def _indent_code(self, code: str, spaces: int) -> str:
        """Indent code by specified number of spaces.

        Args:
            code: Code to indent.
            spaces: Number of spaces to indent.

        Returns:
            Indented code.
        """
        indent = " " * spaces
        lines = code.split("\n")
        return "\n".join(indent + line if line.strip() else line for line in lines)

    def _build_spark_command(
        self,
        script_path: str,
        job_name: str,
        use_local_mode: bool
    ) -> list:
        """Build spark-submit command.

        Args:
            script_path: Path to the Python script.
            job_name: Spark job name.
            use_local_mode: Whether to use local mode.

        Returns:
            List of command arguments.
        """
        cmd = [
            self.spark_submit_path,
            "--name", job_name,
            "--conf", "spark.sql.shuffle.partitions=10",
        ]

        if use_local_mode:
            cmd.extend(["--master", "local[*]"])

        cmd.append(script_path)

        return cmd

    def _parse_output(self, output: str) -> Dict[str, Any]:
        """Parse execution output for results.

        Args:
            output: stdout from PySpark execution.

        Returns:
            Parsed results dictionary.
        """
        results = {
            "output_lines": output.split("\n"),
            "success": "EXECUTION_SUCCESS" in output,
        }

        # Try to extract any JSON output
        for line in output.split("\n"):
            if line.startswith("{"):
                try:
                    results["data"] = json.loads(line)
                except json.JSONDecodeError:
                    pass

        return results


class LocalSparkExecutor(SparkExecutor):
    """Executor for testing without Spark installation."""

    def execute_code(
        self,
        code: str,
        job_name: str = "etl_job",
        use_local_mode: bool = True,
    ) -> Dict[str, Any]:
        """Execute code in local Python for testing.

        Args:
            code: Python code to execute (should work without Spark).
            job_name: Job name (for logging).
            use_local_mode: Ignored for local executor.

        Returns:
            Execution results.
        """
        logger.info(f"Executing Python code in local mode: {job_name}")
        start_time = datetime.utcnow()

        try:
            # Create a safe execution environment
            exec_globals = {"__name__": "__main__"}
            exec_locals = {}

            # Execute the code
            exec(code, exec_globals, exec_locals)

            duration = (datetime.utcnow() - start_time).total_seconds()

            logger.info(f"Local execution successful in {duration:.2f}s")
            return {
                "status": "success",
                "duration_seconds": duration,
                "stdout": "Code executed successfully (local mode)",
                "stderr": "",
                "execution_result": {
                    "output_lines": ["Code executed successfully"],
                    "success": True,
                },
                "error": None,
            }

        except Exception as e:
            logger.error(f"Local execution failed: {str(e)}", exc_info=True)
            duration = (datetime.utcnow() - start_time).total_seconds()
            return {
                "status": "failed",
                "duration_seconds": duration,
                "stdout": "",
                "stderr": str(e),
                "execution_result": None,
                "error": str(e),
            }
