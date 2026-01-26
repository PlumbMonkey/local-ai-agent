"""Research and Implement workflow - autonomous feature development.

This workflow handles:
1. Parse user request
2. Research approach (web, docs, codebase)
3. Plan implementation
4. Generate code
5. Apply changes
6. Test and verify
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from agents.executor import ToolExecutor, ExecutionResult
from agents.confirmation import ConfirmationManager, RiskAssessor

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow Types
# ═══════════════════════════════════════════════════════════════════════════════


class ResearchPhase(str, Enum):
    """Phases of the research workflow."""

    PARSE = "parse"
    RESEARCH = "research"
    PLAN = "plan"
    GENERATE = "generate"
    APPLY = "apply"
    TEST = "test"
    COMPLETE = "complete"
    FAILED = "failed"


@dataclass
class FeatureRequest:
    """Parsed feature request."""

    title: str
    description: str
    requirements: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)
    technologies: List[str] = field(default_factory=list)
    target_files: List[str] = field(default_factory=list)


@dataclass
class ResearchResult:
    """Research gathered for implementation."""

    sources: List[Dict[str, str]] = field(default_factory=list)
    code_examples: List[str] = field(default_factory=list)
    documentation: List[str] = field(default_factory=list)
    similar_code: List[Dict[str, str]] = field(default_factory=list)


@dataclass
class ImplementationPlan:
    """Plan for implementing the feature."""

    steps: List[Dict[str, Any]] = field(default_factory=list)
    files_to_create: List[str] = field(default_factory=list)
    files_to_modify: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    estimated_complexity: str = "medium"


@dataclass
class ImplementationResult:
    """Result of the implementation workflow."""

    success: bool
    phase_reached: ResearchPhase
    feature_request: FeatureRequest
    plan: Optional[ImplementationPlan] = None
    files_created: List[str] = field(default_factory=list)
    files_modified: List[str] = field(default_factory=list)
    tests_passed: bool = False
    duration_seconds: float = 0.0
    research_sources: List[str] = field(default_factory=list)


# ═══════════════════════════════════════════════════════════════════════════════
# Research and Implement Workflow
# ═══════════════════════════════════════════════════════════════════════════════


class ResearchAndImplementWorkflow:
    """
    Autonomous feature implementation workflow with research.

    Example:
        workflow = ResearchAndImplementWorkflow(executor, llm)
        result = await workflow.run("Add pagination to the user list API")
    """

    def __init__(
        self,
        executor: ToolExecutor,
        llm_client: Optional[Any] = None,
        confirmation_manager: Optional[ConfirmationManager] = None,
        max_research_sources: int = 5,
    ):
        """
        Initialize research workflow.

        Args:
            executor: Tool executor for running tools
            llm_client: LLM for analysis and code generation
            confirmation_manager: For user confirmations
            max_research_sources: Maximum sources to research
        """
        self.executor = executor
        self.llm = llm_client
        self.confirmation = confirmation_manager
        self.max_research_sources = max_research_sources
        self.risk_assessor = RiskAssessor()

    async def run(
        self,
        request: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> ImplementationResult:
        """
        Run the research and implement workflow.

        Args:
            request: Feature request or description
            context: Optional additional context

        Returns:
            ImplementationResult with outcome
        """
        start_time = datetime.now()
        context = context or {}

        logger.info(f"Starting research workflow for: {request[:100]}...")

        current_phase = ResearchPhase.PARSE

        try:
            # Phase 1: Parse request
            logger.info("Phase 1: Parsing request...")
            feature = await self._parse_request(request, context)

            # Phase 2: Research
            current_phase = ResearchPhase.RESEARCH
            logger.info("Phase 2: Researching approach...")
            research = await self._research_approach(feature)

            # Phase 3: Plan
            current_phase = ResearchPhase.PLAN
            logger.info("Phase 3: Planning implementation...")
            plan = await self._create_plan(feature, research)
            if not plan or not plan.steps:
                return self._failed_result(
                    feature, ResearchPhase.PLAN, start_time,
                    research.sources
                )

            # Phase 4: Generate code
            current_phase = ResearchPhase.GENERATE
            logger.info("Phase 4: Generating code...")
            generated = await self._generate_code(feature, plan, research)
            if not generated:
                return self._failed_result(
                    feature, ResearchPhase.GENERATE, start_time,
                    [s.get("url", "") for s in research.sources]
                )

            # Phase 5: Apply changes
            current_phase = ResearchPhase.APPLY
            logger.info("Phase 5: Applying changes...")
            apply_result = await self._apply_changes(generated, plan)
            if not apply_result["success"]:
                return self._failed_result(
                    feature, ResearchPhase.APPLY, start_time,
                    [s.get("url", "") for s in research.sources]
                )

            # Phase 6: Test
            current_phase = ResearchPhase.TEST
            logger.info("Phase 6: Testing...")
            test_passed = await self._run_tests(context.get("test_command"))

            duration = (datetime.now() - start_time).total_seconds()

            return ImplementationResult(
                success=True,
                phase_reached=ResearchPhase.COMPLETE,
                feature_request=feature,
                plan=plan,
                files_created=apply_result.get("created", []),
                files_modified=apply_result.get("modified", []),
                tests_passed=test_passed,
                duration_seconds=duration,
                research_sources=[s.get("url", "") for s in research.sources],
            )

        except Exception as e:
            logger.error(f"Research workflow failed at {current_phase}: {e}")
            return ImplementationResult(
                success=False,
                phase_reached=current_phase,
                feature_request=FeatureRequest(title=request[:50], description=request),
                duration_seconds=(datetime.now() - start_time).total_seconds(),
            )

    # ═══════════════════════════════════════════════════════════════════════════
    # Phase Implementations
    # ═══════════════════════════════════════════════════════════════════════════

    async def _parse_request(
        self, request: str, context: Dict[str, Any]
    ) -> FeatureRequest:
        """Parse the feature request."""
        # Use LLM to parse if available
        if self.llm:
            prompt = f"""Parse this feature request into structured format:

