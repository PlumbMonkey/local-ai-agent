"""User confirmation system for destructive actions.

This module provides:
- Risk classification for tool calls
- User approval prompts with timeouts
- Trust rules for skipping confirmation
- Audit logging of confirmations
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Classification
# ═══════════════════════════════════════════════════════════════════════════════


class RiskLevel(str, Enum):
    """Risk levels for tool operations."""

    SAFE = "safe"  # Read-only, no confirmation needed
    LOW = "low"  # Minor changes, optional confirmation
    MEDIUM = "medium"  # Significant changes, confirm by default
    HIGH = "high"  # Destructive/irreversible, always confirm
    CRITICAL = "critical"  # System-level, require explicit confirmation


@dataclass
class RiskAssessment:
    """Assessment of risk for a tool call."""

    tool: str
    arguments: Dict[str, Any]
    level: RiskLevel
    reason: str
    requires_confirmation: bool
    impact_description: str = ""
    affected_resources: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Risk Registry
# ═══════════════════════════════════════════════════════════════════════════════


class ToolRiskRegistry:
    """Registry of known tools and their risk levels."""

    # Default risk levels by tool pattern
    TOOL_RISKS: Dict[str, RiskLevel] = {
        # Safe - read operations
        "filesystem.read_file": RiskLevel.SAFE,
        "filesystem.list_directory": RiskLevel.SAFE,
        "filesystem.search_files": RiskLevel.SAFE,
        "terminal.execute_command": RiskLevel.MEDIUM,  # Could be anything
        "browser.search": RiskLevel.SAFE,
        "browser.fetch_page": RiskLevel.SAFE,
        # Low - minor changes
        "filesystem.create_directory": RiskLevel.LOW,
        # Medium - significant changes
        "filesystem.write_file": RiskLevel.MEDIUM,
        "filesystem.append_file": RiskLevel.MEDIUM,
        "coding.apply_patch": RiskLevel.MEDIUM,
        # High - destructive
        "filesystem.delete_file": RiskLevel.HIGH,
        "filesystem.delete_directory": RiskLevel.HIGH,
        "terminal.execute_sudo": RiskLevel.HIGH,
        "git.commit": RiskLevel.MEDIUM,
        "git.push": RiskLevel.HIGH,
        "git.force_push": RiskLevel.CRITICAL,
        "git.reset_hard": RiskLevel.CRITICAL,
        # Critical - system level
        "system.shutdown": RiskLevel.CRITICAL,
        "system.modify_env": RiskLevel.CRITICAL,
    }

    # Commands that elevate terminal risk
    DANGEROUS_COMMANDS = {
        "rm", "rmdir", "del", "deltree",  # Delete
        "sudo", "runas",  # Privilege escalation
        "chmod", "chown",  # Permissions
        "format", "mkfs",  # Disk
        "dd", "fdisk",  # Low-level disk
        "shutdown", "reboot",  # System
        "kill", "killall", "taskkill",  # Process
        "git push", "git reset",  # Git destructive
    }

    @classmethod
    def get_risk(cls, tool: str, arguments: Dict[str, Any] = None) -> RiskLevel:
        """Get risk level for a tool."""
        arguments = arguments or {}

        # Check direct match
        if tool in cls.TOOL_RISKS:
            base_risk = cls.TOOL_RISKS[tool]
        else:
            # Default to medium for unknown tools
            base_risk = RiskLevel.MEDIUM

        # Elevate risk for terminal commands
        if tool.startswith("terminal."):
            command = str(arguments.get("command", "")).lower()
            for dangerous in cls.DANGEROUS_COMMANDS:
                if dangerous in command:
                    return RiskLevel.HIGH

        # Elevate risk for sudo in any command
        if "sudo" in str(arguments.values()).lower():
            return RiskLevel.HIGH

        return base_risk


# ═══════════════════════════════════════════════════════════════════════════════
# Risk Assessor
# ═══════════════════════════════════════════════════════════════════════════════


class RiskAssessor:
    """Assess risk of tool calls and determine confirmation needs."""

    def __init__(
        self,
        confirmation_threshold: RiskLevel = RiskLevel.MEDIUM,
        trust_rules: Optional[List[Dict[str, Any]]] = None,
    ):
        """
        Initialize risk assessor.

        Args:
            confirmation_threshold: Minimum risk level requiring confirmation
            trust_rules: Optional list of rules to skip confirmation
        """
        self.confirmation_threshold = confirmation_threshold
        self.trust_rules = trust_rules or []
        self._trusted_tools: Set[str] = set()

    def assess(self, tool: str, arguments: Dict[str, Any]) -> RiskAssessment:
        """
        Assess risk of a tool call.

        Args:
            tool: Tool name
            arguments: Tool arguments

        Returns:
            RiskAssessment with risk level and confirmation requirement
        """
        level = ToolRiskRegistry.get_risk(tool, arguments)

        # Check if trusted
        if self._is_trusted(tool, arguments):
            return RiskAssessment(
                tool=tool,
                arguments=arguments,
                level=level,
                reason="Trusted by rule",
                requires_confirmation=False,
            )

        # Determine if confirmation needed
        requires_confirmation = self._level_to_int(level) >= self._level_to_int(
            self.confirmation_threshold
        )

        # Build impact description
        impact = self._describe_impact(tool, arguments, level)

        return RiskAssessment(
            tool=tool,
            arguments=arguments,
            level=level,
            reason=f"Tool '{tool}' has {level.value} risk level",
            requires_confirmation=requires_confirmation,
            impact_description=impact,
            affected_resources=self._get_affected_resources(tool, arguments),
        )

    def trust_tool(self, tool: str):
        """Add tool to trusted set (skip confirmation)."""
        self._trusted_tools.add(tool)
        logger.info(f"Added '{tool}' to trusted tools")

    def untrust_tool(self, tool: str):
        """Remove tool from trusted set."""
        self._trusted_tools.discard(tool)

    def _is_trusted(self, tool: str, arguments: Dict[str, Any]) -> bool:
        """Check if tool/args combination is trusted."""
        if tool in self._trusted_tools:
            return True

        for rule in self.trust_rules:
            if self._matches_rule(rule, tool, arguments):
                return True

        return False

    def _matches_rule(
        self, rule: Dict[str, Any], tool: str, arguments: Dict[str, Any]
    ) -> bool:
        """Check if a trust rule matches."""
        if "tool" in rule and rule["tool"] != tool:
            return False
        if "tool_prefix" in rule and not tool.startswith(rule["tool_prefix"]):
            return False
        if "arguments" in rule:
            for key, value in rule["arguments"].items():
                if key not in arguments or arguments[key] != value:
                    return False
        return True

    def _level_to_int(self, level: RiskLevel) -> int:
        """Convert risk level to integer for comparison."""
        return {
            RiskLevel.SAFE: 0,
            RiskLevel.LOW: 1,
            RiskLevel.MEDIUM: 2,
            RiskLevel.HIGH: 3,
            RiskLevel.CRITICAL: 4,
        }[level]

    def _describe_impact(
        self, tool: str, arguments: Dict[str, Any], level: RiskLevel
    ) -> str:
        """Generate human-readable impact description."""
        if level == RiskLevel.SAFE:
            return "Read-only operation, no changes will be made"

        if "delete" in tool.lower():
            target = arguments.get("path", arguments.get("file", "resource"))
            return f"Will permanently delete: {target}"

        if "write" in tool.lower() or "create" in tool.lower():
            target = arguments.get("path", arguments.get("file", "file"))
            return f"Will create/modify: {target}"

        if tool.startswith("terminal."):
            command = arguments.get("command", "unknown command")
            return f"Will execute: {command}"

        if "git" in tool.lower():
            return f"Git operation: {tool.split('.')[-1]}"

        return f"Will perform {tool} operation"

    def _get_affected_resources(
        self, tool: str, arguments: Dict[str, Any]
    ) -> List[str]:
        """Get list of resources affected by this tool call."""
        resources = []

        # Check for file paths
        for key in ["path", "file", "directory", "source", "destination"]:
            if key in arguments:
                resources.append(str(arguments[key]))

        # Check for command
        if "command" in arguments:
            resources.append(f"command: {arguments['command']}")

        return resources


# ═══════════════════════════════════════════════════════════════════════════════
# Confirmation Manager
# ═══════════════════════════════════════════════════════════════════════════════


@dataclass
class ConfirmationRequest:
    """A pending confirmation request."""

    id: str
    assessment: RiskAssessment
    timestamp: str
    timeout_seconds: float
    prompt: str
    approved: Optional[bool] = None
    responded_at: Optional[str] = None


@dataclass
class ConfirmationResult:
    """Result of a confirmation request."""

    approved: bool
    reason: str
    trust_future: bool = False  # Trust this tool in future


class ConfirmationManager:
    """
    Manage user confirmations for destructive actions.

    Example:
        manager = ConfirmationManager(prompt_fn=cli_prompt)
        result = await manager.request_confirmation(assessment)
        if result.approved:
            # Proceed with action
    """

    def __init__(
        self,
        prompt_fn: Optional[Callable[[str], str]] = None,
        async_prompt_fn: Optional[Callable[[str], Any]] = None,
        default_timeout: float = 60.0,
        auto_deny_on_timeout: bool = True,
    ):
        """
        Initialize confirmation manager.

        Args:
            prompt_fn: Sync function to prompt user (receives message, returns response)
            async_prompt_fn: Async function to prompt user
            default_timeout: Default timeout for responses
            auto_deny_on_timeout: Whether to deny on timeout
        """
        self.prompt_fn = prompt_fn
        self.async_prompt_fn = async_prompt_fn
        self.default_timeout = default_timeout
        self.auto_deny_on_timeout = auto_deny_on_timeout
        self._history: List[ConfirmationRequest] = []
        self._pending: Dict[str, ConfirmationRequest] = {}
        self._request_counter = 0

    async def request_confirmation(
        self,
        assessment: RiskAssessment,
        timeout: Optional[float] = None,
    ) -> ConfirmationResult:
        """
        Request user confirmation for a risky action.

        Args:
            assessment: Risk assessment for the action
            timeout: Optional timeout override

        Returns:
            ConfirmationResult with approval status
        """
        timeout = timeout or self.default_timeout

        # Build confirmation prompt
        prompt = self._build_prompt(assessment)

        # Create request
        self._request_counter += 1
        request_id = f"confirm_{self._request_counter}"
        request = ConfirmationRequest(
            id=request_id,
            assessment=assessment,
            timestamp=datetime.now().isoformat(),
            timeout_seconds=timeout,
            prompt=prompt,
        )
        self._pending[request_id] = request

        logger.info(f"Requesting confirmation for {assessment.tool}")

        try:
            # Get user response
            if self.async_prompt_fn:
                response = await asyncio.wait_for(
                    self.async_prompt_fn(prompt),
                    timeout=timeout,
                )
            elif self.prompt_fn:
                response = await asyncio.wait_for(
                    asyncio.get_event_loop().run_in_executor(
                        None, self.prompt_fn, prompt
                    ),
                    timeout=timeout,
                )
            else:
                # No prompt function, auto-approve safe, deny risky
                if assessment.level in [RiskLevel.SAFE, RiskLevel.LOW]:
                    response = "y"
                else:
                    logger.warning("No prompt function configured, denying by default")
                    response = "n"

            result = self._parse_response(response)

        except asyncio.TimeoutError:
            logger.warning(f"Confirmation timeout after {timeout}s")
            result = ConfirmationResult(
                approved=not self.auto_deny_on_timeout,
                reason="Timeout - " + (
                    "auto-denied" if self.auto_deny_on_timeout else "auto-approved"
                ),
            )

        # Update request
        request.approved = result.approved
        request.responded_at = datetime.now().isoformat()
        self._history.append(request)
        del self._pending[request_id]

        return result

    def _build_prompt(self, assessment: RiskAssessment) -> str:
        """Build user-facing confirmation prompt."""
        risk_emoji = {
            RiskLevel.SAFE: "✅",
            RiskLevel.LOW: "🟡",
            RiskLevel.MEDIUM: "🟠",
            RiskLevel.HIGH: "🔴",
            RiskLevel.CRITICAL: "⛔",
        }

        emoji = risk_emoji.get(assessment.level, "❓")

        lines = [
            f"\n{emoji} CONFIRMATION REQUIRED - {assessment.level.value.upper()} RISK",
            "=" * 50,
            f"Action: {assessment.tool}",
            f"Impact: {assessment.impact_description}",
        ]

        if assessment.affected_resources:
            lines.append("Affected resources:")
            for resource in assessment.affected_resources:
                lines.append(f"  - {resource}")

        # Show arguments for high risk
        if assessment.level in [RiskLevel.HIGH, RiskLevel.CRITICAL]:
            lines.append("\nFull arguments:")
            lines.append(json.dumps(assessment.arguments, indent=2))

        lines.extend([
            "",
            "Options:",
            "  [y/yes]     - Approve this action",
            "  [n/no]      - Deny this action",
            "  [t/trust]   - Approve and trust this tool for session",
            "  [a/abort]   - Abort entire workflow",
            "",
            "Response: ",
        ])

        return "\n".join(lines)

    def _parse_response(self, response: str) -> ConfirmationResult:
        """Parse user response to confirmation."""
        response = response.strip().lower()

        if response in ["y", "yes", "ok", "approve"]:
            return ConfirmationResult(approved=True, reason="User approved")

        if response in ["t", "trust"]:
            return ConfirmationResult(
                approved=True,
                reason="User approved and trusted",
                trust_future=True,
            )

        if response in ["n", "no", "deny"]:
            return ConfirmationResult(approved=False, reason="User denied")

        if response in ["a", "abort"]:
            return ConfirmationResult(
                approved=False,
                reason="User aborted workflow",
            )

        # Unknown response, default to deny for safety
        return ConfirmationResult(
            approved=False,
            reason=f"Unknown response '{response}', denied for safety",
        )

    def get_history(self) -> List[ConfirmationRequest]:
        """Get history of all confirmation requests."""
        return self._history.copy()

    def get_pending(self) -> List[ConfirmationRequest]:
        """Get list of pending confirmation requests."""
        return list(self._pending.values())


# ═══════════════════════════════════════════════════════════════════════════════
# CLI Integration
# ═══════════════════════════════════════════════════════════════════════════════


def cli_prompt(message: str) -> str:
    """Simple CLI prompt function."""
    print(message, end="", flush=True)
    return input()


def create_cli_confirmation_manager() -> ConfirmationManager:
    """Create a confirmation manager with CLI prompts."""
    return ConfirmationManager(
        prompt_fn=cli_prompt,
        default_timeout=120.0,
        auto_deny_on_timeout=True,
    )


# ═══════════════════════════════════════════════════════════════════════════════
# Auto-Confirmation for Testing
# ═══════════════════════════════════════════════════════════════════════════════


class AutoConfirmationManager(ConfirmationManager):
    """Confirmation manager that auto-approves for testing."""

    def __init__(
        self,
        auto_approve: bool = True,
        log_requests: bool = True,
    ):
        super().__init__()
        self.auto_approve = auto_approve
        self.log_requests = log_requests

    async def request_confirmation(
        self,
        assessment: RiskAssessment,
        timeout: Optional[float] = None,
    ) -> ConfirmationResult:
        """Auto-approve/deny without prompting."""
        if self.log_requests:
            logger.info(
                f"Auto-{'approving' if self.auto_approve else 'denying'}: "
                f"{assessment.tool} ({assessment.level.value})"
            )

        return ConfirmationResult(
            approved=self.auto_approve,
            reason="Auto-" + ("approved" if self.auto_approve else "denied"),
        )
