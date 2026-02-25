"""
Reflector - Enhanced Learning System

Analyses execution results, stores lessons persistently (JSON-backed),
and surfaces actionable improvement suggestions for future planning.

Improvements over v1:
- Pydantic ReflectionResult for type safety
- JSON-file-backed lesson store (survives restarts)
- Lesson deduplication via fuzzy-key hashing
- Categorised lessons: quality / security / performance / architecture
- generate_improvement_suggestions uses semantic category matching
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from loguru import logger
from pydantic import BaseModel, Field

from app.models.database import Action
from app.services.llm_service import LLMService


# ---------------------------------------------------------------------------
# Pydantic schema for the reflection output
# ---------------------------------------------------------------------------

class ReflectionResult(BaseModel):
    summary: str
    success_factors: list[str] = Field(default_factory=list)
    failure_factors: list[str] = Field(default_factory=list)
    lessons_learned: list[str] = Field(default_factory=list)
    suggestions: list[str] = Field(default_factory=list)
    patterns_detected: list[str] = Field(default_factory=list)
    risk_assessment: str = ""
    complexity_assessment: str = ""
    # Enhanced fields
    category_tags: list[str] = Field(default_factory=list)   # quality | security | perf | arch
    severity: str = "info"    # info | warning | critical


# ---------------------------------------------------------------------------
# Lesson store entry
# ---------------------------------------------------------------------------

@dataclass
class LessonEntry:
    lesson: str
    category: str
    project_id: int
    timestamp: str
    action_id: int
    hash_key: str = ""

    def __post_init__(self) -> None:
        if not self.hash_key:
            self.hash_key = hashlib.md5(
                self.lesson.lower().strip().encode()
            ).hexdigest()[:12]


# ---------------------------------------------------------------------------
# System prompt
# ---------------------------------------------------------------------------

REFLECTION_SYSTEM_PROMPT = """\
You are a principal engineer mentoring a junior AI coding assistant.
Analyse the execution results and return ONLY a JSON object.

Focus areas:
1. Quality: code correctness, error handling, test coverage
2. Security: secrets, injection risks, auth issues
3. Performance: N+1 queries, missing indexes, blocking I/O
4. Architecture: coupling, patterns, missing abstractions

