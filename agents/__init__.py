"""Agentic workflows and orchestration.

This module provides the autonomous agent infrastructure:
- AgentOrchestrator: LangGraph state machine for multi-step tasks
- ToolExecutor: Smart tool execution with retry logic
- ConfirmationManager: User approval for destructive actions
- Workflows: Pre-built autonomous workflows
- RetryStrategies: Error recovery patterns
"""

from agents.orchestrator import AgentOrchestrator, AgentState
from agents.executor import (
    ToolExecutor,
    BatchExecutor,
    ExecutionResult,
    ExecutionError,
    ErrorCategory,
    ErrorClassifier,
)
from agents.confirmation import (
    ConfirmationManager,
    RiskAssessor,
    RiskLevel,
    RiskAssessment,
    ToolRiskRegistry,
    AutoConfirmationManager,
    create_cli_confirmation_manager,
)
from agents.retry_strategies import (
    RetryStrategy,
    StrategyRegistry,
    StrategyResult,
    FileNotFoundStrategy,
    TimeoutRetryStrategy,
    RateLimitStrategy,
    get_retry_strategy,
    get_recovery_plan,
    retry_with_strategy,
)

# Workflows
from agents.workflows.debug_and_fix import (
    DebugAndFixWorkflow,
    DebugResult,
    ErrorContext,
    create_debug_workflow,
)
from agents.workflows.research_and_implement import (
    ResearchAndImplementWorkflow,
    ImplementationResult,
    FeatureRequest,
    create_research_workflow,
)
from agents.workflows.test_and_commit import (
    TestAndCommitWorkflow,
    CommitResult,
    TestResult,
    create_test_workflow,
)

__all__ = [
    # Core
    "AgentOrchestrator",
    "AgentState",
    "ToolExecutor",
    "BatchExecutor",
    "ExecutionResult",
    "ExecutionError",
    "ErrorCategory",
    "ErrorClassifier",
    # Confirmation
    "ConfirmationManager",
    "RiskAssessor",
    "RiskLevel",
    "RiskAssessment",
    "ToolRiskRegistry",
    "AutoConfirmationManager",
    "create_cli_confirmation_manager",
    # Retry
    "RetryStrategy",
    "StrategyRegistry",
    "StrategyResult",
    "FileNotFoundStrategy",
    "TimeoutRetryStrategy",
    "RateLimitStrategy",
    "get_retry_strategy",
    "get_recovery_plan",
    "retry_with_strategy",
    # Workflows
    "DebugAndFixWorkflow",
    "DebugResult",
    "ErrorContext",
    "create_debug_workflow",
    "ResearchAndImplementWorkflow",
    "ImplementationResult",
    "FeatureRequest",
    "create_research_workflow",
    "TestAndCommitWorkflow",
    "CommitResult",
    "TestResult",
    "create_test_workflow",
]
