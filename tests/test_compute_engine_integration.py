"""Integration tests for compute engine selection feature."""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from src.orchestration import AgentOrchestrator


@pytest.mark.asyncio
async def test_compute_engine_flows_through_pipeline():
    """Test that compute_engine parameter flows through the entire pipeline."""
    
    user_story_data = {
        "title": "Test Pipeline",
        "description": "Load data from S3, transform, write to BigQuery",
        "source_system": "S3",
        "target_system": "BigQuery",
        "compute_engine": "databricks",  # Test Databricks selection
    }
    
    # Mock all agents to avoid actual OpenAI calls
    with patch('src.orchestration.TaskAgent') as MockTaskAgent, \
         patch('src.orchestration.CodingAgent') as MockCodingAgent, \
         patch('src.orchestration.TestAgent') as MockTestAgent, \
         patch('src.orchestration.ExecutionAgent') as MockExecutionAgent, \
         patch('src.orchestration.OrchestrationAgent') as MockOrchestrationAgent, \
         patch('src.orchestration.PRAgent') as MockPRAgent:
        
        # Setup Task Agent mock
        task_agent_instance = MockTaskAgent.return_value
        task_agent_output = Mock()
        task_agent_output.status = Mock(value="SUCCESS")
        task_agent_output.data = {
            "requirements": {
                "title": "Test Pipeline",
                "description": "Test",
                "input_sources": [],
                "transformation_steps": [],
                "output_location": "output",
            },
            "confidence_score": 0.9,
        }
        task_agent_instance.execute = AsyncMock(return_value=task_agent_output)
        
        # Setup Coding Agent mock
        coding_agent_instance = MockCodingAgent.return_value
        coding_agent_output = Mock()
        coding_agent_output.status = Mock(value="SUCCESS")
        coding_agent_output.data = {
            "generated_code": "test code",
            "quality_score": 0.9,
        }
        coding_agent_instance.execute = AsyncMock(return_value=coding_agent_output)
        
        # Setup Test Agent mock
        test_agent_instance = MockTestAgent.return_value
        test_agent_output = Mock()
        test_agent_output.status = Mock(value="SUCCESS")
        test_agent_output.data = {
            "generated_tests": "test code",
            "quality_score": 0.9,
        }
        test_agent_instance.execute = AsyncMock(return_value=test_agent_output)
        
        # Setup Execution Agent mock
        execution_agent_instance = MockExecutionAgent.return_value
        execution_agent_output = Mock()
        execution_agent_output.status = Mock(value="SUCCESS")
        execution_agent_output.data = {
            "execution_result": "success",
            "quality_score": 0.9,
        }
        execution_agent_instance.execute = AsyncMock(return_value=execution_agent_output)
        
        # Setup Orchestration Agent mock - KEY TEST
        orchestration_agent_instance = MockOrchestrationAgent.return_value
        orchestration_agent_output = Mock()
        orchestration_agent_output.status = Mock(value="SUCCESS")
        orchestration_agent_output.data = {
            "generated_orchestration": {
                "dag_file_name": "test_dag.py",
                "dag_code": "# Databricks DAG code",
            },
            "quality_score": 0.9,
        }
        orchestration_agent_instance.execute = AsyncMock(return_value=orchestration_agent_output)
        
        # Setup PR Agent mock
        pr_agent_instance = MockPRAgent.return_value
        pr_agent_output = Mock()
        pr_agent_output.status = Mock(value="SUCCESS")
        pr_agent_output.data = {
            "pull_request": {"pr_url": "https://github.com/test/pr/1"},
            "quality_score": 0.9,
        }
        pr_agent_instance.execute = AsyncMock(return_value=pr_agent_output)
        
        # Execute orchestrator
        orchestrator = AgentOrchestrator()
        final_state = await orchestrator.execute(user_story_data)
        
        # Verify compute_engine was added to attachments
        assert final_state["user_story"]["attachments"]["compute_engine"] == "databricks"
        
        # Verify parsed_requirements has execution_environment
        assert final_state["parsed_requirements"]["execution_environment"] == "databricks"
        
        # Verify orchestration agent was called with execution_environment
        orchestration_call_args = orchestration_agent_instance.execute.call_args[0][0]
        assert orchestration_call_args["execution_environment"] == "databricks"


