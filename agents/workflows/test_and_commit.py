"""Test and Commit workflow - automated testing and committing.

This workflow handles:
1. Run test suite
2. Analyze coverage
3. Fix any failures (optional)
4. Stage changes
5. Create commit with descriptive message
6. Push to remote (optional)
"""

import asyncio
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.executor import ToolExecutor, ExecutionResult
from agents.confirmation import ConfirmationManager, RiskAssessor, RiskLevel

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Types
# ═══════════════════════════════════════════════════════════════════════════════


class TestPhase(str, Enum):
    """Phases of the test workflow."""

    TEST = "test"
    COVERAGE = "coverage"
    FIX = "fix"
    STAGE = "stage"
    COMMIT = "commit"
    PUSH = "push"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class TestResult:
    """Result of running tests."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration_seconds: float = 0.0
    output: str = ""
    failed_tests: List[str] = field(default_factory=list)


@dataclass
class CoverageResult:
    """Code coverage results."""

    total_percentage: float = 0.0
    files_covered: Dict[str, float] = field(default_factory=dict)
    uncovered_lines: Dict[str, List[int]] = field(default_factory=dict)


@dataclass
class CommitResult:
    """Result of the commit workflow."""

    success: bool
    phase_reached: TestPhase
    test_result: Optional[TestResult] = None
    coverage_result: Optional[CoverageResult] = None
    commit_hash: Optional[str] = None
    commit_message: str = ""
    files_committed: List[str] = field(default_factory=list)
    pushed: bool = False
    duration_seconds: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# Test and Commit Workflow
# ═══════════════════════════════════════════════════════════════════════════════


class TestAndCommitWorkflow:
    """
    Automated testing and committing workflow.

    Example:
        workflow = TestAndCommitWorkflow(executor)
        result = await workflow.run(
            message="Add user authentication",
            auto_push=False
        )
    """

    def __init__(
        self,
        executor: ToolExecutor,
        llm_client: Optional[Any] = None,
        confirmation_manager: Optional[ConfirmationManager] = None,
        min_coverage: float = 0.0,  # Minimum coverage percentage required
        fix_failures: bool = False,  # Whether to attempt fixing failures
    ):
        """
        Initialize test workflow.

        Args:
            executor: Tool executor for running tools
            llm_client: LLM for commit message generation
            confirmation_manager: For user confirmations
            min_coverage: Minimum coverage required to commit
            fix_failures: Whether to attempt fixing test failures
        """
        self.executor = executor
        self.llm = llm_client
        self.confirmation = confirmation_manager
        self.min_coverage = min_coverage
        self.fix_failures = fix_failures
        self.risk_assessor = RiskAssessor()

    async def run(
        self,
        message: Optional[str] = None,
        files: Optional[List[str]] = None,
        auto_push: bool = False,
        test_command: Optional[str] = None,
        coverage_command: Optional[str] = None,
    ) -> CommitResult:
        """
        Run the test and commit workflow.

        Args:
            message: Commit message (auto-generated if not provided)
            files: Specific files to commit (all staged if not provided)
            auto_push: Whether to push after commit
            test_command: Custom test command
            coverage_command: Custom coverage command

        Returns:
            CommitResult with outcome
        """
        start_time = datetime.now()
        current_phase = TestPhase.TEST

        logger.info("Starting test and commit workflow...")

        try:
            # Phase 1: Run tests
            logger.info("Phase 1: Running tests...")
            test_result = await self._run_tests(test_command)

            if test_result.failed > 0 or test_result.errors > 0:
                if self.fix_failures:
                    # Phase 2a: Attempt to fix failures
                    current_phase = TestPhase.FIX
                    logger.info("Phase 2: Attempting to fix failures...")
                    fixed = await self._fix_failures(test_result)
                    if fixed:
                        # Re-run tests
                        test_result = await self._run_tests(test_command)

                if test_result.failed > 0 or test_result.errors > 0:
                    return CommitResult(
                        success=False,
                        phase_reached=TestPhase.TEST,
                        test_result=test_result,
                        duration_seconds=(datetime.now() - start_time).total_seconds(),
                    )

            # Phase 2: Check coverage (optional)
            coverage_result = None
            if coverage_command or self.min_coverage > 0:
                current_phase = TestPhase.COVERAGE
                logger.info("Phase 2: Checking coverage...")
                coverage_result = await self._check_coverage(coverage_command)

                if coverage_result.total_percentage < self.min_coverage:
                    logger.warning(
                        f"Coverage {coverage_result.total_percentage}% "
                        f"below minimum {self.min_coverage}%"
                    )
                    return CommitResult(
                        success=False,
                        phase_reached=TestPhase.COVERAGE,
                        test_result=test_result,
                        coverage_result=coverage_result,
                        duration_seconds=(datetime.now() - start_time).total_seconds(),
                    )

            # Phase 3: Stage files
            current_phase = TestPhase.STAGE
            logger.info("Phase 3: Staging files...")
            staged_files = await self._stage_files(files)
            if not staged_files:
                logger.warning("No files to commit")
                return CommitResult(
                    success=False,
                    phase_reached=TestPhase.STAGE,
                    test_result=test_result,
                    coverage_result=coverage_result,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Phase 4: Commit
            current_phase = TestPhase.COMMIT
            logger.info("Phase 4: Committing...")

            # Generate message if not provided
            if not message:
                message = await self._generate_commit_message(staged_files)

            commit_hash = await self._commit(message)
            if not commit_hash:
                return CommitResult(
                    success=False,
                    phase_reached=TestPhase.COMMIT,
                    test_result=test_result,
                    coverage_result=coverage_result,
                    files_committed=staged_files,
                    commit_message=message,
                    duration_seconds=(datetime.now() - start_time).total_seconds(),
                )

            # Phase 5: Push (optional)
            pushed = False
            if auto_push:
                current_phase = TestPhase.PUSH
                logger.info("Phase 5: Pushing to remote...")
                pushed = await self._push()

            duration = (datetime.now() - start_time).total_seconds()

            return CommitResult(
                success=True,
                phase_reached=TestPhase.COMPLETE,
                test_result=test_result,
                coverage_result=coverage_result,
                commit_hash=commit_hash,
                commit_message=message,
                files_committed=staged_files,
                pushed=pushed,
                duration_seconds=duration,
            )

        except Exception as e:
            logger.error(f"Test workflow failed at {current_phase}: {e}")
            return CommitResult(
                success=False,
                phase_reached=current_phase,
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase Implementations
    # ═══════════════════════════════════════════════════════════════════════════

    async def _run_tests(self, command: Optional[str] = None) -> TestResult:
        """Run the test suite."""
        command = command or "python -m pytest -v"

        start = datetime.now()
        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": command},
        )
        duration = (datetime.now() - start).total_seconds()

        output = str(result.result) if result.success else ""

        # Parse pytest output
        test_result = TestResult(
            duration_seconds=duration,
            output=output,
        )

        # Extract counts from pytest output
        # Example: "5 passed, 2 failed, 1 skipped"
        passed_match = re.search(r"(\d+) passed", output)
        failed_match = re.search(r"(\d+) failed", output)
        skipped_match = re.search(r"(\d+) skipped", output)
        error_match = re.search(r"(\d+) error", output)

        if passed_match:
            test_result.passed = int(passed_match.group(1))
        if failed_match:
            test_result.failed = int(failed_match.group(1))
        if skipped_match:
            test_result.skipped = int(skipped_match.group(1))
        if error_match:
            test_result.errors = int(error_match.group(1))

        # Extract failed test names
        failed_tests = re.findall(r"FAILED ([^\s]+)", output)
        test_result.failed_tests = failed_tests

        return test_result

    async def _check_coverage(self, command: Optional[str] = None) -> CoverageResult:
        """Check test coverage."""
        command = command or "python -m pytest --cov --cov-report=term"

        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": command},
        )

        coverage = CoverageResult()

        if result.success:
            output = str(result.result)

            # Extract total coverage
            # Example: "TOTAL    500    50    90%"
            total_match = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
            if total_match:
                coverage.total_percentage = float(total_match.group(1))

            # Extract per-file coverage
            # Example: "src/module.py    100    10    90%"
            file_matches = re.findall(
                r"([^\s]+\.py)\s+\d+\s+\d+\s+(\d+)%", output
            )
            for file_path, pct in file_matches:
                coverage.files_covered[file_path] = float(pct)

        return coverage

    async def _fix_failures(self, test_result: TestResult) -> bool:
        """Attempt to fix test failures."""
        if not self.llm:
            return False

        # This would integrate with the debug workflow
        # For now, just log
        logger.info(f"Would attempt to fix {len(test_result.failed_tests)} failures")
        return False

    async def _stage_files(self, files: Optional[List[str]] = None) -> List[str]:
        """Stage files for commit."""
        if files:
            # Stage specific files
            for file_path in files:
                await self.executor.execute(
                    "terminal.execute_command",
                    {"command": f"git add {file_path}"},
                )
            return files
        else:
            # Stage all changes
            await self.executor.execute(
                "terminal.execute_command",
                {"command": "git add -A"},
            )

            # Get list of staged files
            result = await self.executor.execute(
                "terminal.execute_command",
                {"command": "git diff --staged --name-only"},
            )

            if result.success:
                return str(result.result).strip().split("\n")

            return []

    async def _generate_commit_message(self, files: List[str]) -> str:
        """Generate commit message from changes."""
        if not self.llm:
            # Simple default
            if len(files) == 1:
                return f"Update {files[0]}"
            return f"Update {len(files)} files"

        # Get diff for context
        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": "git diff --staged --stat"},
        )
        diff_stat = str(result.result) if result.success else ""

        prompt = f"""Generate a conventional commit message for these changes:

Files changed:
{chr(10).join(files[:10])}
{f'... and {len(files) - 10} more' if len(files) > 10 else ''}

Diff stats:
{diff_stat[:500]}

Use conventional commit format: type(scope): description
Types: feat, fix, docs, style, refactor, test, chore

Generate only the commit message, no explanation."""

        try:
            if hasattr(self.llm, "generate_async"):
                message = await self.llm.generate_async(prompt)
            else:
                message = self.llm.generate(prompt)

            # Clean up
            message = message.strip().split("\n")[0]  # First line only
            return message[:72]  # Limit length

        except Exception as e:
            logger.warning(f"Commit message generation failed: {e}")
            return f"Update {len(files)} files"

    async def _commit(self, message: str) -> Optional[str]:
        """Create the commit."""
        # Escape message for shell
        safe_message = message.replace('"', '\\"')

        # Request confirmation for commit
        if self.confirmation:
            from agents.confirmation import RiskAssessment

            assessment = RiskAssessment(
                tool="git.commit",
                arguments={"message": message},
                level=RiskLevel.MEDIUM,
                reason="Creating git commit",
                requires_confirmation=True,
                impact_description=f"Will commit with message: {message}",
            )

            confirm_result = await self.confirmation.request_confirmation(assessment)
            if not confirm_result.approved:
                logger.warning("User denied commit")
                return None

        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": f'git commit -m "{safe_message}"'},
        )

        if result.success:
            # Get commit hash
            hash_result = await self.executor.execute(
                "terminal.execute_command",
                {"command": "git rev-parse --short HEAD"},
            )
            if hash_result.success:
                return str(hash_result.result).strip()

        return None

    async def _push(self) -> bool:
        """Push to remote."""
        # Request confirmation for push
        if self.confirmation:
            from agents.confirmation import RiskAssessment

            assessment = RiskAssessment(
                tool="git.push",
                arguments={},
                level=RiskLevel.HIGH,
                reason="Pushing to remote repository",
                requires_confirmation=True,
                impact_description="Will push commits to remote",
            )

            confirm_result = await self.confirmation.request_confirmation(assessment)
            if not confirm_result.approved:
                logger.warning("User denied push")
                return False

        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": "git push"},
        )

        return result.success


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════


def create_test_workflow(
    mcp_registry: Any = None,
    llm_client: Any = None,
    min_coverage: float = 0.0,
) -> TestAndCommitWorkflow:
    """Create a test and commit workflow instance."""
    executor = ToolExecutor(
        mcp_registry=mcp_registry,
        llm_client=llm_client,
    )

    return TestAndCommitWorkflow(
        executor=executor,
        llm_client=llm_client,
        min_coverage=min_coverage,
    )
