"""
API routes for Project Core.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger

from app.schemas.requests import CreateProjectRequest, CreateActionRequest
from app.schemas.responses import ProjectResponse, ActionResponse
from app.services.llm_service import LLMService, get_llm_service

router = APIRouter()


# ── Dependency helpers ────────────────────────────────────────────────────────

def get_llm() -> LLMService:
    return get_llm_service()


# ── Projects ──────────────────────────────────────────────────────────────────

@router.get("/projects", response_model=list[ProjectResponse], tags=["projects"])
async def list_projects() -> list[ProjectResponse]:
    """List all projects."""
    # TODO: query from database
    return []


@router.post("/projects", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED, tags=["projects"])
async def create_project(request: CreateProjectRequest) -> ProjectResponse:
    """Create a new project."""
    slug = request.slug or request.name.lower().replace(" ", "-")
    # TODO: persist to database and create workspace directory
    return ProjectResponse(
        id=1,
        name=request.name,
        slug=slug,
        description=request.description,
        workspace_path=f"/workspaces/{slug}",
        language=request.language,
        framework=request.framework,
        created_at="2025-01-01T00:00:00Z",
    )


@router.get("/projects/{project_id}", response_model=ProjectResponse, tags=["projects"])
async def get_project(project_id: int) -> ProjectResponse:
    """Get project by ID."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


@router.delete("/projects/{project_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["projects"])
async def delete_project(project_id: int) -> None:
    """Delete a project."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")


# ── Actions ───────────────────────────────────────────────────────────────────

@router.post(
    "/projects/{project_id}/actions",
    response_model=ActionResponse,
    status_code=status.HTTP_202_ACCEPTED,
    tags=["actions"],
)
async def create_action(
    project_id: int,
    request: CreateActionRequest,
    llm: LLMService = Depends(get_llm),
) -> ActionResponse:
    """
    Submit a new intent to run through the PEVR loop.

    Returns 202 Accepted – the loop runs asynchronously.
    Poll GET /actions/{id} for status.
    """
    logger.info("New action — project_id={} intent={!r:.80}", project_id, request.intent)
    # TODO: persist Action to DB, launch background task with CoreEngine
    return ActionResponse(
        id=1,
        project_id=project_id,
        intent=request.intent,
        status="pending",
        created_at="2025-01-01T00:00:00Z",
    )


@router.get("/actions/{action_id}", response_model=ActionResponse, tags=["actions"])
async def get_action(action_id: int) -> ActionResponse:
    """Get action status and results."""
    raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Action not found")


@router.post("/actions/{action_id}/approve", tags=["actions"])
async def approve_action(action_id: int) -> dict[str, Any]:
    """Approve a pending action that requires review."""
    # TODO: load action from DB, call engine.approve_action()
    return {"status": "approved", "action_id": action_id}


@router.post("/actions/{action_id}/reject", tags=["actions"])
async def reject_action(action_id: int) -> dict[str, Any]:
    """Reject a pending action."""
    # TODO: load action from DB, call engine.reject_action()
    return {"status": "rejected", "action_id": action_id}


# ── Meta ──────────────────────────────────────────────────────────────────────

@router.get("/stats", tags=["meta"])
async def get_stats(llm: LLMService = Depends(get_llm)) -> dict[str, Any]:
    """Return LLM usage statistics."""
    return llm.get_stats()
