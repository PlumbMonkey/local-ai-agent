"""LangGraph-based workflow orchestrator for autonomous task execution.

This module provides a state machine for multi-step task execution with:
- Planning: Break tasks into executable steps
- Execution: Call MCP tools with results tracking
- Verification: Validate results and run tests
- Retry: Intelligent error recovery with LLM-guided corrections
- Confirmation: Request user approval for destructive actions
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Literal, Optional, TypedDict, Union

from langgraph.graph import END, StateGraph

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Agent State Schema
# ═══════════════════════════════════════════════════════════════════════════════


class TaskStatus(str, Enum):
    """Status of agent task execution."""

    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    AWAITING_CONFIRMATION = "awaiting_confirmation"
    RETRYING = "retrying"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class Step:
    """A single step in the execution plan."""

    id: int
    tool: str
    description: str
    arguments: Dict[str, Any] = field(default_factory=dict)
    depends_on: List[int] = field(default_factory=list)
    optional: bool = False


@dataclass
class ToolCallRecord:
    """Record of a tool invocation."""

    step_id: int
    tool: str
    arguments: Dict[str, Any]
    result: Optional[Any] = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class ErrorRecord:
    """Record of an error during execution."""

    step_id: int
    error_type: str
    message: str
    traceback: Optional[str] = None
    retry_suggestion: Optional[str] = None


class AgentState(TypedDict, total=False):
    """Complete state for autonomous agent execution.

    This TypedDict defines all state that flows through the LangGraph.
    """

    # Input
    task: str  # Original user request
    context: Dict[str, Any]  # Files, environment, additional context

    # Planning
    plan: List[Dict[str, Any]]  # Generated action steps
    current_step: int  # Execution progress (0-indexed)

    # Execution
    tool_calls: List[Dict[str, Any]]  # MCP tool invocations
    tool_results: List[Dict[str, Any]]  # Results from tools

    # Error handling
    errors: List[Dict[str, Any]]  # Errors encountered
    retry_count: int  # Current retry attempt
    max_retries: int  # Maximum retries (default: 3)
    retry_context: Dict[str, Any]  # Context for retry planning

    # Verification
    tests_passed: Optional[bool]  # If tests were run
    verification_result: Dict[str, Any]  # Validation results
    verification_passed: bool  # Overall verification status

    # Confirmation
    requires_confirmation: bool  # Destructive action pending?
    confirmation_action: str  # Action awaiting approval
    confirmation_details: Dict[str, Any]  # Details for user
    user_approved: Optional[bool]  # User's decision

    # Output
    final_result: str  # Success message or error summary
    status: str  # Current TaskStatus value

    # Metadata
    start_time: str
    end_time: Optional[str]
    total_duration_ms: float


# ═══════════════════════════════════════════════════════════════════════════════
# Base Orchestrator
# ═══════════════════════════════════════════════════════════════════════════════


class AgentOrchestrator:
    """
    LangGraph-based orchestrator for autonomous task execution.

    Provides a state machine with plan → execute → verify → retry loop.

    Example:
        orchestrator = AgentOrchestrator(llm_client, tool_executor)
        result = await orchestrator.run("Fix the timeout bug in api.py")
    """

    def __init__(
        self,
        llm_client: Any,  # OllamaClient or compatible
        tool_executor: Optional["ToolExecutor"] = None,
        confirmation_manager: Optional["ConfirmationManager"] = None,
        max_retries: int = 3,
        default_timeout: float = 30.0,
    ):
        """
        Initialize the orchestrator.

        Args:
            llm_client: LLM client for planning and analysis
            tool_executor: MCP tool executor (creates default if None)
            confirmation_manager: Manager for user confirmations
            max_retries: Maximum retry attempts
            default_timeout: Default timeout for tool calls
        """
        self.llm = llm_client
        self.tool_executor = tool_executor
        self.confirmation_manager = confirmation_manager
        self.max_retries = max_retries
        self.default_timeout = default_timeout

        # Build the graph
        self.graph = self._build_graph()

    def _build_graph(self) -> StateGraph:
        """Build the LangGraph state machine."""
        graph = StateGraph(AgentState)

        # Add nodes
        graph.add_node("plan", self._plan_task)
        graph.add_node("execute", self._execute_step)
        graph.add_node("verify", self._verify_result)
        graph.add_node("retry", self._prepare_retry)
        graph.add_node("confirm", self._request_confirmation)
        graph.add_node("summarize", self._summarize_results)

        # Set entry point
        graph.set_entry_point("plan")

        # Add edges
        graph.add_edge("plan", "execute")

        # After execution, check if confirmation needed
        graph.add_conditional_edges(
            "execute",
            self._route_after_execute,
            {
                "confirm": "confirm",
                "verify": "verify",
                "execute": "execute",  # More steps to execute
            },
        )

        # After confirmation
        graph.add_conditional_edges(
            "confirm",
            self._route_after_confirm,
            {
                "execute": "execute",  # Approved, continue
                "summarize": "summarize",  # Denied, end
            },
        )

        # After verification
        graph.add_conditional_edges(
            "verify",
            self._route_after_verify,
            {
                "retry": "retry",
                "summarize": "summarize",
            },
        )

        # Retry goes back to planning with context
        graph.add_edge("retry", "plan")

        # Summarize ends the workflow
        graph.add_edge("summarize", END)

        return graph.compile()

    # ═══════════════════════════════════════════════════════════════════════════
    # Node Implementations
    # ═══════════════════════════════════════════════════════════════════════════

    async def _plan_task(self, state: AgentState) -> AgentState:
        """Generate execution plan for the task."""
        logger.info(f"Planning task: {state.get('task', '')[:100]}")

        retry_context = state.get("retry_context")

        # Build planning prompt
        if retry_context:
            prompt = self._build_retry_plan_prompt(state)
        else:
            prompt = self._build_initial_plan_prompt(state)

        # Get plan from LLM
        plan_response = await self._call_llm(prompt)
        plan = self._parse_plan(plan_response)

        return {
            **state,
            "plan": plan,
            "current_step": 0,
            "status": TaskStatus.PLANNING.value,
        }

    async def _execute_step(self, state: AgentState) -> AgentState:
        """Execute the current step in the plan."""
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)

        if current_step >= len(plan):
            # No more steps
            return state

        step = plan[current_step]
        logger.info(f"Executing step {current_step + 1}/{len(plan)}: {step.get('tool')}")

        # Execute the tool
        start_time = asyncio.get_event_loop().time()
        try:
            result = await self._execute_tool(
                step.get("tool", ""),
                step.get("arguments", {}),
            )
            duration = (asyncio.get_event_loop().time() - start_time) * 1000

            tool_call = {
                "step_id": current_step,
                "tool": step.get("tool"),
                "arguments": step.get("arguments"),
                "result": result,
                "error": None,
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
            }
        except Exception as e:
            duration = (asyncio.get_event_loop().time() - start_time) * 1000
            logger.error(f"Tool execution failed: {e}")

            tool_call = {
                "step_id": current_step,
                "tool": step.get("tool"),
                "arguments": step.get("arguments"),
                "result": None,
                "error": str(e),
                "duration_ms": duration,
                "timestamp": datetime.now().isoformat(),
            }

            # Record error
            errors = state.get("errors", [])
            errors.append({
                "step_id": current_step,
                "error_type": type(e).__name__,
                "message": str(e),
            })
            state["errors"] = errors

        # Update state
        tool_calls = state.get("tool_calls", [])
        tool_calls.append(tool_call)

        tool_results = state.get("tool_results", [])
        tool_results.append(tool_call.get("result") or tool_call.get("error"))

        return {
            **state,
            "tool_calls": tool_calls,
            "tool_results": tool_results,
            "current_step": current_step + 1,
            "status": TaskStatus.EXECUTING.value,
        }

    async def _verify_result(self, state: AgentState) -> AgentState:
        """Verify the results of execution."""
        logger.info("Verifying results")

        # Build verification prompt
        prompt = self._build_verification_prompt(state)
        verification_response = await self._call_llm(prompt)

        # Parse verification result
        try:
            verification = json.loads(verification_response)
        except json.JSONDecodeError:
            verification = {
                "passed": "success" in verification_response.lower(),
                "message": verification_response,
            }

        return {
            **state,
            "verification_result": verification,
            "verification_passed": verification.get("passed", False),
            "status": TaskStatus.VERIFYING.value,
        }

    async def _prepare_retry(self, state: AgentState) -> AgentState:
        """Prepare for retry with error analysis."""
        logger.info(f"Preparing retry (attempt {state.get('retry_count', 0) + 1})")

        # Analyze what went wrong
        analysis_prompt = self._build_error_analysis_prompt(state)
        analysis = await self._call_llm(analysis_prompt)

        try:
            retry_context = json.loads(analysis)
        except json.JSONDecodeError:
            retry_context = {"analysis": analysis, "suggestions": []}

        return {
            **state,
            "retry_count": state.get("retry_count", 0) + 1,
            "retry_context": retry_context,
            "status": TaskStatus.RETRYING.value,
            # Reset execution state for re-planning
            "plan": [],
            "current_step": 0,
            "tool_calls": [],
            "tool_results": [],
        }

    async def _request_confirmation(self, state: AgentState) -> AgentState:
        """Request user confirmation for destructive action."""
        logger.info(f"Requesting confirmation for: {state.get('confirmation_action')}")

        if self.confirmation_manager:
            result = await self.confirmation_manager.request_confirmation(
                action=state.get("confirmation_action", ""),
                details=state.get("confirmation_details", {}),
            )
            approved = result.approved
        else:
            # No confirmation manager, auto-deny destructive actions
            logger.warning("No confirmation manager, auto-denying")
            approved = False

        return {
            **state,
            "user_approved": approved,
            "status": TaskStatus.AWAITING_CONFIRMATION.value,
        }

    async def _summarize_results(self, state: AgentState) -> AgentState:
        """Generate final summary of execution."""
        logger.info("Generating summary")

        # Build summary prompt
        prompt = self._build_summary_prompt(state)
        summary = await self._call_llm(prompt)

        # Determine final status
        if state.get("verification_passed"):
            final_status = TaskStatus.COMPLETE.value
        elif state.get("retry_count", 0) >= self.max_retries:
            final_status = TaskStatus.FAILED.value
        elif state.get("user_approved") is False:
            final_status = TaskStatus.FAILED.value
        else:
            final_status = TaskStatus.COMPLETE.value

        return {
            **state,
            "final_result": summary,
            "status": final_status,
            "end_time": datetime.now().isoformat(),
        }

    # ═══════════════════════════════════════════════════════════════════════════
    # Routing Functions
    # ═══════════════════════════════════════════════════════════════════════════

    def _route_after_execute(self, state: AgentState) -> str:
        """Route after step execution."""
        plan = state.get("plan", [])
        current_step = state.get("current_step", 0)

        # Check if confirmation needed for current step
        if state.get("requires_confirmation"):
            return "confirm"

        # Check if more steps to execute
        if current_step < len(plan):
            return "execute"

        # All steps done, verify
        return "verify"

    def _route_after_confirm(self, state: AgentState) -> str:
        """Route after confirmation."""
        if state.get("user_approved"):
            # Reset confirmation state and continue
            state["requires_confirmation"] = False
            return "execute"
        else:
            return "summarize"

    def _route_after_verify(self, state: AgentState) -> str:
        """Route after verification."""
        if state.get("verification_passed"):
            return "summarize"

        # Check retry limit
        if state.get("retry_count", 0) >= self.max_retries:
            logger.warning(f"Max retries ({self.max_retries}) reached")
            return "summarize"

        return "retry"

    # ═══════════════════════════════════════════════════════════════════════════
    # Prompt Builders
    # ═══════════════════════════════════════════════════════════════════════════

    def _build_initial_plan_prompt(self, state: AgentState) -> str:
        """Build prompt for initial task planning."""
        return f"""You are an autonomous AI agent. Create an execution plan for this task.

