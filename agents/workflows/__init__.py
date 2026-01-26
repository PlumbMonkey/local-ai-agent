"""Pre-built autonomous agent workflows.

Available workflows:
- DebugAndFixWorkflow: 6-step autonomous debugging
- ResearchAndImplementWorkflow: Research-driven feature implementation
- TestAndCommitWorkflow: Automated testing and git workflow
"""

from agents.workflows.debug_and_fix import (
    DebugAndFixWorkflow,
    DebugResult,
    DebugPhase,
    ErrorContext,
    create_debug_workflow,
)
from agents.workflows.research_and_implement import (
    ResearchAndImplementWorkflow,
    ImplementationResult,
    ResearchPhase,
    FeatureRequest,
    ImplementationPlan,
    create_research_workflow,
)
from agents.workflows.test_and_commit import (
    TestAndCommitWorkflow,
    CommitResult,
    TestPhase,
    TestResult,
    CoverageResult,
    create_test_workflow,
)

__all__ = [
    # Debug workflow
    "DebugAndFixWorkflow",
    "DebugResult",
    "DebugPhase",
    "ErrorContext",
    "create_debug_workflow",
    # Research workflow
    "ResearchAndImplementWorkflow",
    "ImplementationResult",
    "ResearchPhase",
    "FeatureRequest",
    "ImplementationPlan",
    "create_research_workflow",
    # Test workflow
    "TestAndCommitWorkflow",
    "CommitResult",
    "TestPhase",
    "TestResult",
    "CoverageResult",
    "create_test_workflow",
]
