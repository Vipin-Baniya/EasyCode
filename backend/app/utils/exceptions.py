"""Custom exceptions for Project Core."""

from __future__ import annotations


class ProjectCoreException(Exception):
    """Base exception for Project Core."""
    pass


class LLMError(ProjectCoreException):
    """LLM API errors."""
    pass


class RateLimitError(ProjectCoreException):
    """Rate limit exceeded."""
    pass


class PlanningError(ProjectCoreException):
    """Planning phase errors."""
    pass


class ExecutionError(ProjectCoreException):
    """Execution phase errors."""
    pass


class VerificationError(ProjectCoreException):
    """Verification phase errors."""
    pass


class DiffError(ProjectCoreException):
    """Diff engine errors."""
    pass


class ApprovalRequiredError(ProjectCoreException):
    """Action requires approval before proceeding."""

    def __init__(self, action_id: int, reason: str = "") -> None:
        self.action_id = action_id
        self.reason = reason
        super().__init__(f"Action {action_id} requires approval. {reason}".strip())


class WorkspaceError(ProjectCoreException):
    """Workspace / filesystem errors."""
    pass


class ConfigurationError(ProjectCoreException):
    """Invalid or missing configuration."""
    pass