TASK: {state.get('task', '')}

CONTEXT:
{json.dumps(state.get('context', {}), indent=2)}

AVAILABLE TOOLS:
- filesystem.read_file(path) - Read a file
- filesystem.write_file(path, content) - Write to a file
- filesystem.list_directory(path) - List directory contents
- terminal.run_command(command) - Execute a shell command
- memory.search(query, domain) - Search conversation memory
- browser.stackoverflow_search(query) - Search StackOverflow
- browser.scrape_page(url) - Fetch web page content

Create a step-by-step plan. Respond with JSON:
{{
    "steps": [
        {{
            "id": 1,
            "tool": "tool_name",
            "description": "What this step does",
            "arguments": {{"arg": "value"}},
            "optional": false
        }}
    ],
    "reasoning": "Brief explanation of approach"
}}"""

    def _build_retry_plan_prompt(self, state: AgentState) -> str:
        """Build prompt for retry planning with error context."""
        return f"""You are an autonomous AI agent. Your previous attempt failed. Create a new plan.

ORIGINAL TASK: {state.get('task', '')}

PREVIOUS ATTEMPT:
{json.dumps(state.get('retry_context', {}), indent=2)}

ERRORS ENCOUNTERED:
{json.dumps(state.get('errors', []), indent=2)}

