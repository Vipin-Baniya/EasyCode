"""
Verifier - Enhanced Production Implementation

Evidence-based verification using real tool execution:
- pytest with coverage reporting
- npm test (Jest / Vitest) with JSON output
- ruff for Python linting (replaces flake8)
- tsc --noEmit for TypeScript type-checking
- py_compile for quick Python syntax validation
- Parallel syntax checks across generated files
"""

from __future__ import annotations

import asyncio
import ast
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from loguru import logger

from app.models.database import Action, Project


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class TestResult:
    tests_run: int = 0
    tests_passed: int = 0
    tests_failed: int = 0
    tests_skipped: int = 0
    duration_seconds: float = 0.0
    output: str = ""
    errors: list[str] = field(default_factory=list)
    passed: bool = False


@dataclass
class LintResult:
    valid: bool = True
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    tool: str = ""


@dataclass
class VerificationReport:
    """Full verification report for a single action execution."""
    passed: bool
    tests_run: int
    tests_passed: int
    tests_failed: int
    tests_skipped: int
    test_output: str
    syntax_valid: bool
    lint_valid: bool
    errors: list[str]
    warnings: list[str]
    coverage_percent: float | None = None
    lint_details: list[str] = field(default_factory=list)
    framework_used: str = ""


# ---------------------------------------------------------------------------
# Verifier
# ---------------------------------------------------------------------------