Request: {request}

Context: {context}

Respond with JSON:
{{
    "title": "Short title",
    "description": "Full description",
    "requirements": ["req1", "req2"],
    "constraints": ["constraint1"],
    "technologies": ["python", "fastapi"],
    "target_files": ["path/to/file.py"]
}}"""

            try:
                if hasattr(self.llm, "generate_async"):
                    response = await self.llm.generate_async(prompt)
                else:
                    response = self.llm.generate(prompt)

                import json
                import re

                json_match = re.search(r"\{[\s\S]*\}", response)
                if json_match:
                    data = json.loads(json_match.group())
                    return FeatureRequest(**data)
            except Exception as e:
                logger.warning(f"LLM parsing failed: {e}")

        # Fallback: simple parsing
        return FeatureRequest(
            title=request[:50],
            description=request,
            requirements=[request],
            target_files=context.get("files", []),
        )

    async def _research_approach(self, feature: FeatureRequest) -> ResearchResult:
        """Research implementation approach."""
        research = ResearchResult()

        # Search for similar patterns in codebase
        for tech in feature.technologies[:3]:
            result = await self.executor.execute(
                "filesystem.search_files",
                {"pattern": "**/*.py", "content": tech},
            )
            if result.success and result.result:
                research.similar_code.append({
                    "term": tech,
                    "matches": str(result.result)[:500],
                })

        # Search web for approaches
        search_query = f"{feature.title} {' '.join(feature.technologies[:2])} implementation"
        result = await self.executor.execute(
            "browser.quick_search",
            {"query": search_query, "source": "all", "limit": self.max_research_sources},
        )
        if result.success and result.result:
            results_data = result.result
            if isinstance(results_data, dict) and "results" in results_data:
                for r in results_data["results"]:
                    research.sources.append({
                        "title": r.get("title", ""),
                        "url": r.get("url", ""),
                        "snippet": r.get("snippet", ""),
                    })

        # Fetch documentation if specific library mentioned
        for tech in feature.technologies[:2]:
            result = await self.executor.execute(
                "browser.fetch_documentation",
                {"library": tech},
            )
            if result.success and result.result:
                doc_data = result.result
                if isinstance(doc_data, dict) and "documentation" in doc_data:
                    research.documentation.append(str(doc_data["documentation"])[:2000])

        return research

    async def _create_plan(
        self, feature: FeatureRequest, research: ResearchResult
    ) -> Optional[ImplementationPlan]:
        """Create implementation plan."""
        if not self.llm:
            # Basic plan without LLM
            return ImplementationPlan(
                steps=[{"action": "implement", "description": feature.description}],
                files_to_create=feature.target_files,
                estimated_complexity="unknown",
            )

        prompt = f"""Create an implementation plan for this feature:

FEATURE:
Title: {feature.title}
Description: {feature.description}
Requirements: {feature.requirements}
Constraints: {feature.constraints}
Technologies: {feature.technologies}

RESEARCH:
Similar code found: {len(research.similar_code)} matches
Documentation: {len(research.documentation)} sources
Web sources: {len(research.sources)} results