Create an improved plan that avoids the previous errors. Respond with JSON:
{{
    "steps": [
        {{
            "id": 1,
            "tool": "tool_name",
            "description": "What this step does",
            "arguments": {{"arg": "value"}},
            "optional": false
        }}
    ],
    "reasoning": "How this plan addresses the previous failure"
}}"""

    def _build_verification_prompt(self, state: AgentState) -> str:
        """Build prompt for result verification."""
        return f"""Verify if this task was completed successfully.

TASK: {state.get('task', '')}

EXECUTION RESULTS:
{json.dumps(state.get('tool_results', []), indent=2)}

ERRORS (if any):
{json.dumps(state.get('errors', []), indent=2)}

Respond with JSON:
{{
    "passed": true/false,
    "message": "Explanation of verification result",
    "issues": ["List of any issues found"]
}}"""

    def _build_error_analysis_prompt(self, state: AgentState) -> str:
        """Build prompt for error analysis before retry."""
        return f"""Analyze why this task execution failed and suggest improvements.

TASK: {state.get('task', '')}

PLAN THAT WAS EXECUTED:
{json.dumps(state.get('plan', []), indent=2)}

TOOL RESULTS:
{json.dumps(state.get('tool_results', []), indent=2)}

ERRORS:
{json.dumps(state.get('errors', []), indent=2)}

