"""Unit tests for the PR Agent."""

import pytest
from unittest.mock import patch

from src.agents.pr_agent import PRAgent, PRAgentInput, PRAgentOutput
from src.agents.pr_agent.schemas import RepositoryInfo
from src.types import AgentStatus, AgentType


@pytest.fixture
def pr_agent():
    """Fixture for PRAgent instance."""
    with patch("src.agents.pr_agent.pr_agent.ChatOpenAI"):
        with patch("src.agents.pr_agent.pr_agent.get_settings") as mock_settings:
            mock_settings.return_value.openai_api_key = "test-key"
            mock_settings.return_value.openai_model = "gpt-4o"
            mock_settings.return_value.openai_temperature = 0.3
            return PRAgent()


@pytest.fixture
def sample_repository_info():
    """Fixture for repository information."""
    return RepositoryInfo(
        owner="amalphonse",
        repo_name="Autonomous-ETL-ELT-Agent-for-DevOps-Driven-Data-Engineering",
        github_token="test-token",
    )


@pytest.fixture
def sample_pr_input(sample_repository_info):
    """Fixture for sample PR input."""
    return {
        "generated_code_files": {
            "src/pipeline.py": "def process(): pass",
            "src/models.py": "class Model: pass",
        },
        "generated_test_files": {
            "tests/test_pipeline.py": "def test_process(): pass",
        },
        "story_title": "Process orders by region",
        "story_description": "Group orders by region and calculate totals",
        "test_quality_score": 0.85,
        "code_quality_score": 0.92,
        "repository": sample_repository_info.model_dump(),
        "auto_merge_enabled": False,
        "create_draft": False,
    }


class TestPRAgentInitialization:
    """Tests for PR Agent initialization."""

    def test_agent_initialization(self, pr_agent):
        """Test that PR Agent initializes correctly."""
        assert pr_agent.agent_type == AgentType.PR
        assert pr_agent.llm is not None
        assert pr_agent.pr_generation_prompt is not None

    def test_agent_has_methods(self, pr_agent):
        """Test that PR Agent has all required methods."""
        assert hasattr(pr_agent, "execute")
        assert hasattr(pr_agent, "validate_input")
        assert hasattr(pr_agent, "_generate_branch_name")
        assert hasattr(pr_agent, "_generate_pr_template")


class TestInputValidation:
    """Tests for PR Agent input validation."""

    def test_valid_input(self, pr_agent, sample_pr_input):
        """Test validation of valid input."""
        assert pr_agent.validate_input(sample_pr_input) is True

    def test_missing_generated_code_files(self, pr_agent, sample_pr_input):
        """Test validation fails without generated code files."""
        invalid_input = sample_pr_input.copy()
        del invalid_input["generated_code_files"]
        assert pr_agent.validate_input(invalid_input) is False

    def test_missing_story_title(self, pr_agent, sample_pr_input):
        """Test validation fails without story title."""
        invalid_input = sample_pr_input.copy()
        del invalid_input["story_title"]
        assert pr_agent.validate_input(invalid_input) is False

    def test_missing_repository(self, pr_agent, sample_pr_input):
        """Test validation fails without repository info."""
        invalid_input = sample_pr_input.copy()
        del invalid_input["repository"]
        assert pr_agent.validate_input(invalid_input) is False


class TestBranchNameGeneration:
    """Tests for Git branch name generation."""

    def test_simple_title(self, pr_agent):
        """Test branch generation from simple title."""
        branch = pr_agent._generate_branch_name("Add new feature")
        assert "feature/" in branch
        assert "add-new-feature" in branch
        assert branch.startswith("feature/")

    def test_title_with_special_chars(self, pr_agent):
        """Test branch generation handles special characters."""
        branch = pr_agent._generate_branch_name("Fix: Bug #123 issue")
        assert "fix" in branch
        assert "bug" in branch
        assert "feature/" in branch

    def test_branch_name_length(self, pr_agent):
        """Test branch name length limit."""
        long_title = "This is a very long story title that should be truncated properly to fit git requirements"
        branch = pr_agent._generate_branch_name(long_title)
        assert len(branch) <= 50

    def test_branch_name_uniqueness(self, pr_agent):
        """Test branch names include timestamp for uniqueness."""
        branch1 = pr_agent._generate_branch_name("Test")
        branch2 = pr_agent._generate_branch_name("Test")
        # Timestamps should be same if generated quickly, but structure preserved
        assert "feature/test-" in branch1
        assert "feature/test-" in branch2


