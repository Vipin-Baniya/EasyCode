"""
Pytest configuration and shared fixtures.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app


# ── Event loop ────────────────────────────────────────────────────────────────

@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop for async tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ── App test client ───────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def client() -> TestClient:
    """FastAPI test client (no real DB – routes return stubs)."""
    return TestClient(app)


# ── Workspace ─────────────────────────────────────────────────────────────────

@pytest.fixture
def workspace(tmp_path: Path) -> Path:
    """Temporary workspace directory for DiffEngine tests."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    return ws