This is retry attempt {state.get('retry_count', 0) + 1} of {self.max_retries}.

Respond with JSON:
{{
    "root_cause": "Main reason for failure",
    "suggestions": ["List of improvements to try"],
    "alternative_approach": "Different strategy if available"
}}"""

    def _build_summary_prompt(self, state: AgentState) -> str:
        """Build prompt for final summary."""
        status = "succeeded" if state.get("verification_passed") else "failed"
        return f"""Summarize the results of this task execution.

TASK: {state.get('task', '')}
STATUS: {status}

STEPS EXECUTED:
{json.dumps(state.get('tool_calls', []), indent=2)}

VERIFICATION:
{json.dumps(state.get('verification_result', {}), indent=2)}

Provide a concise summary for the user explaining what was done and the outcome."""

    # ═══════════════════════════════════════════════════════════════════════════
    # Helper Methods
    # ═══════════════════════════════════════════════════════════════════════════

    async def _call_llm(self, prompt: str) -> str:
        """Call the LLM with a prompt."""
        if hasattr(self.llm, "generate_async"):
            return await self.llm.generate_async(prompt)
        elif hasattr(self.llm, "generate"):
            return self.llm.generate(prompt)
        else:
            # Fallback for testing
            return "{}"

    async def _execute_tool(self, tool: str, arguments: Dict[str, Any]) -> Any:
        """Execute an MCP tool."""
        if self.tool_executor:
            return await self.tool_executor.execute(tool, arguments)
        else:
            logger.warning(f"No tool executor, simulating: {tool}")
            return {"simulated": True, "tool": tool, "arguments": arguments}

    def _parse_plan(self, response: str) -> List[Dict[str, Any]]:
        """Parse LLM response into plan steps."""
        try:
            data = json.loads(response)
            return data.get("steps", [])
        except json.JSONDecodeError:
            logger.warning("Failed to parse plan as JSON, using fallback")
            return [{"id": 1, "tool": "unknown", "description": response}]

    # ═══════════════════════════════════════════════════════════════════════════
    # Public API
    # ═══════════════════════════════════════════════════════════════════════════

    async def run(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentState:
        """
        Run the orchestrator on a task.

        Args:
            task: The user's task/request
            context: Additional context (files, environment, etc.)

        Returns:
            Final agent state with results
        """
        initial_state: AgentState = {
            "task": task,
            "context": context or {},
            "plan": [],
            "current_step": 0,
            "tool_calls": [],
            "tool_results": [],
            "errors": [],
            "retry_count": 0,
            "max_retries": self.max_retries,
            "retry_context": {},
            "tests_passed": None,
            "verification_result": {},
            "verification_passed": False,
            "requires_confirmation": False,
            "confirmation_action": "",
            "confirmation_details": {},
            "user_approved": None,
            "final_result": "",
            "status": TaskStatus.PLANNING.value,
            "start_time": datetime.now().isoformat(),
            "end_time": None,
            "total_duration_ms": 0.0,
        }

        # Run the graph
        logger.info(f"Starting orchestrator for task: {task[:100]}")
        final_state = await self.graph.ainvoke(initial_state)

        # Calculate duration
        if final_state.get("start_time") and final_state.get("end_time"):
            start = datetime.fromisoformat(final_state["start_time"])
            end = datetime.fromisoformat(final_state["end_time"])
            final_state["total_duration_ms"] = (end - start).total_seconds() * 1000

        logger.info(f"Orchestrator complete. Status: {final_state.get('status')}")
        return final_state

    def run_sync(
        self,
        task: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> AgentState:
        """Synchronous wrapper for run()."""
        return asyncio.run(self.run(task, context))