JSON schema (output ONLY this):
{
  "summary": "1–2 sentence analysis",
  "success_factors": ["..."],
  "failure_factors": ["..."],
  "lessons_learned": ["Specific, actionable lesson"],
  "suggestions": ["Concrete next improvement"],
  "patterns_detected": ["e.g. missing error handling pattern"],
  "risk_assessment": "Were risks correctly predicted?",
  "complexity_assessment": "Was estimate accurate?",
  "category_tags": ["quality", "security", "performance", "architecture"],
  "severity": "info|warning|critical"
}
"""

_LESSON_STORE_DIR = Path(".project_core_data")
_MAX_LESSONS_PER_PROJECT = 100
_MAX_PATTERNS_PER_PROJECT = 30


# ---------------------------------------------------------------------------
# Reflector
# ---------------------------------------------------------------------------

class Reflector:
    """
    Learning system that analyses every action and persistently stores
    lessons to improve future planning cycles.

    Lesson store is backed by a JSON file per project in
    `.project_core_data/lessons_{project_id}.json`.
    """

    def __init__(self, llm_service: LLMService, data_dir: str | Path | None = None) -> None:
        self.llm = llm_service
        self._data_dir = Path(data_dir) if data_dir else _LESSON_STORE_DIR
        self._data_dir.mkdir(parents=True, exist_ok=True)
        # In-memory cache: project_id -> store dict
        self._cache: dict[int, dict[str, Any]] = {}

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def reflect_on_action(
        self,
        action: Action,
        plan: dict[str, Any],
        execution: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Generate and store a reflection for a completed action.

        Returns the reflection dict for downstream consumers.
        """
        logger.info("📚 Reflecting on action %s", action.id)

        try:
            context = self._build_context(action, plan, execution, verification)
            raw = await self.llm.generate_structured(
                prompt=context,
                system_prompt=REFLECTION_SYSTEM_PROMPT,
                temperature=0.35,
                max_tokens=2000,
            )
            reflection = self._parse_reflection(raw)

        except Exception as exc:
            logger.warning("Claude reflection failed (%s); using heuristic fallback", exc)
            reflection = self._heuristic_reflection(plan, execution, verification)

        # Store lessons
        self._persist_lessons(action, reflection)

        # Update action record
        try:
            action.reflection = reflection.get("summary", "")
        except Exception:
            pass

        logger.info(
            "✅ Reflection stored — %d lessons, severity: %s",
            len(reflection.get("lessons_learned", [])),
            reflection.get("severity", "info"),
        )
        return reflection

    def get_lessons_for_project(self, project_id: int) -> dict[str, Any]:
        """Return full lesson store for a project."""
        return self._load_store(project_id)

    def generate_improvement_suggestions(
        self,
        project_id: int,
        current_plan: dict[str, Any],
        max_suggestions: int = 6,
    ) -> list[str]:
        """
        Generate targeted suggestions based on past lessons and the
        current plan's risk profile.
        """
        store = self._load_store(project_id)
        suggestions: list[str] = []

        # 1 — Failure-rate based advice
        s = store.get("successes", 0)
        f = store.get("failures", 0)
        if f > s and (s + f) >= 3:
            suggestions.append(
                "High recent failure rate — break this task into smaller, independently testable steps."
            )

        # 2 — Category-pattern matching against current plan intent
        intent_lower = str(current_plan.get("summary", "")).lower()
        lessons: list[dict[str, Any]] = store.get("lessons", [])

        for lesson in reversed(lessons):     # most recent first
            cat = lesson.get("category", "")
            text = lesson.get("lesson", "")

            if cat == "security" and any(
                kw in intent_lower for kw in ("auth", "login", "password", "token", "user")
            ):
                suggestions.append(f"[Security] {text}")

            elif cat == "quality" and any(
                kw in intent_lower for kw in ("test", "fix", "refactor")
            ):
                suggestions.append(f"[Quality] {text}")

            elif cat == "performance" and any(
                kw in intent_lower for kw in ("query", "list", "all", "load")
            ):
                suggestions.append(f"[Performance] {text}")

            elif cat == "architecture" and any(
                kw in intent_lower for kw in ("add", "create", "new", "feature")
            ):
                suggestions.append(f"[Architecture] {text}")

            if len(suggestions) >= max_suggestions:
                break

        # 3 — Risk-level based advice
        risks = current_plan.get("risks", [])
        if any("breaking" in r.lower() for r in risks):
            suggestions.insert(0, "Breaking change detected — ensure backwards-compatible migration path.")

        # 4 — Generic patterns
        patterns: list[str] = store.get("patterns", [])
        for p in patterns[-5:]:
            if len(suggestions) < max_suggestions:
                suggestions.append(f"Recurring pattern: {p}")

        return suggestions[:max_suggestions]

    # -----------------------------------------------------------------------
    # Context builder
    # -----------------------------------------------------------------------

    def _build_context(
        self,
        action: Action,
        plan: dict[str, Any],
        execution: dict[str, Any],
        verification: dict[str, Any],
    ) -> str:
        parts: list[str] = [
            "# ACTION",
            f"Intent    : {action.intent}",
            f"Complexity: {plan.get('estimated_complexity', 'unknown')}",
            f"Steps     : {len(plan.get('steps', []))}",
            f"New files : {len(plan.get('files_to_create', []))}",
            f"Modified  : {len(plan.get('files_to_modify', []))}",
        ]

        risks = plan.get("risks", [])
        if risks:
            parts += ["", "Predicted risks:"]
            parts += [f"  • {r}" for r in risks[:5]]

        parts += [
            "",
            "# EXECUTION",
            f"Success      : {execution.get('success', False)}",
            f"Files created: {len(execution.get('files_created', []))}",
            f"Files modified: {len(execution.get('files_modified', []))}",
        ]
        if execution.get("errors"):
            parts += ["Execution errors:"]
            for e in execution["errors"][:3]:
                parts += [f"  • {e}"]

        parts += [
            "",
            "# VERIFICATION",
            f"Passed       : {verification.get('passed', False)}",
            f"Tests run    : {verification.get('tests_run', 0)}",
            f"Tests passed : {verification.get('tests_passed', 0)}",
            f"Tests failed : {verification.get('tests_failed', 0)}",
            f"Syntax valid : {verification.get('syntax_valid', True)}",
            f"Lint valid   : {verification.get('lint_valid', True)}",
        ]
        cov = verification.get("coverage_percent")
        if cov is not None:
            parts.append(f"Coverage     : {cov}%")
        if verification.get("errors"):
            parts += ["Verification errors:"]
            for e in verification["errors"][:3]:
                parts += [f"  • {e}"]

        parts += ["", "Provide a concise, actionable reflection. Output ONLY the JSON."]
        return "\n".join(parts)

    # -----------------------------------------------------------------------
    # Reflection parsing
    # -----------------------------------------------------------------------

    def _parse_reflection(self, raw: dict[str, Any]) -> dict[str, Any]:
        try:
            obj = ReflectionResult.model_validate(raw)
            return obj.model_dump()
        except Exception as exc:
            logger.debug("Pydantic reflection parse issue: %s", exc)
            # Best-effort normalisation
            raw.setdefault("summary", "Reflection generated")
            raw.setdefault("lessons_learned", [])
            raw.setdefault("success_factors", [])
            raw.setdefault("failure_factors", [])
            raw.setdefault("suggestions", [])
            raw.setdefault("patterns_detected", [])
            raw.setdefault("category_tags", [])
            raw.setdefault("severity", "info")
            return raw

    # -----------------------------------------------------------------------
    # Heuristic fallback
    # -----------------------------------------------------------------------

    def _heuristic_reflection(
        self,
        plan: dict[str, Any],
        execution: dict[str, Any],
        verification: dict[str, Any],
    ) -> dict[str, Any]:
        exec_ok = execution.get("success", False)
        verify_ok = verification.get("passed", False)
        success = exec_ok and verify_ok

        lessons: list[str] = []
        success_factors: list[str] = []
        failure_factors: list[str] = []
        severity = "info"

        if exec_ok:
            success_factors.append("Code generation completed without exceptions")
        else:
            failure_factors.append("Code generation encountered errors")
            lessons.append("Review error handling in generated code templates")
            severity = "warning"

        if verify_ok:
            success_factors.append("All tests passed")
        else:
            failure_factors.append("Verification failed")
            if not verification.get("syntax_valid", True):
                lessons.append("Syntax errors detected — add syntax pre-check before applying diffs")
                severity = "critical"
            if verification.get("tests_failed", 0) > 0:
                lessons.append("Test failures — improve test scaffolding in plan")
                severity = "warning"

        if not verification.get("lint_valid", True):
            lessons.append("Lint errors present — adopt ruff auto-fix in workflow")

        return {
            "summary": "Heuristic reflection (Claude unavailable)",
            "success_factors": success_factors,
            "failure_factors": failure_factors,
            "lessons_learned": lessons,
            "suggestions": [],
            "patterns_detected": [],
            "risk_assessment": "N/A",
            "complexity_assessment": "N/A",
            "category_tags": ["quality"],
            "severity": severity,
        }

    # -----------------------------------------------------------------------
    # Persistent lesson store
    # -----------------------------------------------------------------------

    def _store_path(self, project_id: int) -> Path:
        return self._data_dir / f"lessons_{project_id}.json"

    def _load_store(self, project_id: int) -> dict[str, Any]:
        if project_id in self._cache:
            return self._cache[project_id]

        path = self._store_path(project_id)
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                self._cache[project_id] = data
                return data
            except Exception as exc:
                logger.warning("Could not load lesson store for project %d: %s", project_id, exc)

        empty: dict[str, Any] = {
            "lessons": [],
            "patterns": [],
            "successes": 0,
            "failures": 0,
        }
        self._cache[project_id] = empty
        return empty

    def _save_store(self, project_id: int, store: dict[str, Any]) -> None:
        path = self._store_path(project_id)
        try:
            path.write_text(json.dumps(store, indent=2, ensure_ascii=False), encoding="utf-8")
            self._cache[project_id] = store
        except Exception as exc:
            logger.warning("Could not save lesson store: %s", exc)

    def _persist_lessons(self, action: Action, reflection: dict[str, Any]) -> None:
        project_id = action.project_id
        store = self._load_store(project_id)

        lessons_added = 0
        existing_hashes = {e["hash_key"] for e in store["lessons"] if "hash_key" in e}

        # Categorise each lesson
        tags: list[str] = reflection.get("category_tags", ["quality"])
        category = tags[0] if tags else "quality"

        for lesson_text in reflection.get("lessons_learned", []):
            if not lesson_text.strip():
                continue
            entry = LessonEntry(
                lesson=lesson_text.strip(),
                category=category,
                project_id=project_id,
                timestamp=datetime.now(timezone.utc).isoformat(),
                action_id=action.id,
            )
            if entry.hash_key not in existing_hashes:
                store["lessons"].append(asdict(entry))
                existing_hashes.add(entry.hash_key)
                lessons_added += 1

        # Update patterns (deduplicated)
        new_patterns = reflection.get("patterns_detected", [])
        store["patterns"] = list(
            dict.fromkeys(store["patterns"] + new_patterns)
        )[-_MAX_PATTERNS_PER_PROJECT:]

        # Track success/failure
        overall_ok = (
            len(reflection.get("failure_factors", [])) == 0
            and reflection.get("severity", "info") != "critical"
        )
        if overall_ok:
            store["successes"] += 1
        else:
            store["failures"] += 1

        # Cap total lessons
        store["lessons"] = store["lessons"][-_MAX_LESSONS_PER_PROJECT:]

        self._save_store(project_id, store)
        logger.debug("Persisted %d new lessons for project %d", lessons_added, project_id)
