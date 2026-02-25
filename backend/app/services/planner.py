"""
Intelligent Planner - Enhanced Production Implementation

AI-powered planning with the latest Anthropic SDK patterns:
- Structured JSON output with strict validation
- Retry logic with exponential back-off
- Token budget awareness
- Session-level memory injection
- Pydantic-based plan validation
"""

from __future__ import annotations

import asyncio
import json
import re
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field, field_validator, model_validator

from app.models.database import Project
from app.services.llm_service import LLMService
from app.utils.code_analyzer import CodeAnalyzer


# ---------------------------------------------------------------------------
# Pydantic schema for strict plan validation
# ---------------------------------------------------------------------------

class PlanStep(BaseModel):
    step_number: int
    title: str
    description: str
    action: str = "modify"
    file_path: str
    code_intent: str = ""
    reason: str = ""
    dependencies: list[str] = Field(default_factory=list)
    risk_level: str = "low"

    @field_validator("action")
    @classmethod
    def validate_action(cls, v: str) -> str:
        allowed = {"create", "modify", "delete"}
        if v not in allowed:
            return "modify"
        return v

    @field_validator("risk_level")
    @classmethod
    def validate_risk(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            return "low"
        return v


class NewDependencies(BaseModel):
    python: list[str] = Field(default_factory=list)
    npm: list[str] = Field(default_factory=list)


class ExecutionPlan(BaseModel):
    summary: str
    understanding: str = ""
    steps: list[PlanStep] = Field(default_factory=list)
    files_to_create: list[str] = Field(default_factory=list)
    files_to_modify: list[str] = Field(default_factory=list)
    files_to_delete: list[str] = Field(default_factory=list)
    new_dependencies: NewDependencies = Field(default_factory=NewDependencies)
    imports_needed: dict[str, list[str]] = Field(default_factory=dict)
    tests_to_create: list[str] = Field(default_factory=list)
    security_considerations: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    estimated_complexity: str = "medium"
    assumptions: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)

    @field_validator("estimated_complexity")
    @classmethod
    def validate_complexity(cls, v: str) -> str:
        if v not in ("low", "medium", "high"):
            return "medium"
        return v

    @model_validator(mode="after")
    def sync_file_lists(self) -> "ExecutionPlan":
        """Ensure steps are numbered sequentially."""
        for i, step in enumerate(self.steps, 1):
            step.step_number = i
        return self


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

PLANNING_SYSTEM_PROMPT = """\
You are a principal-level software engineer and architect.

Your task: Convert user requests into detailed, executable plans.

STRICT RULES:
1. Respond with ONLY valid JSON — no markdown fences, no prose.
2. Use exact file paths relative to the project root (e.g. "backend/app/api/auth.py").
3. Break tasks into atomic, ordered steps.
4. Consider the existing project structure and patterns.
5. List every dependency that must be installed.
6. Propose comprehensive, meaningful tests.
7. Flag security implications explicitly.
8. "action" must be one of: create | modify | delete.
9. "risk_level" must be one of: low | medium | high.

JSON schema (output ONLY this structure):
{
  "summary": "One-line description",
  "understanding": "Analysis of the request and your approach",
  "steps": [
    {
      "step_number": 1,
      "title": "Short step title",
      "description": "Detailed explanation",
      "action": "create|modify|delete",
      "file_path": "relative/path/to/file.ext",
      "code_intent": "What code/changes this step needs",
      "reason": "Why this step is necessary",
      "dependencies": [],
      "risk_level": "low|medium|high"
    }
  ],
  "files_to_create": [],
  "files_to_modify": [],
  "files_to_delete": [],
  "new_dependencies": {"python": [], "npm": []},
  "imports_needed": {"path/to/file.py": ["from x import Y"]},
  "tests_to_create": ["Test description"],
  "security_considerations": ["Hash passwords with bcrypt"],
  "risks": ["Breaking change — requires user re-login"],
  "estimated_complexity": "low|medium|high",
  "assumptions": ["User model exists"],
  "success_criteria": ["Users can log in and receive JWT"]
}
"""

# How many times to retry a failed Claude call
_MAX_RETRIES = 3
_RETRY_DELAY_BASE = 1.5   # seconds


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------

