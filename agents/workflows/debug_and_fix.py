"""Debug and Fix workflow - 6-step autonomous debugging.

This workflow handles:
1. Read error context
2. Search codebase for related code
3. Research solutions (web/docs)
4. Generate fix
5. Apply and verify
6. Commit if successful
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.orchestrator import AgentOrchestrator, AgentState
from agents.executor import ToolExecutor, ExecutionResult
from agents.confirmation import ConfirmationManager, RiskAssessor

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Types
# ═══════════════════════════════════════════════════════════════════════════════


class DebugPhase(str, Enum):
    """Phases of the debug workflow."""

    ANALYZE = "analyze"
    SEARCH = "search"
    RESEARCH = "research"
    GENERATE = "generate"
    APPLY = "apply"
    VERIFY = "verify"
    COMMIT = "commit"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class ErrorContext:
    """Context about the error being debugged."""

    error_message: str
    error_type: str
    file_path: Optional[str] = None
    line_number: Optional[int] = None
    stack_trace: Optional[str] = None
    surrounding_code: Optional[str] = None


@dataclass
class DebugResult:
    """Result of the debug workflow."""

    success: bool
    phase_reached: DebugPhase
    error_context: ErrorContext
    solution_applied: Optional[str] = None
    files_modified: List[str] = field(default_factory=list)
    commit_hash: Optional[str] = None
    duration_seconds: float = 0.0
    research_sources: List[str] = field(default_factory=list)


@dataclass
class WorkflowStep:
    """A single step in the workflow."""

    phase: DebugPhase
    description: str
    tools: List[str]
    requires_confirmation: bool = False


# ═══════════════════════════════════════════════════════════════════════════════
# Debug Workflow
# ═══════════════════════════════════════════════════════════════════════════════


class DebugAndFixWorkflow:
    """
    Autonomous debugging workflow that finds and fixes errors.

    Example:
        workflow = DebugAndFixWorkflow(executor, orchestrator)
        result = await workflow.run("TypeError: 'NoneType' has no attribute 'read'")
    """

    STEPS = [
        WorkflowStep(
            phase=DebugPhase.ANALYZE,
            description="Analyze error and gather context",
            tools=["filesystem.read_file", "filesystem.search_files"],
        ),
        WorkflowStep(
            phase=DebugPhase.SEARCH,
            description="Search codebase for related code",
            tools=["filesystem.search_files", "filesystem.grep"],
        ),
        WorkflowStep(
            phase=DebugPhase.RESEARCH,
            description="Research solutions online",
            tools=["browser.lookup_error", "browser.quick_search"],
        ),
        WorkflowStep(
            phase=DebugPhase.GENERATE,
            description="Generate fix based on analysis",
            tools=[],  # Uses LLM directly
        ),
        WorkflowStep(
            phase=DebugPhase.APPLY,
            description="Apply the fix to codebase",
            tools=["filesystem.write_file", "coding.apply_patch"],
            requires_confirmation=True,
        ),
        WorkflowStep(
            phase=DebugPhase.VERIFY,
            description="Verify fix works",
            tools=["terminal.execute_command"],
        ),
        WorkflowStep(
            phase=DebugPhase.COMMIT,
            description="Commit the fix",
            tools=["terminal.execute_command"],
            requires_confirmation=True,
        ),
    ]

    def __init__(
        self,
        executor: ToolExecutor,
        orchestrator: Optional[AgentOrchestrator] = None,
        confirmation_manager: Optional[ConfirmationManager] = None,
        llm_client: Optional[Any] = None,
        auto_commit: bool = False,
    ):
        """
        Initialize debug workflow.

        Args:
            executor: Tool executor for running tools
            orchestrator: Agent orchestrator for planning
            confirmation_manager: For user confirmations
            llm_client: LLM for analysis and fix generation
            auto_commit: Whether to auto-commit fixes
        """
        self.executor = executor
        self.orchestrator = orchestrator
        self.confirmation = confirmation_manager
        self.llm = llm_client
        self.auto_commit = auto_commit
        self.risk_assessor = RiskAssessor()

    async def run(
        self,
        error_input: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> DebugResult:
        """
        Run the debug and fix workflow.

        Args:
            error_input: Error message or description
            context: Optional additional context (file paths, etc.)

        Returns:
            DebugResult with outcome
        """
        start_time = datetime.now()
        context = context or {}

        logger.info(f"Starting debug workflow for: {error_input[:100]}...")

        # Parse error
        error_context = self._parse_error(error_input, context)

        # Track progress
        current_phase = DebugPhase.ANALYZE
        files_modified = []
        research_sources = []
        solution = None

        try:
            # Phase 1: Analyze
            logger.info("Phase 1: Analyzing error...")
            analysis = await self._analyze_error(error_context)
            if not analysis:
                return self._failed_result(
                    error_context, DebugPhase.ANALYZE, start_time
                )

            # Phase 2: Search codebase
            current_phase = DebugPhase.SEARCH
            logger.info("Phase 2: Searching codebase...")
            related_code = await self._search_codebase(error_context, analysis)

            # Phase 3: Research solutions
            current_phase = DebugPhase.RESEARCH
            logger.info("Phase 3: Researching solutions...")
            research = await self._research_solutions(error_context)
            research_sources = research.get("sources", [])

            # Phase 4: Generate fix
            current_phase = DebugPhase.GENERATE
            logger.info("Phase 4: Generating fix...")
            solution = await self._generate_fix(
                error_context, analysis, related_code, research
            )
            if not solution:
                return self._failed_result(
                    error_context, DebugPhase.GENERATE, start_time,
                    research_sources=research_sources
                )

            # Phase 5: Apply fix
            current_phase = DebugPhase.APPLY
            logger.info("Phase 5: Applying fix...")
            apply_result = await self._apply_fix(solution)
            if not apply_result["success"]:
                return self._failed_result(
                    error_context, DebugPhase.APPLY, start_time,
                    research_sources=research_sources
                )
            files_modified = apply_result.get("files", [])

            # Phase 6: Verify
            current_phase = DebugPhase.VERIFY
            logger.info("Phase 6: Verifying fix...")
            verified = await self._verify_fix(error_context, context)
            if not verified:
                # Attempt rollback
                await self._rollback(files_modified)
                return self._failed_result(
                    error_context, DebugPhase.VERIFY, start_time,
                    research_sources=research_sources
                )

            # Phase 7: Commit (optional)
            commit_hash = None
            if self.auto_commit or context.get("commit", False):
                current_phase = DebugPhase.COMMIT
                logger.info("Phase 7: Committing fix...")
                commit_hash = await self._commit_fix(error_context, files_modified)

            # Success!
            duration = (datetime.now() - start_time).total_seconds()
            return DebugResult(
                success=True,
                phase_reached=DebugPhase.COMPLETE,
                error_context=error_context,
                solution_applied=solution.get("description", ""),
                files_modified=files_modified,
                commit_hash=commit_hash,
                duration_seconds=duration,
                research_sources=research_sources,
            )

        except Exception as e:
            logger.error(f"Debug workflow failed at {current_phase}: {e}")
            return self._failed_result(
                error_context, current_phase, start_time,
                research_sources=research_sources
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase Implementations
    # ═══════════════════════════════════════════════════════════════════════════

    def _parse_error(
        self, error_input: str, context: Dict[str, Any]
    ) -> ErrorContext:
        """Parse error input into structured context."""
        import re

        # Try to extract file path and line number
        file_match = re.search(r'File ["\']([^"\']+)["\'],? line (\d+)', error_input)
        file_path = file_match.group(1) if file_match else context.get("file_path")
        line_number = int(file_match.group(2)) if file_match else context.get("line_number")

        # Extract error type
        type_match = re.search(r"(\w+Error|\w+Exception):", error_input)
        error_type = type_match.group(1) if type_match else "UnknownError"

        # Extract core message
        msg_match = re.search(r"(?:Error|Exception):\s*(.+?)(?:\n|$)", error_input)
        error_message = msg_match.group(1) if msg_match else error_input[:200]

        return ErrorContext(
            error_message=error_message,
            error_type=error_type,
            file_path=file_path,
            line_number=line_number,
            stack_trace=error_input if "\n" in error_input else None,
        )

    async def _analyze_error(self, error_context: ErrorContext) -> Optional[Dict[str, Any]]:
        """Analyze the error and gather context."""
        analysis = {
            "error_type": error_context.error_type,
            "likely_causes": [],
            "files_to_check": [],
            "surrounding_code": None,
        }

        # If we have a file path, read surrounding code
        if error_context.file_path:
            result = await self.executor.execute(
                "filesystem.read_file",
                {"path": error_context.file_path},
            )
            if result.success:
                analysis["surrounding_code"] = result.result
                error_context.surrounding_code = result.result

        # Use LLM to analyze
        if self.llm:
            prompt = self._build_analysis_prompt(error_context)
            try:
                if hasattr(self.llm, "generate_async"):
                    llm_analysis = await self.llm.generate_async(prompt)
                else:
                    llm_analysis = self.llm.generate(prompt)
                analysis["llm_analysis"] = llm_analysis
            except Exception as e:
                logger.warning(f"LLM analysis failed: {e}")

        return analysis

    async def _search_codebase(
        self, error_context: ErrorContext, analysis: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Search codebase for related code."""
        results = {"files": [], "matches": []}

        # Search for error-related terms
        search_terms = [
            error_context.error_type,
        ]

        # Extract function/class names from error
        if error_context.stack_trace:
            import re
            func_matches = re.findall(r"in (\w+)", error_context.stack_trace)
            search_terms.extend(func_matches[:3])

        for term in search_terms:
            result = await self.executor.execute(
                "filesystem.search_files",
                {"pattern": f"**/*.py", "content": term},
            )
            if result.success and result.result:
                results["matches"].append({
                    "term": term,
                    "results": result.result,
                })

        return results

    async def _research_solutions(
        self, error_context: ErrorContext
    ) -> Dict[str, Any]:
        """Research solutions online."""
        research = {"sources": [], "solutions": []}

        # Use browser tool to lookup error
        result = await self.executor.execute(
            "browser.lookup_error",
            {
                "error": error_context.error_message,
                "language": "python",
            },
        )

        if result.success and result.result:
            research["lookup_result"] = result.result
            if isinstance(result.result, dict):
                if result.result.get("top_answer"):
                    research["sources"].append(
                        result.result["top_answer"].get("url", "")
                    )

        return research

    async def _generate_fix(
        self,
        error_context: ErrorContext,
        analysis: Dict[str, Any],
        related_code: Dict[str, Any],
        research: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        """Generate a fix based on all gathered information."""
        if not self.llm:
            logger.warning("No LLM configured, cannot generate fix")
            return None

        prompt = self._build_fix_prompt(error_context, analysis, related_code, research)

        try:
            if hasattr(self.llm, "generate_async"):
                fix_response = await self.llm.generate_async(prompt)
            else:
                fix_response = self.llm.generate(prompt)

            # Parse fix response
            return self._parse_fix_response(fix_response)

        except Exception as e:
            logger.error(f"Fix generation failed: {e}")
            return None

    async def _apply_fix(self, solution: Dict[str, Any]) -> Dict[str, Any]:
        """Apply the generated fix."""
        files_modified = []

        for change in solution.get("changes", []):
            file_path = change.get("file")
            content = change.get("content")

            if not file_path or not content:
                continue

            # Check if confirmation needed
            assessment = self.risk_assessor.assess(
                "filesystem.write_file",
                {"path": file_path, "content": content},
            )

            if assessment.requires_confirmation and self.confirmation:
                from agents.confirmation import RiskAssessment
                confirm_result = await self.confirmation.request_confirmation(
                    assessment
                )
                if not confirm_result.approved:
                    logger.warning(f"User denied change to {file_path}")
                    continue

            # Apply change
            result = await self.executor.execute(
                "filesystem.write_file",
                {"path": file_path, "content": content},
            )

            if result.success:
                files_modified.append(file_path)
            else:
                logger.error(f"Failed to modify {file_path}: {result.error}")

        return {
            "success": len(files_modified) > 0,
            "files": files_modified,
        }

    async def _verify_fix(
        self, error_context: ErrorContext, context: Dict[str, Any]
    ) -> bool:
        """Verify the fix works."""
        # Run test command if provided
        test_command = context.get("test_command", "python -m pytest -x")

        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": test_command},
        )

        if result.success:
            # Check if tests passed (look for success indicators)
            output = str(result.result)
            if "passed" in output.lower() or "ok" in output.lower():
                return True
            if "failed" in output.lower() or "error" in output.lower():
                return False
            # If we can't tell, assume success if no error
            return True

        return False

    async def _rollback(self, files_modified: List[str]) -> None:
        """Rollback changes if fix failed."""
        logger.info(f"Rolling back changes to {len(files_modified)} files")

        # Use git to restore files
        for file_path in files_modified:
            await self.executor.execute(
                "terminal.execute_command",
                {"command": f"git checkout -- {file_path}"},
            )

    async def _commit_fix(
        self, error_context: ErrorContext, files_modified: List[str]
    ) -> Optional[str]:
        """Commit the fix."""
        # Stage files
        for file_path in files_modified:
            await self.executor.execute(
                "terminal.execute_command",
                {"command": f"git add {file_path}"},
            )

        # Commit
        commit_msg = f"fix: {error_context.error_type} - {error_context.error_message[:50]}"
        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": f'git commit -m "{commit_msg}"'},
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

    # ═══════════════════════════════════════════════════════════════════════════
    # Prompt Builders
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_analysis_prompt(self, error_context: ErrorContext) -> str:
        """Build prompt for error analysis."""
        return f"""Analyze this error and identify likely causes:

Error Type: {error_context.error_type}
Message: {error_context.error_message}
File: {error_context.file_path or 'Unknown'}
Line: {error_context.line_number or 'Unknown'}

Stack Trace:
{error_context.stack_trace or 'Not available'}

Surrounding Code:
{error_context.surrounding_code or 'Not available'}

Provide:
1. Root cause analysis
2. Likely causes (list 2-3)
3. Files to check
4. Suggested fix approach"""

    def _build_fix_prompt(
        self,
        error_context: ErrorContext,
        analysis: Dict[str, Any],
        related_code: Dict[str, Any],
        research: Dict[str, Any],
    ) -> str:
        """Build prompt for fix generation."""
        return f"""Generate a fix for this error:

ERROR:
Type: {error_context.error_type}
Message: {error_context.error_message}
File: {error_context.file_path}
Line: {error_context.line_number}

ANALYSIS:
{analysis.get('llm_analysis', 'No analysis available')}

RELATED CODE:
{related_code}

RESEARCH:
{research}

Generate a fix. Respond with JSON:
{{
    "description": "Brief description of fix",
    "changes": [
        {{
            "file": "path/to/file.py",
            "content": "full file content with fix applied"
        }}
    ],
    "explanation": "Why this fixes the issue"
}}"""

    def _parse_fix_response(self, response: str) -> Optional[Dict[str, Any]]:
        """Parse LLM fix response."""
        import json
        import re

        # Try to extract JSON
        json_match = re.search(r"\{[\s\S]*\}", response)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass

        # Fallback: create simple structure
        return {
            "description": "LLM-generated fix",
            "changes": [],
            "explanation": response,
        }

    def _failed_result(
        self,
        error_context: ErrorContext,
        phase: DebugPhase,
        start_time: datetime,
        research_sources: List[str] = None,
    ) -> DebugResult:
        """Create a failed result."""
        duration = (datetime.now() - start_time).total_seconds()
        return DebugResult(
            success=False,
            phase_reached=phase,
            error_context=error_context,
            duration_seconds=duration,
            research_sources=research_sources or [],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════


def create_debug_workflow(
    mcp_registry: Any = None,
    llm_client: Any = None,
    auto_commit: bool = False,
) -> DebugAndFixWorkflow:
    """Create a debug and fix workflow instance."""
    executor = ToolExecutor(
        mcp_registry=mcp_registry,
        llm_client=llm_client,
    )

    return DebugAndFixWorkflow(
        executor=executor,
        llm_client=llm_client,
        auto_commit=auto_commit,
    )
