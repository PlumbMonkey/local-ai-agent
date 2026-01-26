"""Unit tests for agent confirmation module."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock

from agents.confirmation import (
    ConfirmationManager,
    RiskAssessor,
    RiskLevel,
    RiskAssessment,
    ToolRiskRegistry,
    AutoConfirmationManager,
    ConfirmationRequest,
    ConfirmationResult,
)


# ═══════════════════════════════════════════════════════════════════════════════
# RiskLevel Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRiskLevel:
    """Tests for RiskLevel enum."""

    def test_risk_level_values(self):
        """Should have correct string values."""
        assert RiskLevel.SAFE.value == "safe"
        assert RiskLevel.LOW.value == "low"
        assert RiskLevel.MEDIUM.value == "medium"
        assert RiskLevel.HIGH.value == "high"
        assert RiskLevel.CRITICAL.value == "critical"


# ═══════════════════════════════════════════════════════════════════════════════
# ToolRiskRegistry Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestToolRiskRegistry:
    """Tests for ToolRiskRegistry."""

    def test_get_risk_known_safe_tool(self):
        """Should return SAFE for read operations."""
        risk = ToolRiskRegistry.get_risk("filesystem.read_file")
        assert risk == RiskLevel.SAFE

    def test_get_risk_known_high_tool(self):
        """Should return HIGH for delete operations."""
        risk = ToolRiskRegistry.get_risk("filesystem.delete_file")
        assert risk == RiskLevel.HIGH

    def test_get_risk_unknown_tool(self):
        """Should return MEDIUM for unknown tools."""
        risk = ToolRiskRegistry.get_risk("unknown.mystery_tool")
        assert risk == RiskLevel.MEDIUM

    def test_get_risk_terminal_with_dangerous_command(self):
        """Should elevate risk for dangerous terminal commands."""
        risk = ToolRiskRegistry.get_risk(
            "terminal.execute_command",
            {"command": "rm -rf /important"}
        )
        assert risk == RiskLevel.HIGH

    def test_get_risk_terminal_safe_command(self):
        """Should not elevate risk for safe commands."""
        risk = ToolRiskRegistry.get_risk(
            "terminal.execute_command",
            {"command": "echo hello"}
        )
        assert risk == RiskLevel.MEDIUM

    def test_get_risk_sudo_elevates(self):
        """Should elevate risk for sudo commands."""
        risk = ToolRiskRegistry.get_risk(
            "terminal.execute_command",
            {"command": "sudo apt update"}
        )
        assert risk == RiskLevel.HIGH


# ═══════════════════════════════════════════════════════════════════════════════
# RiskAssessor Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestRiskAssessor:
    """Tests for RiskAssessor."""

    @pytest.fixture
    def assessor(self):
        """Create assessor with default settings."""
        return RiskAssessor(confirmation_threshold=RiskLevel.MEDIUM)

    def test_assess_safe_tool(self, assessor):
        """Should not require confirmation for safe tools."""
        assessment = assessor.assess("filesystem.read_file", {"path": "test.txt"})
        assert assessment.level == RiskLevel.SAFE
        assert assessment.requires_confirmation is False

    def test_assess_high_risk_tool(self, assessor):
        """Should require confirmation for high risk tools."""
        assessment = assessor.assess("filesystem.delete_file", {"path": "data.db"})
        assert assessment.level == RiskLevel.HIGH
        assert assessment.requires_confirmation is True

    def test_assess_medium_at_threshold(self, assessor):
        """Should require confirmation at threshold."""
        assessment = assessor.assess("filesystem.write_file", {"path": "out.txt"})
        assert assessment.level == RiskLevel.MEDIUM
        assert assessment.requires_confirmation is True

    def test_trust_tool(self, assessor):
        """Should skip confirmation for trusted tools."""
        assessor.trust_tool("filesystem.write_file")
        assessment = assessor.assess("filesystem.write_file", {"path": "out.txt"})
        assert assessment.requires_confirmation is False

    def test_untrust_tool(self, assessor):
        """Should require confirmation after untrusting."""
        assessor.trust_tool("filesystem.write_file")
        assessor.untrust_tool("filesystem.write_file")
        assessment = assessor.assess("filesystem.write_file", {"path": "out.txt"})
        assert assessment.requires_confirmation is True

    def test_trust_rules(self):
        """Should honor trust rules."""
        rules = [
            {"tool_prefix": "filesystem.read"},
            {"tool": "filesystem.write_file", "arguments": {"path": "allowed.txt"}},
        ]
        assessor = RiskAssessor(
            confirmation_threshold=RiskLevel.LOW,
            trust_rules=rules,
        )

        # Should match prefix rule
        assessment = assessor.assess("filesystem.read_file", {})
        assert assessment.requires_confirmation is False

        # Should match exact rule with args
        assessment = assessor.assess(
            "filesystem.write_file",
            {"path": "allowed.txt"}
        )
        assert assessment.requires_confirmation is False

        # Should not match
        assessment = assessor.assess(
            "filesystem.write_file",
            {"path": "other.txt"}
        )
        assert assessment.requires_confirmation is True

    def test_affected_resources(self, assessor):
        """Should extract affected resources."""
        assessment = assessor.assess(
            "filesystem.copy_file",
            {"source": "a.txt", "destination": "b.txt"}
        )
        assert "a.txt" in assessment.affected_resources
        assert "b.txt" in assessment.affected_resources

    def test_impact_description_delete(self, assessor):
        """Should describe delete impact."""
        assessment = assessor.assess(
            "filesystem.delete_file",
            {"path": "important.db"}
        )
        assert "delete" in assessment.impact_description.lower()
        assert "important.db" in assessment.impact_description


# ═══════════════════════════════════════════════════════════════════════════════
# ConfirmationManager Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestConfirmationManager:
    """Tests for ConfirmationManager."""

    @pytest.fixture
    def assessment(self):
        """Create test assessment."""
        return RiskAssessment(
            tool="filesystem.delete_file",
            arguments={"path": "test.txt"},
            level=RiskLevel.HIGH,
            reason="Test",
            requires_confirmation=True,
            impact_description="Will delete test.txt",
        )

    @pytest.mark.asyncio
    async def test_request_with_sync_prompt(self, assessment):
        """Should use sync prompt function."""
        mock_prompt = MagicMock(return_value="yes")
        manager = ConfirmationManager(prompt_fn=mock_prompt)

        result = await manager.request_confirmation(assessment)

        assert result.approved is True
        mock_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_with_async_prompt(self, assessment):
        """Should use async prompt function."""
        mock_prompt = AsyncMock(return_value="yes")
        manager = ConfirmationManager(async_prompt_fn=mock_prompt)

        result = await manager.request_confirmation(assessment)

        assert result.approved is True
        mock_prompt.assert_called_once()

    @pytest.mark.asyncio
    async def test_request_denied(self, assessment):
        """Should handle denial."""
        manager = ConfirmationManager(prompt_fn=lambda _: "no")
        result = await manager.request_confirmation(assessment)
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_request_trust(self, assessment):
        """Should handle trust response."""
        manager = ConfirmationManager(prompt_fn=lambda _: "trust")
        result = await manager.request_confirmation(assessment)
        assert result.approved is True
        assert result.trust_future is True

    @pytest.mark.asyncio
    async def test_request_timeout_deny(self, assessment):
        """Should deny on timeout by default."""
        async def slow_prompt(_):
            await asyncio.sleep(10)
            return "yes"

        manager = ConfirmationManager(
            async_prompt_fn=slow_prompt,
            default_timeout=0.1,
            auto_deny_on_timeout=True,
        )

        result = await manager.request_confirmation(assessment, timeout=0.1)

        assert result.approved is False
        assert "timeout" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_request_timeout_approve(self, assessment):
        """Should approve on timeout when configured."""
        async def slow_prompt(_):
            await asyncio.sleep(10)
            return "no"

        manager = ConfirmationManager(
            async_prompt_fn=slow_prompt,
            default_timeout=0.1,
            auto_deny_on_timeout=False,
        )

        result = await manager.request_confirmation(assessment, timeout=0.1)

        assert result.approved is True
        assert "timeout" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_no_prompt_default_behavior(self, assessment):
        """Should deny high risk without prompt function."""
        manager = ConfirmationManager()
        result = await manager.request_confirmation(assessment)
        assert result.approved is False

    @pytest.mark.asyncio
    async def test_no_prompt_safe_auto_approve(self):
        """Should approve safe actions without prompt."""
        assessment = RiskAssessment(
            tool="filesystem.read_file",
            arguments={},
            level=RiskLevel.SAFE,
            reason="Safe",
            requires_confirmation=False,
        )
        manager = ConfirmationManager()
        result = await manager.request_confirmation(assessment)
        assert result.approved is True

    def test_history_tracking(self):
        """Should track confirmation history."""
        manager = ConfirmationManager()
        assert manager.get_history() == []
        assert manager.get_pending() == []

    @pytest.mark.asyncio
    async def test_history_after_request(self, assessment):
        """Should add to history after request."""
        manager = ConfirmationManager(prompt_fn=lambda _: "y")
        await manager.request_confirmation(assessment)

        history = manager.get_history()
        assert len(history) == 1
        assert history[0].approved is True

    def test_build_prompt(self):
        """Should build readable prompt."""
        manager = ConfirmationManager()
        assessment = RiskAssessment(
            tool="filesystem.delete_file",
            arguments={"path": "/data/important.db"},
            level=RiskLevel.HIGH,
            reason="Destructive",
            requires_confirmation=True,
            impact_description="Will permanently delete file",
            affected_resources=["/data/important.db"],
        )

        prompt = manager._build_prompt(assessment)

        assert "CONFIRMATION REQUIRED" in prompt
        assert "HIGH RISK" in prompt
        assert "delete" in prompt.lower()
        assert "/data/important.db" in prompt

    def test_parse_response_variations(self):
        """Should parse various response formats."""
        manager = ConfirmationManager()

        # Approval variations
        for response in ["y", "yes", "Y", "YES", "ok", "approve"]:
            result = manager._parse_response(response)
            assert result.approved is True

        # Denial variations
        for response in ["n", "no", "N", "NO", "deny"]:
            result = manager._parse_response(response)
            assert result.approved is False

        # Unknown defaults to deny
        result = manager._parse_response("maybe")
        assert result.approved is False


# ═══════════════════════════════════════════════════════════════════════════════
# AutoConfirmationManager Tests
# ═══════════════════════════════════════════════════════════════════════════════


class TestAutoConfirmationManager:
    """Tests for AutoConfirmationManager."""

    @pytest.fixture
    def assessment(self):
        """Create test assessment."""
        return RiskAssessment(
            tool="test.tool",
            arguments={},
            level=RiskLevel.HIGH,
            reason="Test",
            requires_confirmation=True,
        )

    @pytest.mark.asyncio
    async def test_auto_approve(self, assessment):
        """Should auto-approve when configured."""
        manager = AutoConfirmationManager(auto_approve=True)
        result = await manager.request_confirmation(assessment)
        assert result.approved is True
        assert "auto" in result.reason.lower()

    @pytest.mark.asyncio
    async def test_auto_deny(self, assessment):
        """Should auto-deny when configured."""
        manager = AutoConfirmationManager(auto_approve=False)
        result = await manager.request_confirmation(assessment)
        assert result.approved is False
        assert "auto" in result.reason.lower()