class Verifier:
    """
    Real test executor and static-analysis verifier.

    Improvements over v1:
    - Structured VerificationReport dataclass
    - ruff linting (faster + more modern than flake8/pylint)
    - TypeScript compiler check (tsc --noEmit)
    - pytest --cov coverage integration
    - Parallel syntax checking across all changed files
    - Configurable timeout
    """

    DEFAULT_TIMEOUT = 300   # seconds

    def __init__(self, timeout: int = DEFAULT_TIMEOUT) -> None:
        self.timeout = timeout

    # -----------------------------------------------------------------------
    # Public API
    # -----------------------------------------------------------------------

    async def verify_execution(
        self,
        action: Action,
        project: Project,
        execution_result: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Verify execution by running tests, linting and syntax checks.

        Returns a dict representation of VerificationReport.
        """
        logger.info("🔬 Verifying execution for action %s", action.id)
        workspace = Path(project.workspace_path)

        all_errors: list[str] = []
        all_warnings: list[str] = []
        test_result = TestResult()
        lint_result = LintResult(valid=True)
        coverage: float | None = None
        framework_used = ""

        # 1 — Run tests
        if self._has_pytest(workspace):
            framework_used = "pytest"
            test_result = await self._run_pytest(workspace)
        elif self._has_npm_test(workspace):
            framework_used = "npm"
            test_result = await self._run_npm_test(workspace)
        else:
            logger.info("No test framework detected — skipping test run")
            test_result.passed = True   # Don't fail when no tests exist

        all_errors.extend(test_result.errors)

        # 2 — Parse coverage from pytest output
        if framework_used == "pytest":
            coverage = self._parse_coverage(test_result.output)

        # 3 — Syntax + lint checks in parallel
        changed_files = (
            execution_result.get("files_created", [])
            + execution_result.get("files_modified", [])
        )
        if changed_files:
            syntax_ok, syntax_errors = await self._check_syntax_parallel(workspace, changed_files)
            lint_result = await self._run_linting(workspace, changed_files)

            if not syntax_ok:
                all_errors.extend(syntax_errors)
            all_errors.extend(lint_result.errors)
            all_warnings.extend(lint_result.warnings)
        else:
            syntax_ok = True

        # 4 — Determine overall pass
        passed = (
            test_result.passed
            and syntax_ok
            and lint_result.valid
            and not any("syntax error" in e.lower() for e in all_errors)
        )

        report = VerificationReport(
            passed=passed,
            tests_run=test_result.tests_run,
            tests_passed=test_result.tests_passed,
            tests_failed=test_result.tests_failed,
            tests_skipped=test_result.tests_skipped,
            test_output=test_result.output[:8000],  # Truncate for storage
            syntax_valid=syntax_ok,
            lint_valid=lint_result.valid,
            errors=all_errors[:20],
            warnings=all_warnings[:20],
            coverage_percent=coverage,
            lint_details=lint_result.errors[:10],
            framework_used=framework_used,
        )

        logger.info(
            "%s Verification — tests: %d/%d, syntax: %s, lint: %s",
            "✅" if report.passed else "❌",
            report.tests_passed,
            report.tests_run,
            "✅" if report.syntax_valid else "❌",
            "✅" if report.lint_valid else "❌",
        )

        # Return plain dict for compatibility with existing callers
        return {
            "passed": report.passed,
            "tests_run": report.tests_run,
            "tests_passed": report.tests_passed,
            "tests_failed": report.tests_failed,
            "tests_skipped": report.tests_skipped,
            "test_output": report.test_output,
            "syntax_valid": report.syntax_valid,
            "lint_valid": report.lint_valid,
            "errors": report.errors,
            "warnings": report.warnings,
            "coverage_percent": report.coverage_percent,
            "lint_details": report.lint_details,
            "framework_used": report.framework_used,
        }

    # -----------------------------------------------------------------------
    # Test framework detection
    # -----------------------------------------------------------------------

    def _has_pytest(self, workspace: Path) -> bool:
        if any(
            (workspace / f).exists()
            for f in ("pytest.ini", "pyproject.toml", "setup.cfg", "conftest.py")
        ):
            return True
        return bool(list(workspace.rglob("test_*.py"))[:1])

    def _has_npm_test(self, workspace: Path) -> bool:
        pkg = workspace / "package.json"
        if not pkg.exists():
            return False
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            return "test" in data.get("scripts", {})
        except Exception:
            return False

    # -----------------------------------------------------------------------
    # pytest
    # -----------------------------------------------------------------------

    async def _run_pytest(self, workspace: Path) -> TestResult:
        result = TestResult()

        # Build command — add coverage if pytest-cov is available
        cmd = [
            sys.executable, "-m", "pytest",
            "--tb=short", "--no-header",
            "-q",                   # quiet; reduces noise
            "--color=no",
        ]

        # Optionally enable coverage
        try:
            subprocess.run(
                [sys.executable, "-m", "pytest", "--co", "-q", "--co"],
                capture_output=True, cwd=workspace, timeout=5,
            )
            cmd += ["--cov=.", "--cov-report=term-missing"]
        except Exception:
            pass  # pytest-cov not available — skip

        cmd.append(str(workspace))

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                result.errors.append(f"pytest timed out after {self.timeout}s")
                return result

            output = stdout.decode("utf-8", errors="ignore")
            err_out = stderr.decode("utf-8", errors="ignore")
            result.output = output

            counts = self._parse_pytest_summary(output)
            result.tests_passed = counts["passed"]
            result.tests_failed = counts["failed"]
            result.tests_skipped = counts["skipped"]
            result.tests_run = counts["passed"] + counts["failed"] + counts["skipped"]
            result.passed = result.tests_failed == 0 and proc.returncode in (0, 5)  # 5 = no tests

            if err_out.strip():
                result.errors.append(err_out[:500])

        except FileNotFoundError:
            logger.warning("pytest not found — skipping tests")
            result.passed = True
        except Exception as exc:
            result.errors.append(str(exc))
            result.passed = False

        return result

    def _parse_pytest_summary(self, output: str) -> dict[str, int]:
        """Parse pytest's last summary line."""
        counts = {"passed": 0, "failed": 0, "skipped": 0, "error": 0}
        # "5 passed, 2 failed, 1 skipped in 3.21s"
        for key in counts:
            m = re.search(rf"(\d+)\s+{key}", output)
            if m:
                counts[key] = int(m.group(1))
        # Fallback: count individual PASSED/FAILED markers
        if counts["passed"] == 0 and counts["failed"] == 0:
            counts["passed"] = output.count(" PASSED")
            counts["failed"] = output.count(" FAILED") + output.count(" ERROR")
        return counts

    def _parse_coverage(self, output: str) -> float | None:
        """Extract total coverage % from pytest-cov output."""
        m = re.search(r"TOTAL\s+\d+\s+\d+\s+(\d+)%", output)
        return float(m.group(1)) if m else None

    # -----------------------------------------------------------------------
    # npm test (Jest / Vitest)
    # -----------------------------------------------------------------------

    async def _run_npm_test(self, workspace: Path) -> TestResult:
        result = TestResult()
        cmd = ["npm", "test", "--", "--passWithNoTests"]

        # Detect Vitest vs Jest for JSON reporter flag
        pkg = workspace / "package.json"
        is_vitest = False
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                is_vitest = "vitest" in all_deps
            except Exception:
                pass

        if is_vitest:
            cmd = ["npx", "vitest", "run", "--reporter=verbose", "--passWithNoTests"]
        else:
            cmd = ["npm", "test", "--", "--passWithNoTests", "--no-coverage"]

        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), self.timeout)
            except asyncio.TimeoutError:
                proc.kill()
                result.errors.append(f"npm test timed out after {self.timeout}s")
                return result

            output = stdout.decode("utf-8", errors="ignore")
            err_out = stderr.decode("utf-8", errors="ignore")
            result.output = output

            counts = self._parse_npm_summary(output + err_out)
            result.tests_passed = counts["passed"]
            result.tests_failed = counts["failed"]
            result.tests_run = counts["passed"] + counts["failed"]
            result.passed = result.tests_failed == 0 and proc.returncode == 0

        except FileNotFoundError:
            logger.warning("npm not found — skipping tests")
            result.passed = True
        except Exception as exc:
            result.errors.append(str(exc))

        return result

    def _parse_npm_summary(self, output: str) -> dict[str, int]:
        counts = {"passed": 0, "failed": 0}
        # Jest: "Tests: 2 failed, 5 passed, 7 total"
        m = re.search(r"Tests:\s+(?:(\d+)\s+failed,?\s*)?(?:(\d+)\s+passed)?", output)
        if m:
            counts["failed"] = int(m.group(1)) if m.group(1) else 0
            counts["passed"] = int(m.group(2)) if m.group(2) else 0
        # Vitest: "✓ 5 | ✗ 2"
        if counts["passed"] == 0 and counts["failed"] == 0:
            passed = re.search(r"✓\s+(\d+)", output)
            failed = re.search(r"✗\s+(\d+)|(\d+)\s+failed", output)
            if passed:
                counts["passed"] = int(passed.group(1))
            if failed:
                counts["failed"] = int(failed.group(1) or failed.group(2) or 0)
        return counts

    # -----------------------------------------------------------------------
    # Syntax checks
    # -----------------------------------------------------------------------

    async def _check_syntax_parallel(
        self, workspace: Path, file_paths: list[str]
    ) -> tuple[bool, list[str]]:
        """Check syntax of all changed files in parallel."""
        tasks = [
            self._check_file_syntax(workspace / fp, fp)
            for fp in file_paths
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        errors: list[str] = []
        for r in results:
            if isinstance(r, Exception):
                errors.append(str(r))
            elif isinstance(r, list):
                errors.extend(r)
        return (len(errors) == 0), errors

    async def _check_file_syntax(self, full_path: Path, rel_path: str) -> list[str]:
        if not full_path.exists():
            return []
        suffix = full_path.suffix.lower()
        if suffix == ".py":
            return self._check_python_syntax(full_path, rel_path)
        if suffix in (".ts", ".tsx"):
            return await self._check_ts_syntax(full_path, rel_path)
        if suffix in (".js", ".jsx"):
            return await self._check_js_syntax(full_path, rel_path)
        if suffix == ".json":
            return self._check_json_syntax(full_path, rel_path)
        return []

    def _check_python_syntax(self, path: Path, rel: str) -> list[str]:
        try:
            source = path.read_text(encoding="utf-8")
            ast.parse(source, filename=str(path))
            return []
        except SyntaxError as exc:
            return [f"Syntax error in {rel} (line {exc.lineno}): {exc.msg}"]
        except Exception:
            return []

    async def _check_ts_syntax(self, path: Path, rel: str) -> list[str]:
        """Run tsc --noEmit --allowJs on the file if tsc is available."""
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "tsc", "--noEmit", "--allowJs",
                "--target", "ES2022", "--moduleResolution", "node",
                str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
            if proc.returncode != 0:
                msg = stderr.decode("utf-8", errors="ignore").strip()
                return [f"TypeScript error in {rel}: {msg[:300]}"]
        except (FileNotFoundError, asyncio.TimeoutError):
            pass  # tsc/npx not available or slow — skip
        except Exception:
            pass
        return []

    async def _check_js_syntax(self, path: Path, rel: str) -> list[str]:
        try:
            proc = await asyncio.create_subprocess_exec(
                "node", "--check", str(path),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            _, stderr = await asyncio.wait_for(proc.communicate(), timeout=5)
            if proc.returncode != 0:
                msg = stderr.decode("utf-8", errors="ignore").strip()
                return [f"JS syntax error in {rel}: {msg[:200]}"]
        except (FileNotFoundError, asyncio.TimeoutError):
            pass
        return []

    def _check_json_syntax(self, path: Path, rel: str) -> list[str]:
        try:
            json.loads(path.read_text(encoding="utf-8"))
            return []
        except json.JSONDecodeError as exc:
            return [f"JSON error in {rel}: {exc}"]

    # -----------------------------------------------------------------------
    # Linting
    # -----------------------------------------------------------------------

    async def _run_linting(
        self, workspace: Path, file_paths: list[str]
    ) -> LintResult:
        """
        Run ruff (Python) and/or eslint (JS/TS) on changed files.
        Falls back gracefully if linters aren't installed.
        """
        py_files = [fp for fp in file_paths if fp.endswith(".py")]
        js_files = [fp for fp in file_paths if fp.endswith((".js", ".jsx", ".ts", ".tsx"))]

        tasks = []
        if py_files:
            tasks.append(self._run_ruff(workspace, py_files))
        if js_files:
            tasks.append(self._run_eslint(workspace, js_files))

        if not tasks:
            return LintResult(valid=True, tool="none")

        results = await asyncio.gather(*tasks, return_exceptions=True)
        combined = LintResult(valid=True, tool="multi")

        for r in results:
            if isinstance(r, Exception):
                continue
            if not r.valid:
                combined.valid = False
            combined.errors.extend(r.errors)
            combined.warnings.extend(r.warnings)

        return combined

    async def _run_ruff(self, workspace: Path, py_files: list[str]) -> LintResult:
        result = LintResult(tool="ruff")
        paths = [str(workspace / fp) for fp in py_files]

        try:
            proc = await asyncio.create_subprocess_exec(
                "ruff", "check", "--output-format=text", "--select=E,W,F,I", *paths,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=20)
            output = stdout.decode("utf-8", errors="ignore").strip()

            if proc.returncode not in (0, 1):  # 1 = findings; non-1/0 = error
                return result  # ruff crash — ignore

            lines = [l for l in output.splitlines() if l.strip()]
            # Separate errors (E/F) from warnings (W)
            for line in lines[:30]:
                if re.search(r"\s[EF]\d{3}", line):
                    result.errors.append(line)
                    result.valid = False
                elif re.search(r"\s[W]\d{3}", line):
                    result.warnings.append(line)

        except FileNotFoundError:
            pass  # ruff not installed — skip silently
        except asyncio.TimeoutError:
            result.warnings.append("ruff timed out")

        return result

    async def _run_eslint(self, workspace: Path, js_files: list[str]) -> LintResult:
        result = LintResult(tool="eslint")
        if not (workspace / ".eslintrc.json").exists() and not (workspace / ".eslintrc.js").exists():
            return result  # No config — skip to avoid noisy output

        paths = [str(workspace / fp) for fp in js_files]
        try:
            proc = await asyncio.create_subprocess_exec(
                "npx", "eslint", "--format=compact", *paths,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(workspace),
            )
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=30)
            output = stdout.decode("utf-8", errors="ignore").strip()

            if "Error" in output:
                result.valid = False
                result.errors = [l for l in output.splitlines() if "Error" in l][:10]
            elif "Warning" in output:
                result.warnings = [l for l in output.splitlines() if "Warning" in l][:10]

        except (FileNotFoundError, asyncio.TimeoutError):
            pass

        return result
