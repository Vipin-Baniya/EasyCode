"""Request schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field, field_validator


class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    slug: str | None = Field(default=None, pattern=r"^[a-z0-9-]+$")
    description: str | None = None
    language: str | None = None
    framework: str | None = None

    @field_validator("slug", mode="before")
    @classmethod
    def normalise_slug(cls, v: str | None) -> str | None:
        if v:
            return v.lower().replace(" ", "-").replace("_", "-")
        return v


class CreateActionRequest(BaseModel):
    intent: str = Field(..., min_length=1, max_length=4000)
    context: dict | None = None
    permission_level: str = Field(default="review", pattern=r"^(none|review|auto)$")