class Planner:
    """
    AI-powered planner that generates structured, validated execution plans.

    Enhancements over v1:
    - Pydantic validation of every generated plan
    - Retry logic with exponential back-off
    - JSON extraction from dirty LLM output
    - Token-budget-aware context trimming
    - Lessons injection from past Reflector output
    """

    def __init__(self, llm_service: LLMService) -> None:
        self.llm = llm_service
        self.analyzer = CodeAnalyzer()

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def create_plan(
        self,
        intent: str,
        project: Project,
        session_context: dict[str, Any] | None = None,
        past_lessons: list[str] | None = None,
    ) -> dict[str, Any]:
        """
        Create an intelligent, validated execution plan.

        Args:
            intent: The user's request.
            project: Target project.
            session_context: Conversation history / recent files.
            past_lessons: Lessons from Reflector to improve planning.

        Returns:
            Validated plan dict ready for CodeExecutor.
        """
        logger.info("🧠 Planning: %.100s", intent)

        try:
            # 1 — Project analysis
            analysis = self.analyzer.analyze_project(project.workspace_path)

            # 2 — Build context
            context = self._build_context(
                intent=intent,
                analysis=analysis,
                session_context=session_context or {},
                past_lessons=past_lessons or [],
            )

            # 3 — Claude call with retries
            raw = await self._call_with_retries(context)

            # 4 — Validate and enrich
            plan = self._validate_plan(raw, project, analysis)

            logger.info(
                "✅ Plan ready — %d steps, %d new files, %d modifications",
                len(plan["steps"]),
                len(plan["files_to_create"]),
                len(plan["files_to_modify"]),
            )
            return plan

        except Exception:
            logger.exception("❌ Planning failed; using fallback")
            return self._fallback_plan(intent, project)

    # -----------------------------------------------------------------------
    # Context builder
    # -----------------------------------------------------------------------

    def _build_context(
        self,
        intent: str,
        analysis: dict[str, Any],
        session_context: dict[str, Any],
        past_lessons: list[str],
    ) -> str:
        """
        Build a rich yet token-efficient context string for Claude.

        We keep each section tightly bounded to avoid hitting token limits.
        """
        parts: list[str] = [
            "# USER REQUEST",
            intent.strip(),
            "",
            "# PROJECT OVERVIEW",
            f"Tech Stack : {analysis.get('tech_stack_summary', 'Unknown')}",
            f"Files      : {analysis.get('total_files', 0)} ({analysis.get('total_lines', 0)} lines)",
            f"Languages  : {', '.join(analysis.get('languages', {}).keys())}",
        ]

        if analysis.get("frameworks"):
            parts += ["", f"Frameworks : {', '.join(analysis['frameworks'])}"]

        if analysis.get("patterns"):
            parts += ["", "Patterns   : " + ", ".join(analysis["patterns"])]

        # Key source files (capped)
        src = analysis.get("source_files", [])[:30]
        if src:
            parts += ["", "Source files:"]
            parts += [f"  {f}" for f in src]

        # Existing models / routes (capped)
        for label, key in (("Models", "models"), ("Routes/API", "routes")):
            items = analysis.get(key, [])[:10]
            if items:
                parts += ["", f"{label}:"]
                parts += [f"  {f}" for f in items]

        # Dependencies
        py = analysis.get("python_dependencies", [])[:20]
        nm = analysis.get("npm_dependencies", [])[:20]
        if py:
            parts += ["", f"Python deps : {', '.join(py)}"]
        if nm:
            parts += ["", f"NPM deps    : {', '.join(nm)}"]

        # Security findings (only highs)
        highs = [
            s for s in analysis.get("security_findings", [])
            if s.get("severity") == "high"
        ][:5]
        if highs:
            parts += ["", "⚠️  Existing HIGH security findings:"]
            for s in highs:
                parts += [f"  [{s['file_path']}:{s['line_number']}] {s['description']}"]

        # Session context
        if session_context:
            parts.append("")
            parts.append("# SESSION CONTEXT")
            if session_context.get("last_action"):
                parts.append(f"Last action     : {session_context['last_action']}")
            if session_context.get("recent_files"):
                parts.append(f"Recently edited : {', '.join(session_context['recent_files'][:6])}")
            if session_context.get("chat_history"):
                parts.append("Recent messages :")
                for msg in session_context["chat_history"][-4:]:
                    role = msg.get("role", "user")
                    text = str(msg.get("content", ""))[:200]
                    parts.append(f"  [{role}] {text}")

        # Past lessons
        if past_lessons:
            parts += ["", "# LESSONS FROM PAST ACTIONS"]
            for lesson in past_lessons[-5:]:
                parts.append(f"  • {lesson}")

        parts += [
            "",
            "# TASK",
            "Create a detailed, step-by-step plan to fulfil the user request.",
            "Use exact paths relative to the project root.",
            "Output ONLY the JSON plan — no markdown, no extra text.",
        ]

        return "\n".join(parts)

    # -----------------------------------------------------------------------
    # Claude interaction
    # -----------------------------------------------------------------------

    async def _call_with_retries(self, context: str) -> dict[str, Any]:
        """Call Claude with retry + exponential back-off."""
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                raw = await self.llm.generate_structured(
                    prompt=context,
                    system_prompt=PLANNING_SYSTEM_PROMPT,
                    temperature=0.2,
                    max_tokens=4096,
                )
                return raw

            except json.JSONDecodeError as exc:
                logger.warning("Attempt %d — JSON parse failed: %s", attempt, exc)
                last_exc = exc

            except Exception as exc:
                logger.warning("Attempt %d — Claude call failed: %s", attempt, exc)
                last_exc = exc

            if attempt < _MAX_RETRIES:
                delay = _RETRY_DELAY_BASE ** attempt
                logger.debug("Retrying in %.1f s …", delay)
                await asyncio.sleep(delay)

        raise RuntimeError(f"All {_MAX_RETRIES} planning attempts failed") from last_exc

    # -----------------------------------------------------------------------
    # Plan validation
    # -----------------------------------------------------------------------

    def _validate_plan(
        self,
        raw: dict[str, Any],
        project: Project,
        analysis: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Validate with Pydantic, then enrich with project metadata.
        """
        try:
            plan_obj = ExecutionPlan.model_validate(raw)
        except Exception as exc:
            logger.warning("Pydantic validation issue — best-effort coercion: %s", exc)
            # Coerce what we can
            plan_obj = ExecutionPlan(
                summary=raw.get("summary", "Execute user request"),
                understanding=raw.get("understanding", ""),
                steps=self._coerce_steps(raw.get("steps", [])),
            )

        plan = plan_obj.model_dump()

        # Sync file lists with steps
        existing = set(analysis.get("source_files", []))
        for step in plan["steps"]:
            fp = step.get("file_path", "")
            if not fp:
                continue
            if fp in existing:
                if fp not in plan["files_to_modify"]:
                    plan["files_to_modify"].append(fp)
            else:
                if fp not in plan["files_to_create"]:
                    plan["files_to_create"].append(fp)

        # Metadata
        plan["project_id"] = project.id
        plan["project_language"] = project.language
        plan["project_framework"] = project.framework
        plan["tech_stack"] = analysis.get("tech_stack_summary", "")
        plan["requires_approval"] = (
            bool(plan["files_to_delete"])
            or plan["estimated_complexity"] == "high"
            or len(plan["risks"]) > 2
            or any("breaking" in r.lower() for r in plan["risks"])
        )

        return plan

    def _coerce_steps(self, raw_steps: list[Any]) -> list[PlanStep]:
        steps: list[PlanStep] = []
        for i, s in enumerate(raw_steps, 1):
            if not isinstance(s, dict):
                continue
            try:
                steps.append(PlanStep(
                    step_number=s.get("step_number", i),
                    title=s.get("title", f"Step {i}"),
                    description=s.get("description", ""),
                    action=s.get("action", "modify"),
                    file_path=s.get("file_path", ""),
                    code_intent=s.get("code_intent", ""),
                    reason=s.get("reason", ""),
                    dependencies=s.get("dependencies", []),
                    risk_level=s.get("risk_level", "low"),
                ))
            except Exception:
                pass
        return steps

    # -----------------------------------------------------------------------
    # Fallback
    # -----------------------------------------------------------------------

    def _fallback_plan(self, intent: str, project: Project) -> dict[str, Any]:
        logger.warning("⚠️  Using fallback plan")
        return {
            "summary": f"Fallback plan: {intent[:60]}",
            "understanding": "AI planning unavailable; fallback used.",
            "steps": [{
                "step_number": 1,
                "title": "Create stub file",
                "description": "Minimal stub for the user request",
                "action": "create",
                "file_path": "implementation_stub.py",
                "code_intent": intent,
                "reason": "Fallback",
                "dependencies": [],
                "risk_level": "low",
            }],
            "files_to_create": ["implementation_stub.py"],
            "files_to_modify": [],
            "files_to_delete": [],
            "new_dependencies": {"python": [], "npm": []},
            "imports_needed": {},
            "tests_to_create": [],
            "security_considerations": [],
            "risks": ["Fallback plan — limited functionality"],
            "estimated_complexity": "low",
            "assumptions": ["Claude API unavailable"],
            "success_criteria": ["Stub file created"],
            "requires_approval": True,
            "project_id": project.id,
            "project_language": project.language,
            "project_framework": project.framework,
            "tech_stack": "",
            "is_fallback": True,
        }
