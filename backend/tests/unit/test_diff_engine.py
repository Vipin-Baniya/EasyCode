"""
Unit tests for DiffEngine.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from app.services.diff_engine import DiffEngine, DiffOperation, FileDiff


@pytest.fixture
def tmp_workspace(tmp_path: Path) -> Path:
    return tmp_path


@pytest.fixture
def engine(tmp_workspace: Path) -> DiffEngine:
    return DiffEngine(workspace_root=str(tmp_workspace))


# ── create_diff ───────────────────────────────────────────────────────────────

class TestCreateDiff:
    def test_create_new_file(self, engine: DiffEngine) -> None:
        diff = engine.create_diff("hello.py", "print('hello')", DiffOperation.CREATE)
        assert diff.operation == DiffOperation.CREATE
        assert diff.file_path == "hello.py"
        assert diff.new_content == "print('hello')"
        assert diff.line_changes["additions"] == 1
        assert diff.checksum_after is not None

    def test_modify_existing_file(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        (tmp_workspace / "hello.py").write_text("x = 1\n")
        diff = engine.create_diff("hello.py", "x = 2\n", DiffOperation.MODIFY)
        assert diff.operation == DiffOperation.MODIFY
        assert diff.original_content == "x = 1\n"
        assert diff.unified_diff is not None
        assert diff.line_changes["additions"] >= 1
        assert diff.checksum_before is not None
        assert diff.checksum_after is not None
        assert diff.checksum_before != diff.checksum_after

    def test_create_has_no_unified_diff(self, engine: DiffEngine) -> None:
        diff = engine.create_diff("new.py", "pass\n", DiffOperation.CREATE)
        assert diff.unified_diff is None  # No original to diff against

    def test_modify_nonexistent_file_becomes_create(self, engine: DiffEngine) -> None:
        # File doesn't exist → should silently switch to CREATE
        diff = engine.create_diff("ghost.py", "pass\n", DiffOperation.MODIFY)
        assert diff.operation == DiffOperation.CREATE


# ── validate_diff ─────────────────────────────────────────────────────────────

class TestValidateDiff:
    def test_create_valid(self, engine: DiffEngine) -> None:
        diff = engine.create_diff("brand_new.py", "pass", DiffOperation.CREATE)
        valid, warnings = engine.validate_diff(diff)
        assert valid is True
        assert warnings == []

    def test_create_existing_file_invalid(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        (tmp_workspace / "exists.py").write_text("pass")
        diff = FileDiff(
            operation=DiffOperation.CREATE,
            file_path="exists.py",
            new_content="pass",
        )
        valid, warnings = engine.validate_diff(diff)
        assert valid is False
        assert any("already exists" in w for w in warnings)

    def test_modify_missing_file_invalid(self, engine: DiffEngine) -> None:
        diff = FileDiff(
            operation=DiffOperation.MODIFY,
            file_path="missing.py",
            original_content="x=1",
            new_content="x=2",
        )
        valid, warnings = engine.validate_diff(diff)
        assert valid is False

    def test_oversized_file_invalid(self, engine: DiffEngine) -> None:
        big_content = "x" * (6 * 1024 * 1024)  # 6 MB
        diff = FileDiff(
            operation=DiffOperation.CREATE,
            file_path="big.py",
            new_content=big_content,
            line_changes={"additions": 1, "deletions": 0},
        )
        valid, warnings = engine.validate_diff(diff)
        assert valid is False
        assert any("5 MB" in w for w in warnings)


# ── apply_diff ────────────────────────────────────────────────────────────────

class TestApplyDiff:
    def test_apply_create(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        diff = engine.create_diff("new_file.py", "x = 42\n", DiffOperation.CREATE)
        engine.apply_diff(diff)
        assert (tmp_workspace / "new_file.py").read_text() == "x = 42\n"
        assert diff.applied is True

    def test_apply_modify(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        (tmp_workspace / "target.py").write_text("x = 1\n")
        diff = engine.create_diff("target.py", "x = 99\n", DiffOperation.MODIFY)
        engine.apply_diff(diff)
        assert (tmp_workspace / "target.py").read_text() == "x = 99\n"
        assert diff.backup_path is not None

    def test_apply_delete(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        p = tmp_workspace / "del_me.py"
        p.write_text("pass\n")
        diff = engine.create_diff("del_me.py", "", DiffOperation.DELETE)
        engine.apply_diff(diff)
        assert not p.exists()

    def test_dry_run_does_not_write(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        diff = engine.create_diff("dry.py", "pass\n", DiffOperation.CREATE)
        engine.apply_diff(diff, dry_run=True)
        assert not (tmp_workspace / "dry.py").exists()
        assert diff.applied is False

    def test_creates_parent_dirs(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        diff = engine.create_diff("deep/nested/file.py", "pass\n", DiffOperation.CREATE)
        engine.apply_diff(diff)
        assert (tmp_workspace / "deep/nested/file.py").exists()


# ── rollback ──────────────────────────────────────────────────────────────────

class TestRollback:
    def test_rollback_create(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        diff = engine.create_diff("rollback_me.py", "pass\n", DiffOperation.CREATE)
        engine.apply_diff(diff)
        assert (tmp_workspace / "rollback_me.py").exists()
        engine.rollback_diff(diff)
        assert not (tmp_workspace / "rollback_me.py").exists()

    def test_rollback_modify(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        p = tmp_workspace / "original.py"
        p.write_text("original content\n")
        diff = engine.create_diff("original.py", "modified content\n", DiffOperation.MODIFY)
        engine.apply_diff(diff)
        assert p.read_text() == "modified content\n"
        engine.rollback_diff(diff)
        assert p.read_text() == "original content\n"

    def test_rollback_unapplied_diff_noop(self, engine: DiffEngine) -> None:
        diff = FileDiff(
            operation=DiffOperation.CREATE,
            file_path="never_applied.py",
            new_content="pass",
        )
        result = engine.rollback_diff(diff)
        assert result is True  # Should succeed without error


# ── apply_diffs (batch) ───────────────────────────────────────────────────────

class TestApplyDiffs:
    def test_batch_apply_success(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        diffs = [
            engine.create_diff(f"file_{i}.py", f"x = {i}\n", DiffOperation.CREATE)
            for i in range(3)
        ]
        result = engine.apply_diffs(diffs)
        assert result.applied == 3
        assert result.failed == 0
        assert result.success

    def test_batch_rollback_on_error(self, engine: DiffEngine, tmp_workspace: Path) -> None:
        # First diff is valid, second will fail (file doesn't exist for MODIFY)
        good = engine.create_diff("good.py", "pass\n", DiffOperation.CREATE)
        bad = FileDiff(
            operation=DiffOperation.MODIFY,
            file_path="nonexistent.py",
            original_content="x",
            new_content="y",
            line_changes={"additions": 1, "deletions": 1},
        )
        result = engine.apply_diffs([good, bad], stop_on_error=True)
        assert result.failed > 0
        # good.py should have been rolled back
        assert not (tmp_workspace / "good.py").exists()