Create a step-by-step plan. Respond with JSON:
{{
    "steps": [
        {{"action": "create_file", "path": "...", "description": "..."}},
        {{"action": "modify_file", "path": "...", "description": "..."}}
    ],
    "files_to_create": ["path/new.py"],
    "files_to_modify": ["path/existing.py"],
    "dependencies": ["package1"],
    "estimated_complexity": "low|medium|high"
}}"""

        try:
            if hasattr(self.llm, "generate_async"):
                response = await self.llm.generate_async(prompt)
            else:
                response = self.llm.generate(prompt)

            import json
            import re

            json_match = re.search(r"\{[\s\S]*\}", response)
            if json_match:
                data = json.loads(json_match.group())
                return ImplementationPlan(**data)
        except Exception as e:
            logger.warning(f"Plan creation failed: {e}")

        return None

    async def _generate_code(
        self,
        feature: FeatureRequest,
        plan: ImplementationPlan,
        research: ResearchResult,
    ) -> Optional[Dict[str, Any]]:
        """Generate code for the feature."""
        if not self.llm:
            return None

        generated = {"files": {}}

        # Generate each file in the plan
        for step in plan.steps:
            if step.get("action") in ["create_file", "modify_file"]:
                file_path = step.get("path", "")
                if not file_path:
                    continue

                # Get existing content if modifying
                existing_content = ""
                if step.get("action") == "modify_file":
                    result = await self.executor.execute(
                        "filesystem.read_file",
                        {"path": file_path},
                    )
                    if result.success:
                        existing_content = str(result.result)

                prompt = f"""Generate code for this step:

STEP: {step.get('description', '')}
FILE: {file_path}
ACTION: {step.get('action')}

FEATURE CONTEXT:
{feature.description}

EXISTING CODE:
{existing_content[:3000] if existing_content else 'New file'}

SIMILAR CODE PATTERNS:
{research.similar_code[:2]}

Generate the complete file content. Use best practices.
Only output the code, no explanations."""

                try:
                    if hasattr(self.llm, "generate_async"):
                        code = await self.llm.generate_async(prompt)
                    else:
                        code = self.llm.generate(prompt)

                    # Clean up code (remove markdown code blocks)
                    import re
                    code = re.sub(r"^```\w*\n", "", code)
                    code = re.sub(r"\n```$", "", code)

                    generated["files"][file_path] = code

                except Exception as e:
                    logger.error(f"Code generation failed for {file_path}: {e}")

        return generated if generated["files"] else None

    async def _apply_changes(
        self, generated: Dict[str, Any], plan: ImplementationPlan
    ) -> Dict[str, Any]:
        """Apply generated code changes."""
        created = []
        modified = []

        for file_path, content in generated.get("files", {}).items():
            # Determine if create or modify
            is_new = file_path in plan.files_to_create

            # Check confirmation
            assessment = self.risk_assessor.assess(
                "filesystem.write_file",
                {"path": file_path, "content": content[:100] + "..."},
            )

            if assessment.requires_confirmation and self.confirmation:
                confirm_result = await self.confirmation.request_confirmation(
                    assessment
                )
                if not confirm_result.approved:
                    logger.warning(f"User denied change to {file_path}")
                    continue

            # Apply
            result = await self.executor.execute(
                "filesystem.write_file",
                {"path": file_path, "content": content},
            )

            if result.success:
                if is_new:
                    created.append(file_path)
                else:
                    modified.append(file_path)
            else:
                logger.error(f"Failed to apply {file_path}: {result.error}")

        return {
            "success": len(created) + len(modified) > 0,
            "created": created,
            "modified": modified,
        }

    async def _run_tests(self, test_command: Optional[str] = None) -> bool:
        """Run tests to verify implementation."""
        command = test_command or "python -m pytest -x"

        result = await self.executor.execute(
            "terminal.execute_command",
            {"command": command},
        )

        if result.success:
            output = str(result.result).lower()
            return "passed" in output or ("error" not in output and "failed" not in output)

        return False

    def _failed_result(
        self,
        feature: FeatureRequest,
        phase: ResearchPhase,
        start_time: datetime,
        sources: List[str] = None,
    ) -> ImplementationResult:
        """Create failed result."""
        return ImplementationResult(
            success=False,
            phase_reached=phase,
            feature_request=feature,
            duration_seconds=(datetime.now() - start_time).total_seconds(),
            research_sources=sources or [],
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Factory Functions
# ═══════════════════════════════════════════════════════════════════════════════


def create_research_workflow(
    mcp_registry: Any = None,
    llm_client: Any = None,
) -> ResearchAndImplementWorkflow:
    """Create a research and implement workflow instance."""
    executor = ToolExecutor(
        mcp_registry=mcp_registry,
        llm_client=llm_client,
    )

    return ResearchAndImplementWorkflow(
        executor=executor,
        llm_client=llm_client,
    )
