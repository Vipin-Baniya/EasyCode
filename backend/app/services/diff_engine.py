"""
Diff Engine - Enhanced Production Implementation

Safe, atomic, reversible code modifications with:
- SHA-256 content checksums for integrity verification
- Concurrent diff application (thread-safe)
- Dry-run mode
- HTML diff preview (optional)
- Size limits to prevent accidental overwrites
- Improved backup naming to avoid collisions
- Proper use of Optional / None typing
"""

from __future__ import annotations

import difflib
import hashlib
import shutil
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Enums / data models
# ---------------------------------------------------------------------------

class DiffOperation(str, Enum):
    CREATE = "create"
    MODIFY = "modify"
    DELETE = "delete"


@dataclass
class FileDiff:
    """Represents a pending or applied diff for a single file."""
    operation: DiffOperation
    file_path: str
    original_content: str | None = None
    new_content: str | None = None
    unified_diff: str | None = None
    line_changes: dict[str, int] = field(default_factory=lambda: {"additions": 0, "deletions": 0})
    applied: bool = False
    backup_path: str | None = None
    checksum_before: str | None = None   # SHA-256 of original
    checksum_after: str | None = None    # SHA-256 of new_content
    applied_at: str | None = None        # ISO-8601 timestamp


@dataclass
class ApplyResult:
    total: int
    applied: int
    failed: int
    skipped: int
    errors: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.failed == 0


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Max size for a single file write (default 5 MB)
_MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024
# Warn (but don't block) on diffs larger than this many lines
_LARGE_DIFF_LINES = 500


# ---------------------------------------------------------------------------
# DiffEngine
# ---------------------------------------------------------------------------

