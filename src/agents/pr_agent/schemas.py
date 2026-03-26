"""Schemas and data models for the PR Agent.

The PR Agent is responsible for creating Git branches, commits, and Pull Requests
for the generated code.
"""

from typing import List, Optional, Dict, Any, Literal
from pydantic import BaseModel, Field


class GitCommit(BaseModel):
    """Git commit information."""

    message: str = Field(..., description="Commit message")
    description: Optional[str] = Field(
        None, description="Detailed commit description"
    )
    files_changed: List[str] = Field(
        default_factory=list, description="List of files changed in commit"
    )
    insertions: int = Field(default=0, description="Number of lines inserted")
    deletions: int = Field(default=0, description="Number of lines deleted")


class GitBranch(BaseModel):
    """Git branch information."""

    branch_name: str = Field(..., description="Name of the branch")
    base_branch: str = Field(
        default="main", description="Base branch to branch from"
    )
    created: bool = Field(default=False, description="Whether branch was created")


class PullRequestTemplate(BaseModel):
    """Pull Request template and structure."""

    title: str = Field(..., description="PR title")
    description: str = Field(..., description="PR description")
    changes_summary: str = Field(..., description="Summary of changes")
    testing_notes: str = Field(..., description="Testing and validation notes")
    breaking_changes: List[str] = Field(
        default_factory=list, description="List of breaking changes if any"
    )
    labels: List[str] = Field(
        default_factory=list, description="GitHub labels to apply"
    )
    reviewers: List[str] = Field(
        default_factory=list, description="Suggested reviewers"
    )


class RepositoryInfo(BaseModel):
    """Repository configuration and information."""

    owner: str = Field(..., description="GitHub repository owner")
    repo_name: str = Field(..., description="GitHub repository name")
    github_token: Optional[str] = Field(
        None, description="GitHub API token (from config)"
    )
    github_url: Optional[str] = Field(
        None, description="Full GitHub repository URL"
    )


class GeneratedPullRequest(BaseModel):
    """Complete generated pull request information."""

    pr_title: str = Field(..., description="Title of the PR")
    pr_description: str = Field(..., description="Description of the PR")
    pr_number: Optional[int] = Field(
        None, description="PR number (assigned by GitHub)"
    )
    pr_url: Optional[str] = Field(None, description="URL to the PR on GitHub")
    branch_name: str = Field(..., description="Name of the feature branch")
    commits: List[GitCommit] = Field(
        ..., description="List of commits in this PR"
    )
    files_changed: List[Dict[str, Any]] = Field(
        default_factory=list,
        description="Files changed with metadata (name, additions, deletions)",
    )
    is_draft: bool = Field(
        default=False, description="Whether PR is in draft mode"
    )
    auto_merge: bool = Field(
        default=False, description="Whether to auto-merge after checks pass"
    )
    assignees: List[str] = Field(
        default_factory=list, description="GitHub usernames to assign PR to"
    )
    labels: List[str] = Field(
        default_factory=list, description="GitHub labels to apply"
    )
    milestone: Optional[str] = Field(None, description="GitHub milestone ID")


class PRAgentInput(BaseModel):
    """Input to the PR Agent."""

    generated_code_files: Dict[str, str] = Field(
        ...,
        description="Dict mapping file paths to code content",
    )
    generated_test_files: Dict[str, str] = Field(
        ...,
        description="Dict mapping test file paths to test code content",
    )
    story_title: str = Field(..., description="Title from the user story")
    story_description: str = Field(..., description="Description from user story")
    test_quality_score: float = Field(
        ..., description="Code quality score from Test Agent"
    )
    code_quality_score: float = Field(
        ..., description="Code quality score from Coding Agent"
    )
    repository: RepositoryInfo = Field(
        ..., description="Repository configuration"
    )
    auto_merge_enabled: bool = Field(
        default=False, description="Whether to enable auto-merge"
    )
    create_draft: bool = Field(
        default=False, description="Whether to create draft PR"
    )
    add_reviewers: List[str] = Field(
        default_factory=list, description="Users to assign as reviewers"
    )
    apply_labels: List[str] = Field(
        default_factory=list, description="Labels to apply to PR"
    )


class PRAgentOutput(BaseModel):
    """Output from the PR Agent."""

    pull_request: GeneratedPullRequest = Field(
        ..., description="Generated PR information"
    )
    pr_created_successfully: bool = Field(
        ..., description="Whether PR was created successfully"
    )
    pr_quality_score: float = Field(
        ..., description="Quality score of the PR (0-1)"
    )
    pr_url: Optional[str] = Field(
        None, description="URL to the created PR on GitHub"
    )
    commit_shas: List[str] = Field(
        default_factory=list, description="List of commit SHAs that were pushed"
    )
    warnings: List[str] = Field(
        default_factory=list, description="Warnings or notes about the PR"
    )
    next_steps: List[str] = Field(
        default_factory=list, description="Recommended next steps"
    )
    raw_response: Optional[Dict[str, Any]] = Field(
        None, description="Raw GitHub API response for debugging"
    )