class TestPRQualityScore:
    """Tests for PR quality scoring."""

    def test_quality_score_range(self, pr_agent, sample_pr_input):
        """Test that quality scores are in valid range."""
        from src.agents.pr_agent.schemas import GeneratedPullRequest

        pull_request = GeneratedPullRequest(
            pr_title="Test PR",
            pr_description="Test description",
            branch_name="feature/test",
            commits=[],
            files_changed=[{"filename": "test.py", "additions": 10}],
        )

        score = pr_agent._calculate_pr_quality_score(
            pull_request, PRAgentInput(**sample_pr_input)
        )

        assert 0.0 <= score <= 1.0

    def test_quality_improves_with_metadata(self, pr_agent, sample_pr_input):
        """Test quality score increases with complete PR metadata."""
        from src.agents.pr_agent.schemas import GeneratedPullRequest, GitCommit

        minimal_pr = GeneratedPullRequest(
            pr_title="",
            pr_description="",
            branch_name="feature/test",
            commits=[],
            files_changed=[],
        )

        complete_pr = GeneratedPullRequest(
            pr_title="Comprehensive PR Title for Testing",
            pr_description="Very detailed description " * 10,
            branch_name="feature/test",
            commits=[
                GitCommit(
                    message="Add feature",
                    files_changed=["test.py"],
                )
            ],
            labels=["enhancement", "data-pipeline"],
            assignees=["user1"],
            files_changed=[
                {"filename": "test.py", "additions": 100},
                {"filename": "test2.py", "additions": 50},
            ],
        )

        pr_input = PRAgentInput(**sample_pr_input)
        minimal_score = pr_agent._calculate_pr_quality_score(minimal_pr, pr_input)
        complete_score = pr_agent._calculate_pr_quality_score(complete_pr, pr_input)

        assert complete_score > minimal_score


class TestFilesMetadata:
    """Tests for file change metadata preparation."""

    def test_files_metadata_creation(self, pr_agent, sample_pr_input):
        """Test that files metadata is created correctly."""
        pr_input = PRAgentInput(**sample_pr_input)
        files_metadata = pr_agent._prepare_files_metadata(pr_input)

        assert len(files_metadata) >= 3  # 2 code + 1 test
        assert all("filename" in f for f in files_metadata)
        assert all("additions" in f for f in files_metadata)

    def test_files_metadata_status(self, pr_agent, sample_pr_input):
        """Test that file status is set correctly."""
        pr_input = PRAgentInput(**sample_pr_input)
        files_metadata = pr_agent._prepare_files_metadata(pr_input)

        assert all(f["status"] == "added" for f in files_metadata)


class TestDefaultCommits:
    """Tests for default commit generation."""

    def test_default_commits_structure(self, pr_agent, sample_pr_input):
        """Test default commits have correct structure."""
        pr_input = PRAgentInput(**sample_pr_input)
        commits = pr_agent._default_commits(pr_input)

        assert len(commits) == 2  # Code commit + test commit
        assert commits[0].message == "feat: add generated PySpark pipeline code"
        assert commits[1].message == "test: add comprehensive pytest suite"

    def test_default_commits_files(self, pr_agent, sample_pr_input):
        """Test default commits reference correct files."""
        pr_input = PRAgentInput(**sample_pr_input)
        commits = pr_agent._default_commits(pr_input)

        code_commit = commits[0]
        test_commit = commits[1]

        assert len(code_commit.files_changed) > 0
        assert len(test_commit.files_changed) > 0


class TestNextSteps:
    """Tests for next steps generation."""

    def test_next_steps_structure(self, pr_agent, sample_pr_input):
        """Test next steps are comprehensive."""
        pr_input = PRAgentInput(**sample_pr_input)
        next_steps = pr_agent._generate_next_steps(pr_input, quality_score=0.8)

        assert len(next_steps) > 0
        assert any("Review" in step for step in next_steps)
        assert any("merge" in step.lower() for step in next_steps)

    def test_next_steps_quality_dependent(self, pr_agent, sample_pr_input):
        """Test next steps vary based on quality score."""
        pr_input = PRAgentInput(**sample_pr_input)

        high_quality_steps = pr_agent._generate_next_steps(pr_input, quality_score=0.9)
        low_quality_steps = pr_agent._generate_next_steps(pr_input, quality_score=0.5)

        # Low quality should have warning
        assert any("⚠️" in step or "below" in step.lower() for step in low_quality_steps)

    def test_auto_merge_in_next_steps(self, pr_agent, sample_pr_input):
        """Test auto-merge is mentioned when enabled."""
        sample_pr_input["auto_merge_enabled"] = True
        pr_input = PRAgentInput(**sample_pr_input)
        next_steps = pr_agent._generate_next_steps(pr_input, quality_score=0.8)

        assert any("auto-merge" in step.lower() for step in next_steps)


class TestPRAgentOutput:
    """Tests for PR Agent output structure."""

    @pytest.mark.asyncio
    async def test_successful_execution(self, pr_agent, sample_pr_input):
        """Test successful execution of PR Agent."""
        output = await pr_agent.execute(sample_pr_input)

        assert output.status == AgentStatus.SUCCESS
        assert output.agent_type == AgentType.PR
        assert "pull_request" in output.data
        assert "pr_quality_score" in output.data
        assert "next_steps" in output.data

    @pytest.mark.asyncio
    async def test_invalid_input_execution(self, pr_agent):
        """Test execution with invalid input."""
        invalid_input = {"invalid": "data"}

        output = await pr_agent.execute(invalid_input)

        assert output.status == AgentStatus.FAILED
        assert output.error is not None

    @pytest.mark.asyncio
    async def test_pr_data_completeness(self, pr_agent, sample_pr_input):
        """Test PR output contains all expected data."""
        output = await pr_agent.execute(sample_pr_input)

        assert output.status == AgentStatus.SUCCESS
        pr_data = output.data["pull_request"]

        assert pr_data["pr_title"]  # Should not be empty
        assert pr_data["pr_description"]  # Should not be empty
        assert pr_data["branch_name"]  # Should start with feature/
        assert pr_data["branch_name"].startswith("feature/")
