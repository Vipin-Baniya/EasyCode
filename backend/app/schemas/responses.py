"""Response schemas."""

from __future__ import annotations

from pydantic import BaseModel


class ProjectResponse(BaseModel):
    id: int
    name: str
    slug: str
    description: str | None = None
    workspace_path: str
    language: str | None = None
    framework: str | None = None
    created_at: str


class ActionResponse(BaseModel):
    id: int
    project_id: int
    intent: str
    status: str
    plan: dict | None = None
    execution_result: dict | None = None
    verification_result: dict | None = None
    reflection: str | None = None
    error: str | None = None
    requires_approval: bool = False
    created_at: str
