"""
Database models for Project Core.
Uses SQLAlchemy 2.0 for ORM.
"""

from datetime import datetime
from typing import Optional, List, Dict, Any
from enum import Enum as PyEnum

from sqlalchemy import (
    Column, Integer, String, Text, Boolean, DateTime, 
    ForeignKey, JSON, Enum, Index, UniqueConstraint
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class PermissionLevel(str, PyEnum):
    """Permission levels for execution."""
    NONE = "none"  # No execution allowed
    REVIEW = "review"  # Requires approval
    AUTO = "auto"  # Automatic execution


class ActionStatus(str, PyEnum):
    """Status of an action."""
    PENDING = "pending"
    PLANNING = "planning"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    ROLLED_BACK = "rolled_back"


class User(Base):
    """User model."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    username: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    
    full_name: Mapped[Optional[str]] = mapped_column(String(255))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Settings
    default_permission_level: Mapped[str] = mapped_column(
        Enum(PermissionLevel),
        default=PermissionLevel.REVIEW,
        nullable=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_login: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    projects: Mapped[List["Project"]] = relationship("Project", back_populates="owner", cascade="all, delete-orphan")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="user", cascade="all, delete-orphan")


class Project(Base):
    """Project model - represents a codebase being worked on."""
    __tablename__ = "projects"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    owner_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    
    # Project location
    workspace_path: Mapped[str] = mapped_column(String(500), nullable=False)
    git_url: Mapped[Optional[str]] = mapped_column(String(500))
    branch: Mapped[str] = mapped_column(String(100), default="main", nullable=False)
    
    # Project metadata
    language: Mapped[Optional[str]] = mapped_column(String(50))  # primary language
    framework: Mapped[Optional[str]] = mapped_column(String(100))
    
    # Settings
    auto_test: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_format: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Status
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    
    # Relationships
    owner: Mapped["User"] = relationship("User", back_populates="projects")
    sessions: Mapped[List["Session"]] = relationship("Session", back_populates="project", cascade="all, delete-orphan")
    actions: Mapped[List["Action"]] = relationship("Action", back_populates="project", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_project_owner_name", "owner_id", "name"),
    )


class Session(Base):
    """Session model - represents a conversation/work session."""
    __tablename__ = "sessions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Session context
    context: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # Status
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    last_activity: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="sessions")
    project: Mapped["Project"] = relationship("Project", back_populates="sessions")
    messages: Mapped[List["Message"]] = relationship("Message", back_populates="session", cascade="all, delete-orphan", order_by="Message.created_at")
    actions: Mapped[List["Action"]] = relationship("Action", back_populates="session", cascade="all, delete-orphan")


class Message(Base):
    """Message model - represents a message in a session."""
    __tablename__ = "messages"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    metadata: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="messages")
    
    __table_args__ = (
        Index("idx_message_session_created", "session_id", "created_at"),
    )


class Action(Base):
    """Action model - represents a Plan → Execute → Verify → Reflect cycle."""
    __tablename__ = "actions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(Integer, ForeignKey("sessions.id", ondelete="CASCADE"), nullable=False)
    project_id: Mapped[int] = mapped_column(Integer, ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    
    # Action details
    intent: Mapped[str] = mapped_column(Text, nullable=False)  # What the user wants
    plan: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # The plan
    execution_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # Execution results
    verification_result: Mapped[Optional[Dict[str, Any]]] = mapped_column(JSON)  # Test results
    reflection: Mapped[Optional[str]] = mapped_column(Text)  # What was learned
    
    # Status
    status: Mapped[str] = mapped_column(
        Enum(ActionStatus),
        default=ActionStatus.PENDING,
        nullable=False,
        index=True
    )
    
    # Approval (for review permission level)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    approved: Mapped[Optional[bool]] = mapped_column(Boolean)
    approved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text)
    error_trace: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Relationships
    session: Mapped["Session"] = relationship("Session", back_populates="actions")
    project: Mapped["Project"] = relationship("Project", back_populates="actions")
    diffs: Mapped[List["Diff"]] = relationship("Diff", back_populates="action", cascade="all, delete-orphan")
    audit_logs: Mapped[List["AuditLog"]] = relationship("AuditLog", back_populates="action", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_action_session_status", "session_id", "status"),
        Index("idx_action_project_status", "project_id", "status"),
    )


class Diff(Base):
    """Diff model - represents a code change."""
    __tablename__ = "diffs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_id: Mapped[int] = mapped_column(Integer, ForeignKey("actions.id", ondelete="CASCADE"), nullable=False)
    
    # File information
    file_path: Mapped[str] = mapped_column(String(500), nullable=False)
    operation: Mapped[str] = mapped_column(String(20), nullable=False)  # create, modify, delete
    
    # Diff content
    original_content: Mapped[Optional[str]] = mapped_column(Text)
    new_content: Mapped[Optional[str]] = mapped_column(Text)
    unified_diff: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Application status
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    rolled_back: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    rolled_back_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Error tracking
    error: Mapped[Optional[str]] = mapped_column(Text)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    
    # Relationships
    action: Mapped["Action"] = relationship("Action", back_populates="diffs")


class AuditLog(Base):
    """Audit log model - comprehensive logging of all actions."""
    __tablename__ = "audit_logs"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    action_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("actions.id", ondelete="SET NULL"))
    
    # Event details
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    event_data: Mapped[Dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    
    # User tracking
    user_id: Mapped[Optional[int]] = mapped_column(Integer)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45))
    user_agent: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Timestamp
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    # Relationships
    action: Mapped[Optional["Action"]] = relationship("Action", back_populates="audit_logs")
    
    __table_args__ = (
        Index("idx_audit_event_created", "event_type", "created_at"),
    )
