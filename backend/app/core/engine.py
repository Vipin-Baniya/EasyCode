"""
Core Engine – Plan → Execute → Verify → Reflect orchestrator.

The PEVR loop is the heart of Project Core. Every user intent travels
through all four phases before being considered complete.
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any

from loguru import logger

from app.models.database import Action, ActionStatus, Session, Project
from app.services.llm_service import LLMService
from app.services.planner import Planner
from app.services.executor import CodeExecutor
from app.services.verifier import Verifier
from app.services.reflector import Reflector
from app.services.diff_engine import DiffEngine
from app.utils.exceptions import (
    ApprovalRequiredError,
    ExecutionError,
    PlanningError,
    VerificationError,
)


class EnginePhase(str, Enum):
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    REFLECTING = "reflecting"


class CoreEngine:
    """
    Orchestrates the Plan → Execute → Verify → Reflect loop.

    Guarantees:
    - No code is written without a plan
    - No plan is executed without validation
    - Failed verifications trigger automatic rollback
    - Every cycle produces a reflection for learning
    """

    def __init__(self, llm_service: LLMService, diff_engine: DiffEngine) -> None:
        self.llm = llm_service
        self.diff_engine = diff_engine

        # Initialise the four PEVR components
        self.planner = Planner(llm_service)
        self.executor = CodeExecutor(diff_engine, llm_service)
        self.verifier = Verifier()
        self.reflector = Reflector(llm_service)

    # -----------------------------------------------------------------------
    # Main entry point
    # -----------------------------------------------------------------------

    async def process_intent(
        self,
        action: Action,
        session: Session,
        project: Project,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Run a user intent through the complete PEVR loop.

        Returns a result dict with keys:
            action_id, phases_completed, success,
            plan, execution, verification, reflection, error
        """
        logger.info("🔄 PEVR loop starting — action_id={}", action.id)

        result: dict[str, Any] = {
            "action_id": action.id,
            "phases_completed": [],
            "success": False,
            "requires_approval": False,
        }

        try:
            # ── PHASE 1: PLAN ──────────────────────────────────────────────
            plan = await self._plan(action, session, project, context)
            result["plan"] = plan
            result["phases_completed"].append(EnginePhase.PLANNING)

            # Approval gate
            if action.requires_approval and not action.approved:
                result["requires_approval"] = True
                action.status = ActionStatus.PENDING
                logger.info("⏸  Action {} requires approval", action.id)
                return result

            # ── PHASE 2: EXECUTE ──────────────────────────────────────────
            execution = await self._execute(action, project, plan)
            result["execution"] = execution
            result["phases_completed"].append(EnginePhase.EXECUTING)

            # ── PHASE 3: VERIFY ───────────────────────────────────────────
            verification = await self._verify(action, project, execution)
            result["verification"] = verification
            result["phases_completed"].append(EnginePhase.VERIFYING)

            # ── PHASE 4: REFLECT ──────────────────────────────────────────
            reflection = await self._reflect(action, result)
            result["reflection"] = reflection
            result["phases_completed"].append(EnginePhase.REFLECTING)

            action.status = ActionStatus.COMPLETED
            action.completed_at = datetime.now(timezone.utc)
            result["success"] = True
            logger.info("✅ PEVR loop complete — action_id={}", action.id)

        except ApprovalRequiredError:
            raise

        except VerificationError as exc:
            logger.error("❌ Verification failed — action_id={}: {}", action.id, exc)
            await self._rollback(action, project)
            action.status = ActionStatus.ROLLED_BACK
            action.error = str(exc)
            result["error"] = str(exc)

        except (PlanningError, ExecutionError) as exc:
            logger.error("❌ {} — action_id={}: {}", type(exc).__name__, action.id, exc)
            action.status = ActionStatus.FAILED
            action.error = str(exc)
            result["error"] = str(exc)

        except Exception as exc:
            logger.exception("💥 Unexpected error in PEVR loop — action_id={}", action.id)
            action.status = ActionStatus.FAILED
            action.error = str(exc)
            result["error"] = str(exc)

        return result

    # -----------------------------------------------------------------------
    # Phase helpers
    # -----------------------------------------------------------------------

    async def _plan(
        self,
        action: Action,
        session: Session,
        project: Project,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:
        logger.info("📋 Planning — action_id={}", action.id)
        action.status = ActionStatus.PLANNING
        action.started_at = datetime.now(timezone.utc)

        # Pull past lessons from reflector to improve planning
        lessons_data = self.reflector.get_lessons_for_project(project.id)
        past_lessons: list[str] = [
            e["lesson"] for e in lessons_data.get("lessons", [])[-10:]
        ]

        try:
            plan = await self.planner.create_plan(
                intent=action.intent,
                project=project,
                session_context=context or {},
                past_lessons=past_lessons,
            )
            action.plan = plan
            if plan.get("requires_approval"):
                action.requires_approval = True
            logger.info("📋 Plan ready: {}", plan.get("summary", "N/A"))
            return plan
        except Exception as exc:
            raise PlanningError(f"Planning failed: {exc}") from exc

    async def _execute(
        self,
        action: Action,
        project: Project,
        plan: dict[str, Any],
    ) -> dict[str, Any]:
        logger.info("⚡ Executing — action_id={}", action.id)
        action.status = ActionStatus.EXECUTING

        try:
            result = await self.executor.execute_plan(
                action=action,
                project=project,
                plan=plan,
            )
            action.execution_result = result
            logger.info(
                "⚡ Execution done — {} files created, {} modified",
                len(result.get("files_created", [])),
                len(result.get("files_modified", [])),
            )
            return result
        except Exception as exc:
            raise ExecutionError(f"Execution failed: {exc}") from exc

    async def _verify(
        self,
        action: Action,
        project: Project,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        logger.info("🔬 Verifying — action_id={}", action.id)
        action.status = ActionStatus.VERIFYING

        try:
            result = await self.verifier.verify_execution(
                action=action,
                project=project,
                execution_result=execution,
            )
            action.verification_result = result

            if not result.get("passed", False):
                errors = "; ".join(result.get("errors", ["unknown"]))
                raise VerificationError(f"Tests/lint failed: {errors}")

            logger.info("🔬 Verification passed")
            return result
        except VerificationError:
            raise
        except Exception as exc:
            raise VerificationError(f"Verification error: {exc}") from exc

    async def _reflect(
        self,
        action: Action,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        logger.info("📚 Reflecting — action_id={}", action.id)
        try:
            reflection = await self.reflector.reflect_on_action(
                action=action,
                plan=result.get("plan", {}),
                execution=result.get("execution", {}),
                verification=result.get("verification", {}),
            )
            action.reflection = reflection.get("summary", "")
            logger.info("📚 Reflection stored — severity={}", reflection.get("severity", "info"))
            return reflection
        except Exception as exc:
            logger.warning("Reflection failed (non-fatal): {}", exc)
            return {"summary": "Reflection failed", "error": str(exc)}

    async def _rollback(self, action: Action, project: Project) -> None:
        logger.warning("⏪ Rolling back — action_id={}", action.id)
        try:
            await self.executor.rollback_action(action, project)
            logger.info("⏪ Rollback complete")
        except Exception as exc:
            logger.error("Rollback failed — manual intervention may be needed: {}", exc)

    # -----------------------------------------------------------------------
    # Approval helpers
    # -----------------------------------------------------------------------

    async def approve_action(self, action: Action) -> None:
        action.approved = True
        action.approved_at = datetime.now(timezone.utc)
        logger.info("✅ Action {} approved", action.id)

    async def reject_action(self, action: Action) -> None:
        action.approved = False
        action.status = ActionStatus.CANCELLED
        logger.info("🚫 Action {} rejected", action.id)
