# Intelligent Core — Enhancement Changelog

**Total: 3,325 lines (+652 from v1 / +24%)**

---

## code_analyzer.py (604 → 767 lines)

### Bug Fixes
- `@dataclass` mutable default arguments replaced with `field(default_factory=list)` — fixes `TypeError` at instantiation
- `asyncio.get_event_loop()` usage updated to handle already-running loops (FastAPI compatibility)
- File discovery now catches `PermissionError` instead of silently skipping

### Enhancements
- **Async-first**: `analyze_project_async()` for use inside FastAPI; `analyze_project()` wraps it safely
- **Parallel file analysis**: all files analysed concurrently via `asyncio.gather` + thread pool
- **Security scan**: 9 OWASP-aligned pattern checks (hardcoded secrets, SQLi, eval, pickle, shell injection, JWT bypass, SSL bypass, DEBUG flag)
- **Complexity scoring**: lightweight McCabe-style estimate for both Python and JS/TS
- **Type-hint coverage detection**: `has_type_hints` flag on Python files
- **CI/CD detection**: GitHub Actions, GitLab CI, Jenkins, CircleCI, Travis, Bitbucket
- **Docker detection**: `has_docker` flag
- **pyproject.toml** parsed alongside `requirements.txt` for Python deps
- **15 additional frameworks**: alembic, celery, redis, pydantic, pytest, vitest, jest, vue composables
- **`_extract_python_exports`**: parses `__all__` + top-level class/def names
- **Improved JS import parser**: handles `require()` and scoped packages
- Extended `ignore_dirs` and `supported_extensions` (`.scss`, `.sh`, `.toml`, `.env`)

---

## planner.py (405 → 463 lines)

### Bug Fixes
- `llm.generate_structured` now wrapped in retry loop — single failure no longer causes silent fallback
- Plan step `action` field defaulted to `"modify"` only if invalid value received

### Enhancements
- **Pydantic v2 validation**: `PlanStep`, `NewDependencies`, `ExecutionPlan` — invalid plans are coerced rather than silently dropped
- **Retry with exponential back-off**: up to 3 attempts with `1.5^n` second delays
- **`past_lessons` parameter**: injects Reflector lessons into planning context for continuous improvement
- **`session_context.chat_history`**: recent messages included in context for conversational continuity
- **Security findings injection**: high-severity findings from analyzer surfaced to planner
- **Token-budget-aware context**: each section is capped to prevent exceeding context window
- **`@model_validator`**: auto-renumbers steps sequentially after validation

---

## executor.py (531 → 620 lines)

### Bug Fixes
- `import re` was inside a function body — moved to module level
- Modification output < 20 chars now falls back to original + TODO instead of overwriting with empty file
- `_clean_generated_code` replaced with `_extract_code` — correctly handles nested fences and language-tagged blocks

### Enhancements
- **Parallel step execution**: independent `create` steps run concurrently (up to 4 via semaphore)
- **`_partition_steps`**: separates independent from dependent steps for safe parallelism
- **`dry_run` mode**: preview diffs without touching the filesystem
- **Extended language support**: SQL, shell/bash, YAML, JSON, Markdown, CSS/SCSS
- **Language-specific system prompts**: Python (PEP 8, Pydantic v2, loguru), TypeScript (strict, no `any`), SQL (indexes, guards), shell (`set -euo pipefail`)
- **Context trimming**: large existing files are head+tail trimmed rather than hard-cut
- **`_stub` fallback**: language-aware stubs (Python, TS/JS, SQL, shell)
- **`apply_diffs` call moved to executor**: diffs now applied atomically after all steps complete

---

## verifier.py (426 → 561 lines)

### Bug Fixes
- `py_compile` replaced with `ast.parse` — works without writing `.pyc` files
- `asyncio.wait_for` correctly kills subprocess on timeout rather than leaving zombie processes
- `process.returncode == 5` (pytest no-tests-found) now treated as pass

### Enhancements
- **Structured `VerificationReport` dataclass** — typed result instead of raw dict
- **`ruff` linter**: replaces flake8 — faster, modern, supports `--select=E,W,F,I`
- **`tsc --noEmit` TypeScript type-checking** via `npx tsc`
- **ESLint integration** (only when `.eslintrc.*` present, to avoid noise)
- **Parallel syntax checks**: all changed files checked concurrently
- **pytest-cov integration**: coverage % parsed and reported
- **Vitest detection**: auto-selects `npx vitest run` over `npm test` when vitest is installed
- **`tests_skipped` counter** in results
- **`lint_details` list** for surfacing specific lint violations to the UI

---

## reflector.py (310 → 456 lines)

### Bug Fixes
- In-memory `lesson_store` wiped on restart — replaced with JSON file persistence
- Duplicate lessons no longer stored (MD5 hash deduplication)

### Enhancements
- **Pydantic v2 `ReflectionResult`**: strict schema with `category_tags` and `severity` fields
- **JSON file-backed store**: lessons survive service restarts in `.project_core_data/lessons_{id}.json`
- **Lesson categorisation**: quality / security / performance / architecture
- **`severity` field**: info / warning / critical — surfaces critical issues to orchestrator
- **Semantic suggestion matching**: `generate_improvement_suggestions` matches past lessons by category against current plan intent
- **`LessonEntry` dataclass** with timestamp, action_id, and hash_key
- **Configurable `data_dir`**: injectable for testing

---

## diff_engine.py (397 → 458 lines)

### Bug Fixes
- `_create_backup` returned `None` for non-existent files — now returns `None` explicitly and callers handle it
- `rollback_diff` now falls back to `original_content` if backup file is missing
- `backup_path` naming collision fixed: includes stem hash + microsecond timestamp

### Enhancements
- **SHA-256 checksums**: `checksum_before` / `checksum_after` on every diff
- **Integrity check**: warns if file was externally modified between `create_diff` and `apply_diff`
- **Thread-safe**: internal `threading.Lock` on all filesystem writes
- **`ApplyResult` and `RollbackResult` dataclasses** — typed return values with `.success` property
- **`preview_html`**: side-by-side HTML diff table for web UI rendering
- **`dry_run` support** in `apply_diff` and `apply_diffs`
- **Size limit** (5 MB default) prevents accidental file corruption
- **`backup_retention_days`** configurable; `cleanup_backups()` returns deletion count
- **`.bak` extension** (was `.backup`) for clarity; consistent naming scheme

---

## Dependency Summary

| Package    | Version Requirement | Usage |
|------------|---------------------|-------|
| `loguru`   | ≥ 0.7               | All files — structured logging |
| `pydantic` | ≥ 2.0               | planner, reflector — data validation |
| Python     | ≥ 3.11              | `X \| Y` union syntax, `sys.stdlib_module_names` |

All other imports are Python stdlib only.
