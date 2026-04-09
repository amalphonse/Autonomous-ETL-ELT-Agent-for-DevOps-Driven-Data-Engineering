"""PR Agent implementation for creating Git branches, commits, and Pull Requests."""

import json
import logging
from typing import Optional, Dict, Any, List
from datetime import datetime
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate

try:
    from github import Github, GithubException
    GITHUB_AVAILABLE = True
except ImportError:
    GITHUB_AVAILABLE = False

from src.config import get_settings
from src.types import Agent, AgentType, AgentStatus, AgentInput, AgentOutput
from src.agents.pr_agent.schemas import (
    PRAgentInput,
    PRAgentOutput,
    GeneratedPullRequest,
    GitCommit,
    PullRequestTemplate,
)

logger = logging.getLogger(__name__)


class PRAgent(Agent):
    """PR Agent: Creates Git branches, commits, and Pull Requests.

    This agent takes generated code and tests from previous agents and:
    - Creates a feature branch
    - Prepares commits with meaningful messages
    - Generates comprehensive PR descriptions
    - Creates Pull Requests via GitHub API
    - Manages PR metadata (labels, reviewers, etc.)
    """

    def __init__(self):
        """Initialize the PR Agent with LangChain components."""
        super().__init__(AgentType.PR)
        self.settings = get_settings()
        self.llm = ChatOpenAI(
            model=self.settings.openai_model,
            temperature=self.settings.openai_temperature,
            api_key=self.settings.openai_api_key,
        )
        self._setup_prompts()

    def _setup_prompts(self):
        """Set up LangChain prompts for PR generation."""
        self.pr_generation_prompt = ChatPromptTemplate.from_template(
            """You are an expert software engineer creating Pull Requests.
Your task is to generate a comprehensive PR description based on generated code.

Story Title: {story_title}
Story Description: {story_description}

Generated Code Files: {file_list}
Generated Test Files: {test_file_list}

Code Quality Score: {code_quality_score}
Test Quality Score: {test_quality_score}

Generate a JSON object with the following structure:
{{
  "title": "Clear, concise PR title (max 80 chars)",
  "description": "Comprehensive PR description with motivation and context",
  "changes_summary": "Bullet-point summary of changes",
  "testing_notes": "How to test these changes, what tests are included",
  "breaking_changes": [],
  "labels": ["enhancement", "data-pipeline"],
  "reviewers": []
}}

Requirements for the PR:
1. Title should be clear and descriptive
2. Description should explain the "why" behind changes
3. Include testing approach and coverage
4. Mention any configuration or deployment notes
5. Be concise but comprehensive
6. Use markdown formatting
7. Include code examples if relevant
8. Suggest appropriate labels and reviewers
9. Highlight any risks or limitations
10. Provide clear testing instructions for reviewers"""
        )

        self.commit_message_prompt = ChatPromptTemplate.from_template(
            """You are an expert at writing clear commit messages.
Based on these files being changed, generate clear, concise commit messages.

Files Changed:
{files_changed}

Story Context:
{story_context}

Generate JSON array of commits:
[
  {{
    "message": "Brief commit message (imperative mood)",
    "description": "Longer description if needed",
    "files_changed": ["list", "of", "files"]
  }}
]

Requirements:
1. Use imperative mood (e.g., "Add feature" not "Added feature")
2. First line should be <= 72 characters
3. Include context in description
4. Group related changes in single commit"""
        )

    async def execute(self, agent_input: AgentInput) -> AgentOutput:
        """Execute the PR Agent to create a Pull Request.

        Args:
            agent_input: Should be PRAgentInput with generated code and tests.

        Returns:
            AgentOutput with PR information and creation status.
        """
        try:
            # Validate input
            if not self.validate_input(agent_input):
                return self._error_output("Invalid input format. Expected PRAgentInput.")

            # Convert to dict if needed and then to PRAgentInput
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()

            pr_input = PRAgentInput(**agent_input_dict)

            logger.info(
                f"PR Agent processing: {pr_input.story_title}"
            )

            # Step 1: Generate branch name from story
            branch_name = self._generate_branch_name(pr_input.story_title)
            logger.debug(f"Generated branch name: {branch_name}")

            # Step 2: Generate PR description and metadata
            logger.debug("Generating PR description...")
            pr_template = self._generate_pr_template(pr_input)

            # Step 3: Generate commit messages
            logger.debug("Generating commit messages...")
            commits = self._generate_commits(pr_input)

            # Step 4: Calculate files changed
            files_changed = self._prepare_files_metadata(pr_input)

            # Step 5: Build PR object
            pull_request = GeneratedPullRequest(
                pr_title=pr_template.title,
                pr_description=pr_template.description,
                branch_name=branch_name,
                commits=commits,
                files_changed=files_changed,
                is_draft=pr_input.create_draft,
                auto_merge=pr_input.auto_merge_enabled,
                assignees=pr_input.add_reviewers,
                labels=pr_input.apply_labels if pr_input.apply_labels else pr_template.labels,
            )

            # Step 6: Calculate quality score
            quality_score = self._calculate_pr_quality_score(
                pull_request, pr_input
            )

            # Step 7: Generate next steps
            next_steps = self._generate_next_steps(pr_input, quality_score)

            # Step 8: Create actual GitHub PR
            pr_url = None
            pr_number = None
            pr_created = False
            try:
                pr_url, pr_number = self._create_github_pr(
                    pr_input, pull_request, branch_name, pr_template
                )
                pr_created = pr_url is not None
                if pr_url:
                    pull_request.pr_url = pr_url
                    pull_request.pr_number = pr_number
                    logger.info(f"GitHub PR created: {pr_url}")
            except Exception as gh_err:
                logger.warning(f"GitHub PR creation failed (non-fatal): {gh_err}")

            # Step 9: Create output
            pr_output = PRAgentOutput(
                pull_request=pull_request,
                pr_created_successfully=pr_created,
                pr_quality_score=quality_score,
                pr_url=pr_url,
                commit_shas=[],
                next_steps=next_steps,
            )

            logger.info(f"PR Agent completed with quality score: {quality_score:.2f}")

            return AgentOutput(
                agent_type=self.agent_type,
                status=AgentStatus.SUCCESS,
                data=pr_output.model_dump(),
            )

        except Exception as e:
            logger.error(f"PR Agent execution failed: {str(e)}")
            return self._error_output(f"PR Agent failed: {str(e)}")

    def _create_github_pr(
        self,
        pr_input: "PRAgentInput",
        pull_request: GeneratedPullRequest,
        branch_name: str,
        pr_template: "PullRequestTemplate",
    ):
        """Create an actual GitHub Pull Request using PyGithub.

        Returns:
            Tuple of (pr_url, pr_number) or (None, None) on failure.
        """
        if not GITHUB_AVAILABLE:
            logger.warning("PyGithub not installed — skipping GitHub PR creation")
            return None, None

        token = (
            pr_input.repository.github_token
            or self.settings.github_token
        )
        if not token:
            logger.warning("No GitHub token configured — skipping PR creation")
            return None, None

        owner = pr_input.repository.owner or self.settings.github_repo_owner
        repo_name = pr_input.repository.repo_name or self.settings.github_repo_name
        if not owner or not repo_name:
            logger.warning("GitHub owner/repo not configured — skipping PR creation")
            return None, None

        try:
            gh = Github(token)
            repo = gh.get_repo(f"{owner}/{repo_name}")

            # Get default branch
            default_branch = repo.default_branch  # e.g. "main"
            base_sha = repo.get_branch(default_branch).commit.sha

            # Create feature branch
            try:
                repo.create_git_ref(ref=f"refs/heads/{branch_name}", sha=base_sha)
                logger.info(f"Created branch: {branch_name}")
            except GithubException as e:
                if e.status == 422:  # branch already exists
                    logger.warning(f"Branch {branch_name} already exists, reusing")
                else:
                    raise

            # Commit all code + test files to the branch
            all_files = {}
            all_files.update(pr_input.generated_code_files)
            all_files.update(pr_input.generated_test_files)

            for file_path, content in all_files.items():
                if not content or not content.strip():
                    continue
                try:
                    # Try to update if exists, else create
                    try:
                        existing = repo.get_contents(file_path, ref=branch_name)
                        repo.update_file(
                            path=file_path,
                            message=f"Update {file_path} via ETL agent",
                            content=content,
                            sha=existing.sha,
                            branch=branch_name,
                        )
                    except GithubException:
                        repo.create_file(
                            path=file_path,
                            message=f"Add {file_path} via ETL agent",
                            content=content,
                            branch=branch_name,
                        )
                except Exception as fe:
                    logger.warning(f"Failed to commit {file_path}: {fe}")

            # Create the Pull Request
            pr_body = pr_template.description
            if pr_template.changes_summary:
                pr_body += f"\n\n## Changes\n{pr_template.changes_summary}"
            if pr_template.testing_notes:
                pr_body += f"\n\n## Testing\n{pr_template.testing_notes}"

            gh_pr = repo.create_pull(
                title=pull_request.pr_title,
                body=pr_body,
                head=branch_name,
                base=default_branch,
                draft=pull_request.is_draft,
            )

            # Apply labels if any
            if pull_request.labels:
                try:
                    gh_pr.add_to_labels(*pull_request.labels)
                except Exception:
                    pass

            logger.info(f"GitHub PR #{gh_pr.number} created: {gh_pr.html_url}")
            return gh_pr.html_url, gh_pr.number

        except Exception as e:
            logger.error(f"GitHub PR creation error: {e}")
            return None, None

    def validate_input(self, agent_input: AgentInput) -> bool:
        """Validate that the input is valid for PR creation.

        Args:
            agent_input: Input to validate.

        Returns:
            True if valid, False otherwise.
        """
        try:
            if isinstance(agent_input, dict):
                agent_input_dict = agent_input
            else:
                agent_input_dict = agent_input.model_dump()

            # Check for required fields
            required_fields = [
                "generated_code_files",
                "generated_test_files",
                "story_title",
                "story_description",
                "repository",
            ]

            for field in required_fields:
                if field not in agent_input_dict:
                    logger.warning(f"Missing '{field}' in agent input")
                    return False

            # Try to validate as PRAgentInput
            PRAgentInput(**agent_input_dict)
            return True

        except Exception as e:
            logger.warning(f"Input validation failed: {str(e)}")
            return False

    def _generate_branch_name(self, story_title: str) -> str:
        """Generate a Git branch name from story title.

        Args:
            story_title: The user story title.

        Returns:
            Valid Git branch name.
        """
        # Sanitize: lowercase, replace spaces with hyphens, remove special chars
        branch_name = story_title.lower()
        branch_name = branch_name.replace(" ", "-")
        branch_name = "".join(c for c in branch_name if c.isalnum() or c == "-")
        branch_name = branch_name.strip("-")

        # Add timestamp component for uniqueness
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        branch_name = f"feature/{branch_name}-{timestamp[:8]}"

        return branch_name[:50]  # Git has limits

    def _generate_pr_template(self, pr_input: PRAgentInput) -> PullRequestTemplate:
        """Generate PR template using LLM.

        Args:
            pr_input: PR input data.

        Returns:
            PullRequestTemplate object.
        """
        try:
            chain = self.pr_generation_prompt | self.llm

            file_list = ", ".join(list(pr_input.generated_code_files.keys())[:10])
            test_file_list = ", ".join(
                list(pr_input.generated_test_files.keys())[:5]
            )

            response = chain.invoke(
                {
                    "story_title": pr_input.story_title,
                    "story_description": pr_input.story_description,
                    "file_list": file_list,
                    "test_file_list": test_file_list,
                    "code_quality_score": f"{pr_input.code_quality_score:.2%}",
                    "test_quality_score": f"{pr_input.test_quality_score:.2%}",
                }
            )

            pr_data = json.loads(self._extract_json(response.content))

            return PullRequestTemplate(
                title=pr_data.get("title", pr_input.story_title),
                description=pr_data.get("description", pr_input.story_description),
                changes_summary=pr_data.get(
                    "changes_summary", "See generated code files"
                ),
                testing_notes=pr_data.get("testing_notes", "Run pytest suite"),
                breaking_changes=pr_data.get("breaking_changes", []),
                labels=pr_data.get("labels", []),
                reviewers=pr_data.get("reviewers", []),
            )
        except Exception as e:
            logger.warning(f"LLM PR generation failed: {str(e)}")
            # Fallback to basic template
            return PullRequestTemplate(
                title=pr_input.story_title,
                description=pr_input.story_description,
                changes_summary="See generated code and tests",
                testing_notes="Run pytest suite to validate changes",
                breaking_changes=[],
                labels=["enhancement"],
                reviewers=[],
            )

    def _generate_commits(self, pr_input: PRAgentInput) -> List[GitCommit]:
        """Generate commit messages for the changes.

        Args:
            pr_input: PR input data.

        Returns:
            List of GitCommit objects.
        """
        try:
            files_list = list(pr_input.generated_code_files.keys())
            test_files_list = list(pr_input.generated_test_files.keys())

            chain = self.commit_message_prompt | self.llm

            response = chain.invoke(
                {
                    "files_changed": "\n".join(files_list + test_files_list),
                    "story_context": pr_input.story_title,
                }
            )

            commits_data = json.loads(self._extract_json(response.content))

            commits = []
            for commit_data in commits_data:
                commits.append(
                    GitCommit(
                        message=commit_data.get("message", "Add generated pipeline"),
                        description=commit_data.get("description"),
                        files_changed=commit_data.get("files_changed", files_list),
                        insertions=len(pr_input.generated_code_files)
                        * 50,  # Estimation
                        deletions=0,
                    )
                )

            return commits if commits else self._default_commits(pr_input)

        except Exception as e:
            logger.warning(f"LLM commit generation failed: {str(e)}")
            return self._default_commits(pr_input)

    def _default_commits(self, pr_input: PRAgentInput) -> List[GitCommit]:
        """Generate default commits if LLM fails.

        Args:
            pr_input: PR input data.

        Returns:
            List of default GitCommit objects.
        """
        return [
            GitCommit(
                message="feat: add generated PySpark pipeline code",
                description="Add pipeline implementation with schema models",
                files_changed=list(pr_input.generated_code_files.keys()),
                insertions=len(pr_input.generated_code_files) * 50,
            ),
            GitCommit(
                message="test: add comprehensive pytest suite",
                description="Add unit, integration, and validation tests",
                files_changed=list(pr_input.generated_test_files.keys()),
                insertions=len(pr_input.generated_test_files) * 50,
            ),
        ]

    def _prepare_files_metadata(self, pr_input: PRAgentInput) -> List[Dict[str, Any]]:
        """Prepare metadata for changed files.

        Args:
            pr_input: PR input data.

        Returns:
            List of file change metadata.
        """
        files_changed = []

        for file_path, content in pr_input.generated_code_files.items():
            files_changed.append(
                {
                    "filename": file_path,
                    "additions": len(content.split("\n")),
                    "deletions": 0,
                    "status": "added",
                }
            )

        for file_path, content in pr_input.generated_test_files.items():
            files_changed.append(
                {
                    "filename": file_path,
                    "additions": len(content.split("\n")),
                    "deletions": 0,
                    "status": "added",
                }
            )

        return files_changed

    def _extract_json(self, text: str) -> str:
        """Extract JSON from text, handling markdown wrapping.

        Args:
            text: Text containing JSON.

        Returns:
            Clean JSON string.
        """
        # Try direct JSON parse
        try:
            json.loads(text)
            return text
        except json.JSONDecodeError:
            pass

        # Try to find JSON in text
        start_idx = text.find("{")
        end_idx = text.rfind("}") + 1

        if start_idx != -1 and end_idx > start_idx:
            json_str = text[start_idx:end_idx]
            try:
                json.loads(json_str)
                return json_str
            except json.JSONDecodeError:
                pass

        raise ValueError(f"Could not extract valid JSON from response: {text}")

    def _calculate_pr_quality_score(
        self, pull_request: GeneratedPullRequest, pr_input: PRAgentInput
    ) -> float:
        """Calculate quality score for the PR.

        Args:
            pull_request: Generated PR object.
            pr_input: Original input.

        Returns:
            Quality score between 0 and 1.
        """
        score = 0.6  # Base score

        # Code quality contribution
        score += pr_input.code_quality_score * 0.15

        # Test quality contribution
        score += pr_input.test_quality_score * 0.15

        # PR metadata quality
        if pull_request.pr_title and len(pull_request.pr_title) > 10:
            score += 0.05

        if pull_request.pr_description and len(pull_request.pr_description) > 100:
            score += 0.05

        if pull_request.commits and len(pull_request.commits) > 0:
            score += 0.05

        if pull_request.labels:
            score += 0.03

        if pull_request.assignees:
            score += 0.02

        # Files changed completeness
        if pull_request.files_changed and len(pull_request.files_changed) > 0:
            score += 0.04

        return min(1.0, score)

    def _generate_next_steps(
        self, pr_input: PRAgentInput, quality_score: float
    ) -> List[str]:
        """Generate recommended next steps.

        Args:
            pr_input: PR input data.
            quality_score: Calculated quality score.

        Returns:
            List of next step recommendations.
        """
        next_steps = []

        # Basic next step
        next_steps.append(
            "1. Review the generated Pull Request for correctness"
        )

        # If quality is lower, suggest review
        if quality_score < 0.75:
            next_steps.append(
                "2. ⚠️  Code quality is below target - review for potential improvements"
            )
        else:
            next_steps.append("2. ✅ Code quality is acceptable - proceed to review")

        # GitHub specific steps
        next_steps.append("3. Request reviews from team members")
        next_steps.append("4. Run CI/CD pipeline and verify all checks pass")
        next_steps.append("5. If approved, merge to main branch")

        # Auto-merge info
        if pr_input.auto_merge_enabled:
            next_steps.append("6. PR will auto-merge when all checks pass")

        return next_steps

    def _error_output(self, error_message: str) -> AgentOutput:
        """Create an error output.

        Args:
            error_message: Error message.

        Returns:
            AgentOutput with error status.
        """
        return AgentOutput(
            agent_type=self.agent_type,
            status=AgentStatus.FAILED,
            error=error_message,
        )