class DiffEngine:
    """
    Production-grade, thread-safe diff engine.

    Usage:
        engine = DiffEngine(workspace_path="/path/to/project")
        diff = engine.create_diff("src/auth.py", new_code, DiffOperation.CREATE)
        engine.apply_diff(diff)
        engine.rollback_diff(diff)   # undo if needed
    """

    def __init__(
        self,
        workspace_root: str | Path,
        backup_retention_days: int = 7,
    ) -> None:
        self.workspace_root = Path(workspace_root).resolve()
        self.backup_dir = self.workspace_root / ".project_core_backups"
        self.backup_dir.mkdir(parents=True, exist_ok=True)
        self._backup_retention_days = backup_retention_days
        self._lock = threading.Lock()

    # -----------------------------------------------------------------------
    # Create diff
    # -----------------------------------------------------------------------

    def create_diff(
        self,
        file_path: str,
        new_content: str | None,
        operation: DiffOperation = DiffOperation.MODIFY,
        original_content: str | None = None,
    ) -> FileDiff:
        """
        Build a FileDiff object (does NOT touch the filesystem).

        Args:
            file_path: Path relative to workspace root.
            new_content: New file content (None for DELETE).
            operation: CREATE | MODIFY | DELETE.
            original_content: Explicit original; read from disk if absent.
        """
        logger.debug("Creating diff — %s %s", operation.value, file_path)
        full_path = self.workspace_root / file_path

        # Resolve original content
        if operation == DiffOperation.MODIFY and original_content is None:
            if full_path.exists():
                original_content = full_path.read_text(encoding="utf-8", errors="replace")
            else:
                logger.warning("%s does not exist; treating as CREATE", file_path)
                operation = DiffOperation.CREATE
                original_content = None

        # Generate unified diff
        unified: str | None = None
        additions = deletions = 0

        if operation in (DiffOperation.MODIFY, DiffOperation.DELETE):
            orig_lines = (original_content or "").splitlines(keepends=True)
            new_lines = (new_content or "").splitlines(keepends=True)
            diff_lines = list(difflib.unified_diff(
                orig_lines, new_lines,
                fromfile=f"a/{file_path}",
                tofile=f"b/{file_path}",
                lineterm="",
            ))
            if diff_lines:
                unified = "\n".join(diff_lines)
            for line in diff_lines:
                if line.startswith("+") and not line.startswith("+++"):
                    additions += 1
                elif line.startswith("-") and not line.startswith("---"):
                    deletions += 1

        elif operation == DiffOperation.CREATE:
            additions = len((new_content or "").splitlines())

        # Checksums
        def _sha(text: str | None) -> str | None:
            return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else None

        return FileDiff(
            operation=operation,
            file_path=file_path,
            original_content=original_content,
            new_content=new_content,
            unified_diff=unified,
            line_changes={"additions": additions, "deletions": deletions},
            checksum_before=_sha(original_content),
            checksum_after=_sha(new_content),
        )

    # -----------------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------------

    def validate_diff(self, diff: FileDiff) -> tuple[bool, list[str]]:
        """
        Pre-apply validation.

        Returns:
            (is_valid, list_of_warnings)
        """
        warnings: list[str] = []
        full_path = self.workspace_root / diff.file_path

        # File existence checks
        if diff.operation == DiffOperation.CREATE:
            if full_path.exists():
                warnings.append(f"CREATE: file already exists — {diff.file_path}")
                return False, warnings

        elif diff.operation in (DiffOperation.MODIFY, DiffOperation.DELETE):
            if not full_path.exists():
                warnings.append(f"{diff.operation.value.upper()}: file not found — {diff.file_path}")
                return False, warnings

        # Content integrity check (if we have original)
        if diff.operation == DiffOperation.MODIFY and diff.checksum_before and full_path.exists():
            current_sha = hashlib.sha256(
                full_path.read_bytes()
            ).hexdigest()
            if current_sha != diff.checksum_before:
                warnings.append(
                    f"INTEGRITY: {diff.file_path} was modified since diff was created — "
                    "contents may have changed."
                )

        # Size guard
        content = diff.new_content or ""
        if len(content.encode("utf-8")) > _MAX_FILE_SIZE_BYTES:
            warnings.append(
                f"SIZE: {diff.file_path} exceeds {_MAX_FILE_SIZE_BYTES // 1024 // 1024} MB limit"
            )
            return False, warnings

        # Large change warning
        total_lines = diff.line_changes["additions"] + diff.line_changes["deletions"]
        if total_lines > _LARGE_DIFF_LINES:
            warnings.append(
                f"Large change: {total_lines} lines modified in {diff.file_path}. "
                "Consider splitting into smaller diffs."
            )

        return True, warnings

    # -----------------------------------------------------------------------
    # Single diff apply / rollback
    # -----------------------------------------------------------------------

    def apply_diff(self, diff: FileDiff, dry_run: bool = False) -> bool:
        """
        Apply a single diff to the filesystem.

        Thread-safe via internal lock.

        Returns:
            True on success.
        Raises:
            ValueError / OSError on failure.
        """
        with self._lock:
            valid, warnings = self.validate_diff(diff)
            for w in warnings:
                logger.warning("Diff warning: %s", w)
            if not valid:
                raise ValueError(f"Invalid diff for {diff.file_path}: {warnings}")

            if dry_run:
                logger.info("[DRY-RUN] Would %s: %s", diff.operation.value, diff.file_path)
                return True

            full_path = self.workspace_root / diff.file_path
            full_path.parent.mkdir(parents=True, exist_ok=True)

            # Backup before destructive ops
            if diff.operation in (DiffOperation.MODIFY, DiffOperation.DELETE):
                diff.backup_path = self._create_backup(full_path)

            if diff.operation == DiffOperation.CREATE:
                full_path.write_text(diff.new_content or "", encoding="utf-8")
                logger.info("✅ Created : %s (+%d lines)", diff.file_path, diff.line_changes["additions"])

            elif diff.operation == DiffOperation.MODIFY:
                full_path.write_text(diff.new_content or "", encoding="utf-8")
                logger.info(
                    "✅ Modified: %s (+%d/-%d)",
                    diff.file_path,
                    diff.line_changes["additions"],
                    diff.line_changes["deletions"],
                )

            elif diff.operation == DiffOperation.DELETE:
                full_path.unlink()
                logger.info("✅ Deleted : %s", diff.file_path)

            diff.applied = True
            diff.applied_at = datetime.now(timezone.utc).isoformat()
            return True

    def rollback_diff(self, diff: FileDiff) -> bool:
        """Undo a single applied diff."""
        if not diff.applied:
            logger.debug("Diff not applied — nothing to roll back: %s", diff.file_path)
            return True

        with self._lock:
            full_path = self.workspace_root / diff.file_path
            try:
                if diff.operation == DiffOperation.CREATE:
                    if full_path.exists():
                        full_path.unlink()
                    logger.info("🔄 Rolled back CREATE: %s", diff.file_path)

                elif diff.operation in (DiffOperation.MODIFY, DiffOperation.DELETE):
                    if diff.backup_path:
                        self._restore_backup(full_path, diff.backup_path)
                    else:
                        # No backup — reconstruct from original_content
                        if diff.original_content is not None:
                            full_path.write_text(diff.original_content, encoding="utf-8")
                        else:
                            logger.warning("No backup or original_content for rollback of %s", diff.file_path)
                            return False
                    logger.info("🔄 Rolled back %s: %s", diff.operation.value, diff.file_path)

                diff.applied = False
                return True

            except Exception as exc:
                logger.error("Rollback failed for %s: %s", diff.file_path, exc)
                return False

    # -----------------------------------------------------------------------
    # Batch apply / rollback
    # -----------------------------------------------------------------------

    def apply_diffs(
        self,
        diffs: list[FileDiff],
        dry_run: bool = False,
        stop_on_error: bool = True,
    ) -> ApplyResult:
        """
        Apply multiple diffs.

        If stop_on_error=True (default), any failure rolls back all
        previously applied diffs and returns success=False.
        """
        result = ApplyResult(total=len(diffs), applied=0, failed=0, skipped=0)
        applied_so_far: list[FileDiff] = []

        for idx, diff in enumerate(diffs):
            try:
                self.apply_diff(diff, dry_run=dry_run)
                applied_so_far.append(diff)
                result.applied += 1

            except Exception as exc:
                result.failed += 1
                result.errors.append({"index": idx, "file": diff.file_path, "error": str(exc)})
                logger.error("Diff %d failed (%s): %s", idx, diff.file_path, exc)

                if stop_on_error:
                    logger.warning("Stopping and rolling back %d applied diffs", len(applied_so_far))
                    rb = self.rollback_diffs(applied_so_far)
                    result.applied -= rb.rolled_back
                    break

        logger.info(
            "apply_diffs — %d/%d applied, %d failed",
            result.applied, result.total, result.failed,
        )
        return result

    def rollback_diffs(self, diffs: list[FileDiff]) -> "RollbackResult":
        """Rollback in reverse order."""
        rolled_back = failed = 0
        for diff in reversed(diffs):
            if self.rollback_diff(diff):
                rolled_back += 1
            else:
                failed += 1
        logger.info("rollback_diffs — %d rolled back, %d failed", rolled_back, failed)
        return RollbackResult(total=len(diffs), rolled_back=rolled_back, failed=failed)

    # -----------------------------------------------------------------------
    # Previews
    # -----------------------------------------------------------------------

    def preview_text(self, diff: FileDiff) -> str:
        """Plain-text diff preview."""
        sep = "=" * 62
        lines = [
            sep,
            f"Operation : {diff.operation.value.upper()}",
            f"File      : {diff.file_path}",
            f"Changes   : +{diff.line_changes['additions']} / -{diff.line_changes['deletions']}",
            sep,
        ]
        if diff.unified_diff:
            lines += ["", diff.unified_diff]
        elif diff.operation == DiffOperation.CREATE and diff.new_content:
            preview = diff.new_content[:800]
            lines += ["", preview]
            if len(diff.new_content) > 800:
                lines.append(f"\n… ({len(diff.new_content)} total chars)")
        return "\n".join(lines)

    def preview_html(self, diff: FileDiff) -> str:
        """Side-by-side HTML diff (for web UIs)."""
        differ = difflib.HtmlDiff(wrapcolumn=80)
        orig_lines = (diff.original_content or "").splitlines()
        new_lines = (diff.new_content or "").splitlines()
        return differ.make_table(
            orig_lines, new_lines,
            fromdesc="Before", todesc="After",
            context=True, numlines=3,
        )

    # -----------------------------------------------------------------------
    # Backup helpers
    # -----------------------------------------------------------------------

    def _create_backup(self, file_path: Path) -> str | None:
        if not file_path.exists():
            return None
        ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
        # Include stem hash to avoid collisions on same-named files
        stem_hash = hashlib.md5(str(file_path).encode()).hexdigest()[:6]
        backup_name = f"{file_path.name}.{ts}.{stem_hash}.bak"
        backup_path = self.backup_dir / backup_name
        shutil.copy2(file_path, backup_path)
        logger.debug("Backup created: %s", backup_path)
        return str(backup_path)

    def _restore_backup(self, file_path: Path, backup_path: str) -> None:
        bp = Path(backup_path)
        if bp.exists():
            file_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(bp, file_path)
            logger.debug("Restored from backup: %s → %s", bp.name, file_path)
        else:
            logger.warning("Backup not found: %s", backup_path)

    def cleanup_backups(self) -> int:
        """Remove backup files older than retention period. Returns count deleted."""
        cutoff = datetime.now(timezone.utc).timestamp() - (
            self._backup_retention_days * 86_400
        )
        removed = 0
        for bak in self.backup_dir.glob("*.bak"):
            try:
                if bak.stat().st_mtime < cutoff:
                    bak.unlink()
                    removed += 1
            except Exception:
                pass
        if removed:
            logger.info("Cleaned up %d old backups", removed)
        return removed


# ---------------------------------------------------------------------------
# Rollback result (separate to avoid circular ref)
# ---------------------------------------------------------------------------

@dataclass
class RollbackResult:
    total: int
    rolled_back: int
    failed: int

    @property
    def success(self) -> bool:
        return self.failed == 0
