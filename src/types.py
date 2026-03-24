"""Base agent types and abstractions for the multi-agent orchestration system."""

from typing import Any, Dict, Optional
from enum import Enum
from pydantic import BaseModel, Field
from abc import ABC, abstractmethod


class AgentType(str, Enum):
    """Enumeration of agent types in the orchestration system."""

    TASK = "task"
    CODING = "coding"
    TEST = "test"
    PR = "pr"


class AgentStatus(str, Enum):
    """Status of an agent execution."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    COMPLETED = "completed"


class AgentInput(BaseModel):
    """Base model for agent input."""

    user_id: Optional[str] = None
    request_id: Optional[str] = Field(default=None, description="Unique request identifier")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


class AgentOutput(BaseModel):
    """Base model for agent output."""

    agent_type: AgentType
    status: AgentStatus
    data: Dict[str, Any] = Field(default_factory=dict, description="Output data")
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Execution metadata")


class Agent(ABC):
    """Abstract base class for all agents in the system."""

    def __init__(self, agent_type: AgentType):
        """Initialize the agent.

        Args:
            agent_type: Type of agent being initialized.
        """
        self.agent_type = agent_type

    @abstractmethod
    async def execute(self, agent_input: AgentInput) -> AgentOutput:
        """Execute the agent with the given input.

        Args:
            agent_input: Input data for the agent.

        Returns:
            AgentOutput with the execution results.
        """
        pass

    @abstractmethod
    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate the input for this agent.

        Args:
            agent_input: Input data to validate.

        Returns:
            True if input is valid, False otherwise.
        """
        pass


class OrchestrationState(BaseModel):
    """State maintained throughout the orchestration workflow."""

    request_id: str
    user_story: Optional[Dict[str, Any]] = None
    task_agent_output: Optional[AgentOutput] = None
    coding_agent_output: Optional[AgentOutput] = None
    test_agent_output: Optional[AgentOutput] = None
    pr_agent_output: Optional[AgentOutput] = None
    errors: list = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