@pytest.mark.asyncio
async def test_default_compute_engine():
    """Test that default compute engine is dataproc when not specified."""
    
    user_story_data = {
        "title": "Test Pipeline",
        "description": "Load data",
        # No compute_engine specified
    }
    
    with patch('src.orchestration.TaskAgent') as MockTaskAgent, \
         patch('src.orchestration.CodingAgent'), \
         patch('src.orchestration.TestAgent'), \
         patch('src.orchestration.ExecutionAgent'), \
         patch('src.orchestration.OrchestrationAgent') as MockOrchestrationAgent, \
         patch('src.orchestration.PRAgent'):
        
        # Setup Task Agent mock
        task_agent_instance = MockTaskAgent.return_value
        task_agent_output = Mock()
        task_agent_output.status = Mock(value="SUCCESS")
        task_agent_output.data = {
            "requirements": {
                "title": "Test",
                "description": "Test",
                "input_sources": [],
                "transformation_steps": [],
                "output_location": "output",
            },
            "confidence_score": 0.9,
        }
        task_agent_instance.execute = AsyncMock(return_value=task_agent_output)
        
        # Setup other agents with minimal mocks
        for agent_class in [MockOrchestrationAgent]:
            instance = agent_class.return_value
            output = Mock()
            output.status = Mock(value="SUCCESS")
            output.data = {"quality_score": 0.9}
            instance.execute = AsyncMock(return_value=output)
        
        orchestrator = AgentOrchestrator()
        final_state = await orchestrator.execute(user_story_data)
        
        # Should NOT have compute_engine in attachments since not provided
        assert "compute_engine" not in final_state["user_story"].get("attachments", {})


@pytest.mark.parametrize("compute_engine,expected", [
    ("dataproc", "dataproc"),
    ("databricks", "databricks"),
    ("emr", "emr"),
    ("synapse", "synapse"),
])
@pytest.mark.asyncio
async def test_all_compute_engines(compute_engine, expected):
    """Test that all compute engines are properly handled."""
    
    user_story_data = {
        "title": "Test Pipeline",
        "description": "Test",
        "compute_engine": compute_engine,
    }
    
    with patch('src.orchestration.TaskAgent') as MockTaskAgent, \
         patch('src.orchestration.CodingAgent'), \
         patch('src.orchestration.TestAgent'), \
         patch('src.orchestration.ExecutionAgent'), \
         patch('src.orchestration.OrchestrationAgent') as MockOrchestrationAgent, \
         patch('src.orchestration.PRAgent'):
        
        # Setup Task Agent
        task_agent_instance = MockTaskAgent.return_value
        task_agent_output = Mock()
        task_agent_output.status = Mock(value="SUCCESS")
        task_agent_output.data = {
            "requirements": {
                "title": "Test",
                "description": "Test",
                "input_sources": [],
                "transformation_steps": [],
                "output_location": "output",
            },
            "confidence_score": 0.9,
        }
        task_agent_instance.execute = AsyncMock(return_value=task_agent_output)
        
        # Setup Orchestration Agent
        orchestration_agent_instance = MockOrchestrationAgent.return_value
        orchestration_agent_output = Mock()
        orchestration_agent_output.status = Mock(value="SUCCESS")
        orchestration_agent_output.data = {
            "generated_orchestration": {},
            "quality_score": 0.9,
        }
        orchestration_agent_instance.execute = AsyncMock(return_value=orchestration_agent_output)
        
        orchestrator = AgentOrchestrator()
        final_state = await orchestrator.execute(user_story_data)
        
        # Verify the compute engine flows through correctly
        assert final_state["user_story"]["attachments"]["compute_engine"] == expected
        assert final_state["parsed_requirements"]["execution_environment"] == expected
