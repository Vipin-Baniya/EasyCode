"""
Code Analyzer - Enhanced Production Implementation

Deep project analysis engine with async support, complexity scoring,
security pattern detection, and comprehensive tech stack intelligence.
"""

from __future__ import annotations

import ast
import asyncio
import json
import re
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from loguru import logger


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class FileInfo:
    """Detailed information about a single file."""
    path: str
    name: str
    extension: str
    size: int
    lines: int
    language: str
    is_test: bool = False
    is_config: bool = False
    is_entry_point: bool = False
    imports: list[str] = field(default_factory=list)
    exports: list[str] = field(default_factory=list)
    complexity_score: int = 0          # Cyclomatic-style estimate
    has_type_hints: bool = False        # Python type-annotation coverage
    has_docstrings: bool = False


@dataclass
class SecurityFinding:
    """A potential security issue found in the codebase."""
    file_path: str
    line_number: int
    severity: str      # "high" | "medium" | "low"
    category: str      # e.g. "hardcoded_secret", "sql_injection"
    description: str
    snippet: str


@dataclass
class ProjectStructure:
    """Complete project structure analysis."""
    root_path: str
    total_files: int
    total_lines: int
    languages: dict[str, int]
    frameworks: list[str]
    patterns: list[str]
    entry_points: list[str]
    files: list[dict[str, Any]]
    directories: list[str]
    source_files: list[str]
    test_files: list[str]
    config_files: list[str]
    models: list[str]
    routes: list[str]
    components: list[str]
    services: list[str]
    utils: list[str]
    python_dependencies: list[str]
    npm_dependencies: list[str]
    import_graph: dict[str, list[str]]
    tech_stack_summary: str
    security_findings: list[dict[str, Any]] = field(default_factory=list)
    avg_complexity_score: float = 0.0
    test_coverage_ratio: float = 0.0   # test files / source files
    has_ci: bool = False
    has_docker: bool = False
    has_type_hints: bool = False


# ---------------------------------------------------------------------------
# Main analyzer
# ---------------------------------------------------------------------------

class CodeAnalyzer:
    """
    Async-capable code analyzer with deep project intelligence.

    Capabilities:
    - Async file discovery and parallel analysis
    - Language, framework and dependency detection
    - Import/export graph construction
    - Architectural pattern recognition
    - Security smell detection
    - Complexity estimation
    - CI/CD and Docker awareness
    """

    # ---- Configuration constants -------------------------------------------

    SUPPORTED_EXTENSIONS: dict[str, str] = {
        ".py": "python",
        ".js": "javascript",
        ".jsx": "javascript",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".json": "json",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".md": "markdown",
        ".html": "html",
        ".css": "css",
        ".scss": "css",
        ".sql": "sql",
        ".sh": "shell",
        ".toml": "toml",
        ".env": "env",
    }

    FRAMEWORK_INDICATORS: dict[str, list[str]] = {
        "fastapi": ["from fastapi", "FastAPI()", "@app.get", "@app.post", "APIRouter", "Depends("],
        "flask": ["from flask", "Flask(__name__)", "@app.route", "Blueprint("],
        "django": ["from django", "django.conf", "models.Model", "admin.site", "INSTALLED_APPS"],
        "react": ["from 'react'", 'from "react"', "useState", "useEffect", "React.FC", "JSX.Element"],
        "nextjs": ["next/", "getServerSideProps", "getStaticProps", "NextPage", "useRouter"],
        "vue": ["createApp", "defineComponent", "ref(", "reactive(", "computed("],
        "express": ["express()", "app.listen", 'require("express")', "Router()"],
        "nestjs": ["@nestjs/", "NestFactory", "@Controller", "@Injectable", "@Module"],
        "sqlalchemy": ["from sqlalchemy", "declarative_base", "Column(", "relationship(", "Session"],
        "alembic": ["from alembic", "op.create_table", "upgrade()", "downgrade()"],
        "prisma": ["PrismaClient", "@prisma/client", "prisma."],
        "tailwindcss": ["@tailwind", "tailwind.config", 'className="', "tw`"],
        "celery": ["from celery", "Celery(", "@app.task", "@shared_task"],
        "redis": ["import redis", "from redis", "Redis(", "StrictRedis"],
        "pydantic": ["from pydantic", "BaseModel", "Field(", "validator(", "model_validator"],
        "pytest": ["import pytest", "from pytest", "@pytest.fixture", "@pytest.mark"],
        "vitest": ["from 'vitest'", 'from "vitest"', "describe(", "it(", "expect("],
        "jest": ["from '@jest", "jest.fn()", "describe(", "expect(", "beforeEach("],
    }

    IGNORE_DIRS: frozenset[str] = frozenset({
        "node_modules", "__pycache__", ".git", ".venv", "venv",
        "env", ".pytest_cache", "dist", "build", ".next", "coverage",
        ".idea", ".vscode", "htmlcov", ".mypy_cache", ".tox",
        ".eggs", "*.egg-info", ".cache",
    })

    # Security smell patterns  (pattern, severity, category, description)
    SECURITY_PATTERNS: list[tuple[str, str, str, str]] = [
        (r'(?i)(password|passwd|secret|api_key|apikey|token)\s*=\s*["\'][^"\']{4,}["\']',
         "high", "hardcoded_secret", "Hardcoded credential or secret"),
        (r'(?i)execute\s*\(\s*["\'].*%s.*["\']',
         "high", "sql_injection", "Potential SQL injection via string formatting"),
        (r'(?i)eval\s*\(',
         "medium", "code_injection", "Use of eval() — potential code injection"),
        (r'(?i)pickle\.loads?\(',
         "medium", "deserialization", "Unsafe pickle deserialization"),
        (r'(?i)subprocess\.call\s*\(.*shell=True',
         "high", "shell_injection", "subprocess with shell=True — shell injection risk"),
        (r'(?i)os\.system\s*\(',
         "medium", "shell_injection", "os.system() — prefer subprocess"),
        (r'(?i)jwt\.decode\(.*verify.*=.*False',
         "high", "jwt_bypass", "JWT signature verification disabled"),
        (r'(?i)ssl.*verify.*=.*False',
         "medium", "ssl_bypass", "SSL certificate verification disabled"),
        (r'DEBUG\s*=\s*True',
         "low", "debug_enabled", "DEBUG mode enabled — disable in production"),
    ]

    MAX_FILES = 500

    # -----------------------------------------------------------------------

    def __init__(self, max_file_read_kb: int = 100) -> None:
        self._max_file_bytes = max_file_read_kb * 1024

    # ---- Public API --------------------------------------------------------

    def analyze_project(self, workspace_path: str) -> dict[str, Any]:
        """
        Synchronous entry-point (wraps async implementation).

        Automatically uses an existing event loop or creates one.
        """
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Inside an async context (FastAPI, etc.) — schedule coroutine
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(asyncio.run, self._analyze_async(workspace_path))
                    return future.result()
            else:
                return loop.run_until_complete(self._analyze_async(workspace_path))
        except RuntimeError:
            return asyncio.run(self._analyze_async(workspace_path))

    async def analyze_project_async(self, workspace_path: str) -> dict[str, Any]:
        """Async entry-point for callers already inside an event loop."""
        return await self._analyze_async(workspace_path)

    # ---- Core pipeline -----------------------------------------------------

    async def _analyze_async(self, workspace_path: str) -> dict[str, Any]:
        """Full async analysis pipeline."""
        logger.info(f"🔍 Analyzing project: {workspace_path}")
        root = Path(workspace_path)

        if not root.exists():
            logger.warning(f"⚠️  Path does not exist: {workspace_path}")
            return asdict(self._empty_structure(workspace_path))

        try:
            # Phase 1 – File discovery
            all_files = self._discover_files(root)
            logger.debug(f"📁 Discovered {len(all_files)} files")

            # Phase 2 – Parallel deep analysis
            file_infos: list[FileInfo] = await asyncio.gather(
                *[self._analyze_file_async(f, root) for f in all_files]
            )

            # Phase 3 – Framework + CI/Docker detection
            frameworks = await self._detect_frameworks_async(all_files, root)
            has_ci = self._detect_ci(root)
            has_docker = (root / "Dockerfile").exists() or (root / "docker-compose.yml").exists()

            # Phase 4 – Categorise
            categorised = self._categorise_files(file_infos)

            # Phase 5 – Dependencies
            python_deps = self._extract_python_deps(root)
            npm_deps = self._extract_npm_deps(root)

            # Phase 6 – Patterns
            patterns = self._detect_patterns(file_infos, frameworks, root)

            # Phase 7 – Import graph
            import_graph = self._build_import_graph(file_infos)

            # Phase 8 – Security findings
            security_findings = await self._scan_security_async(all_files, root)

            # Phase 9 – Metrics
            source_count = len(categorised["source"]) or 1
            test_count = len(categorised["test"])
            avg_complexity = (
                sum(f.complexity_score for f in file_infos) / len(file_infos)
                if file_infos else 0.0
            )
            has_type_hints = any(f.has_type_hints for f in file_infos if f.language == "python")

            structure = ProjectStructure(
                root_path=workspace_path,
                total_files=len(all_files),
                total_lines=sum(f.lines for f in file_infos),
                languages=self._count_languages(file_infos),
                frameworks=frameworks,
                patterns=patterns,
                entry_points=self._find_entry_points(file_infos),
                files=[asdict(f) for f in file_infos],
                directories=self._list_directories(root),
                source_files=categorised["source"],
                test_files=categorised["test"],
                config_files=categorised["config"],
                models=categorised["models"],
                routes=categorised["routes"],
                components=categorised["components"],
                services=categorised["services"],
                utils=categorised["utils"],
                python_dependencies=python_deps,
                npm_dependencies=npm_deps,
                import_graph=import_graph,
                tech_stack_summary=self._build_tech_summary(frameworks, python_deps, npm_deps),
                security_findings=[asdict(s) for s in security_findings],
                avg_complexity_score=round(avg_complexity, 2),
                test_coverage_ratio=round(test_count / source_count, 2),
                has_ci=has_ci,
                has_docker=has_docker,
                has_type_hints=has_type_hints,
            )

            logger.info(
                f"✅ Analysis complete — {structure.total_files} files, "
                f"{structure.total_lines} lines, {len(structure.frameworks)} frameworks, "
                f"{len(security_findings)} security findings"
            )
            return asdict(structure)

        except Exception:
            logger.exception("❌ Analysis pipeline failed")
            return asdict(self._empty_structure(workspace_path))

    # ---- File discovery ----------------------------------------------------

    def _discover_files(self, root: Path) -> list[Path]:
        files: list[Path] = []
        try:
            for item in root.rglob("*"):
                if any(part in self.IGNORE_DIRS for part in item.parts):
                    continue
                if item.is_file() and item.suffix in self.SUPPORTED_EXTENSIONS:
                    files.append(item)
                    if len(files) >= self.MAX_FILES:
                        logger.debug("File discovery capped at %d files", self.MAX_FILES)
                        break
        except PermissionError as exc:
            logger.warning("Permission error during file discovery: %s", exc)
        return files

    # ---- Per-file analysis -------------------------------------------------

    async def _analyze_file_async(self, file_path: Path, root: Path) -> FileInfo:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._analyze_file, file_path, root)

    def _analyze_file(self, file_path: Path, root: Path) -> FileInfo:
        """Deep single-file analysis (runs in thread pool)."""
        try:
            rel_path = str(file_path.relative_to(root))
            ext = file_path.suffix
            language = self.SUPPORTED_EXTENSIONS.get(ext, "unknown")
            size = file_path.stat().st_size
            lines = 0
            imports: list[str] = []
            exports: list[str] = []
            complexity = 0
            has_type_hints = False
            has_docstrings = False

            try:
                raw = file_path.read_bytes()[: self._max_file_bytes]
                content = raw.decode("utf-8", errors="ignore")
                lines = content.count("\n") + 1

                if language == "python":
                    imports = self._extract_python_imports(content)
                    exports = self._extract_python_exports(content)
                    complexity = self._estimate_python_complexity(content)
                    has_type_hints = self._has_python_type_hints(content)
                    has_docstrings = '"""' in content or "'''" in content
                elif language in ("javascript", "typescript"):
                    imports = self._extract_js_imports(content)
                    exports = self._extract_js_exports(content)
                    complexity = self._estimate_js_complexity(content)
            except Exception as exc:
                logger.debug("Error reading %s: %s", file_path, exc)

            name_lower = file_path.name.lower()
            is_test = bool(re.search(r"(test_|_test|\.test\.|\.spec\.)", name_lower))
            is_config = file_path.name in {
                "package.json", "requirements.txt", "setup.py", "pyproject.toml",
                "tsconfig.json", "vite.config.ts", "vite.config.js",
                "webpack.config.js", ".env.example", "Dockerfile",
                "docker-compose.yml", "fly.toml", "vercel.json",
                "pytest.ini", ".gitignore", "README.md", "Makefile",
                ".eslintrc.json", ".eslintrc.js", "babel.config.js",
            }
            is_entry_point = file_path.name in {
                "main.py", "app.py", "__main__.py", "index.js",
                "index.ts", "App.tsx", "App.jsx", "server.js",
                "index.tsx", "index.jsx", "wsgi.py", "asgi.py",
            }

            return FileInfo(
                path=rel_path,
                name=file_path.name,
                extension=ext,
                size=size,
                lines=lines,
                language=language,
                is_test=is_test,
                is_config=is_config,
                is_entry_point=is_entry_point,
                imports=imports[:30],
                exports=exports[:30],
                complexity_score=complexity,
                has_type_hints=has_type_hints,
                has_docstrings=has_docstrings,
            )
        except Exception as exc:
            logger.debug("Error analysing %s: %s", file_path, exc)
            return FileInfo(
                path=str(file_path),
                name=file_path.name,
                extension=file_path.suffix,
                size=0,
                lines=0,
                language="unknown",
            )

    # ---- Import/export extraction ------------------------------------------

    def _extract_python_imports(self, content: str) -> list[str]:
        pattern = re.compile(r"(?:^|\n)(?:from\s+([\w.]+)\s+import|import\s+([\w.,\s]+))")
        modules: set[str] = set()
        for m in pattern.finditer(content):
            raw = m.group(1) or m.group(2)
            if not raw:
                continue
            for pkg in raw.split(","):
                base = pkg.strip().split(".")[0]
                if base and not base.startswith("_"):
                    modules.add(base)
        return sorted(modules)

    def _extract_python_exports(self, content: str) -> list[str]:
        """Extract __all__ and top-level class/function names."""
        names: set[str] = set()
        all_match = re.search(r"__all__\s*=\s*\[([^\]]+)\]", content)
        if all_match:
            for item in re.findall(r"['\"](\w+)['\"]", all_match.group(1)):
                names.add(item)
        for m in re.finditer(r"^(?:class|def|async def)\s+(\w+)", content, re.MULTILINE):
            names.add(m.group(1))
        return sorted(names)

    def _extract_js_imports(self, content: str) -> list[str]:
        pattern = re.compile(r"""import\s+(?:[\w\s{},*]+\s+from\s+)?['"]([^'"]+)['"]""")
        pkgs: set[str] = set()
        for m in pattern.finditer(content):
            mod = m.group(1)
            if mod.startswith("."):
                continue
            parts = mod.split("/")
            pkg = f"{parts[0]}/{parts[1]}" if parts[0].startswith("@") and len(parts) > 1 else parts[0]
            pkgs.add(pkg)
        # Also catch require()
        for m in re.finditer(r"""require\s*\(\s*['"]([^'"./][^'"]*)['"]\s*\)""", content):
            pkgs.add(m.group(1).split("/")[0])
        return sorted(pkgs)

    def _extract_js_exports(self, content: str) -> list[str]:
        names: set[str] = set()
        for m in re.finditer(
            r"export\s+(?:default\s+)?(?:function|class|const|let|var|interface|type|enum)\s+(\w+)",
            content,
        ):
            names.add(m.group(1))
        for m in re.finditer(r"export\s*\{([^}]+)\}", content):
            for name in re.findall(r"\b(\w+)\b", m.group(1)):
                names.add(name)
        return sorted(names)

    # ---- Complexity estimation ---------------------------------------------

    def _estimate_python_complexity(self, content: str) -> int:
        """Lightweight McCabe-style estimate without executing code."""
        keywords = ("if ", "elif ", "for ", "while ", "except ", "with ",
                    "and ", "or ", " lambda ", "@")
        return sum(content.count(kw) for kw in keywords)

    def _estimate_js_complexity(self, content: str) -> int:
        keywords = ("if (", "else if (", "for (", "while (", "catch (",
                    "switch (", " && ", " || ", "? ", "=> ")
        return sum(content.count(kw) for kw in keywords)

    def _has_python_type_hints(self, content: str) -> bool:
        return bool(
            re.search(r"def \w+\([^)]*:\s*\w", content)
            or re.search(r"\)\s*->\s*\w", content)
            or re.search(r":\s*(?:str|int|float|bool|list|dict|Optional|Union|Any)\b", content)
        )

    # ---- Framework detection -----------------------------------------------

    async def _detect_frameworks_async(self, files: list[Path], root: Path) -> list[str]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._detect_frameworks, files, root)

    def _detect_frameworks(self, files: list[Path], root: Path) -> list[str]:
        detected: set[str] = set()
        sample = [f for f in files if f.suffix in (".py", ".js", ".jsx", ".ts", ".tsx")][:60]

        for fp in sample:
            try:
                content = fp.read_bytes()[:20_000].decode("utf-8", errors="ignore")
                for fw, indicators in self.FRAMEWORK_INDICATORS.items():
                    if any(ind in content for ind in indicators):
                        detected.add(fw)
            except Exception as exc:
                logger.debug("Framework scan error in %s: %s", fp, exc)

        # Package.json cross-check
        pkg = root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                all_deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}
                mapping = {
                    "react": "react", "next": "nextjs", "vue": "vue",
                    "express": "express", "@nestjs/core": "nestjs",
                    "vitest": "vitest", "jest": "jest",
                }
                for pkg_name, fw in mapping.items():
                    if pkg_name in all_deps:
                        detected.add(fw)
            except Exception:
                pass

        # pyproject.toml / requirements cross-check
        for dep_name, fw in [
            ("fastapi", "fastapi"), ("flask", "flask"), ("django", "django"),
            ("sqlalchemy", "sqlalchemy"), ("alembic", "alembic"),
            ("celery", "celery"), ("redis", "redis"), ("pydantic", "pydantic"),
            ("pytest", "pytest"),
        ]:
            req = root / "requirements.txt"
            if req.exists():
                try:
                    text = req.read_text(encoding="utf-8").lower()
                    if dep_name in text:
                        detected.add(fw)
                except Exception:
                    pass

        return sorted(detected)

    # ---- Security scan -----------------------------------------------------

    async def _scan_security_async(self, files: list[Path], root: Path) -> list[SecurityFinding]:
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, self._scan_security, files, root)

    def _scan_security(self, files: list[Path], root: Path) -> list[SecurityFinding]:
        findings: list[SecurityFinding] = []
        scannable = [f for f in files if f.suffix in (".py", ".js", ".ts", ".tsx", ".jsx")][:100]

        compiled = [(re.compile(p, re.IGNORECASE), sev, cat, desc)
                    for p, sev, cat, desc in self.SECURITY_PATTERNS]

        for fp in scannable:
            try:
                lines = fp.read_text(encoding="utf-8", errors="ignore").splitlines()
                for lineno, line in enumerate(lines, 1):
                    for pattern, severity, category, description in compiled:
                        if pattern.search(line):
                            findings.append(SecurityFinding(
                                file_path=str(fp.relative_to(root)),
                                line_number=lineno,
                                severity=severity,
                                category=category,
                                description=description,
                                snippet=line.strip()[:120],
                            ))
                            break  # one finding per line
            except Exception as exc:
                logger.debug("Security scan error in %s: %s", fp, exc)

        return findings

    # ---- CI/CD detection ---------------------------------------------------

    def _detect_ci(self, root: Path) -> bool:
        ci_paths = [
            root / ".github" / "workflows",
            root / ".gitlab-ci.yml",
            root / "Jenkinsfile",
            root / ".circleci" / "config.yml",
            root / ".travis.yml",
            root / "bitbucket-pipelines.yml",
        ]
        return any(p.exists() for p in ci_paths)

    # ---- Categorisation ----------------------------------------------------

    def _categorise_files(self, file_infos: list[FileInfo]) -> dict[str, list[str]]:
        cats: dict[str, list[str]] = {
            k: [] for k in ("source", "test", "config", "models", "routes",
                            "components", "services", "utils")
        }
        for fi in file_infos:
            pl = fi.path.lower()
            if fi.is_test:
                cats["test"].append(fi.path)
            elif fi.is_config:
                cats["config"].append(fi.path)
            elif fi.language in ("python", "javascript", "typescript"):
                cats["source"].append(fi.path)

            if not fi.is_test:
                if re.search(r"[\\/]model", pl):
                    cats["models"].append(fi.path)
                if re.search(r"[\\/](route|api|endpoint|controller|view)", pl):
                    cats["routes"].append(fi.path)
                if re.search(r"[\\/]component", pl):
                    cats["components"].append(fi.path)
                if re.search(r"[\\/]service", pl):
                    cats["services"].append(fi.path)
                if re.search(r"[\\/](util|helper|lib|common)", pl):
                    cats["utils"].append(fi.path)
        return cats

    # ---- Pattern detection -------------------------------------------------

    def _detect_patterns(
        self, file_infos: list[FileInfo], frameworks: list[str], root: Path
    ) -> list[str]:
        patterns: set[str] = set()
        paths = [f.path.lower() for f in file_infos]

        if any("model" in p for p in paths):
            patterns.add("has_data_models")
        if any(re.search(r"(route|api|endpoint)", p) for p in paths):
            patterns.add("has_api_layer")
        if any("service" in p for p in paths):
            patterns.add("service_layer_architecture")
        if any("test" in p for p in paths):
            patterns.add("has_test_suite")
        if any("migration" in p for p in paths):
            patterns.add("has_db_migrations")
        if any(fw in frameworks for fw in ("fastapi", "flask", "django", "express", "nestjs")):
            patterns.add("backend_api")
        if any(fw in frameworks for fw in ("react", "vue", "nextjs")):
            patterns.add("frontend_spa")
        if "nextjs" in frameworks:
            patterns.add("fullstack_nextjs")
        if any("component" in p for p in paths):
            patterns.add("component_based_ui")
        if any(fw in frameworks for fw in ("sqlalchemy", "prisma", "alembic")):
            patterns.add("orm_database")
        if "celery" in frameworks:
            patterns.add("async_task_queue")
        if "redis" in frameworks:
            patterns.add("caching_layer")
        if "tailwindcss" in frameworks:
            patterns.add("utility_first_css")
        if any(f.is_config for f in file_infos):
            patterns.add("well_configured")
        if self._detect_ci(root):
            patterns.add("has_ci_cd")
        if (root / "Dockerfile").exists():
            patterns.add("containerised")

        return sorted(patterns)

    # ---- Import graph ------------------------------------------------------

    def _build_import_graph(self, file_infos: list[FileInfo]) -> dict[str, list[str]]:
        return {
            fi.path: fi.imports
            for fi in file_infos[:150]
            if fi.imports
        }

    # ---- Entry points ------------------------------------------------------

    def _find_entry_points(self, file_infos: list[FileInfo]) -> list[str]:
        return [fi.path for fi in file_infos if fi.is_entry_point]

    # ---- Language counts ---------------------------------------------------

    def _count_languages(self, file_infos: list[FileInfo]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for fi in file_infos:
            counts[fi.language] = counts.get(fi.language, 0) + 1
        return dict(sorted(counts.items(), key=lambda x: x[1], reverse=True))

    # ---- Directory listing -------------------------------------------------

    def _list_directories(self, root: Path) -> list[str]:
        dirs: set[str] = set()
        try:
            for item in root.rglob("*"):
                if item.is_dir() and not any(ign in item.parts for ign in self.IGNORE_DIRS):
                    try:
                        if any(item.iterdir()):
                            dirs.add(str(item.relative_to(root)))
                    except PermissionError:
                        pass
        except Exception as exc:
            logger.debug("Directory listing error: %s", exc)
        return sorted(dirs)[:80]

    # ---- Dependency extraction ---------------------------------------------

    def _extract_python_deps(self, root: Path) -> list[str]:
        deps: set[str] = set()

        # requirements.txt
        req = root / "requirements.txt"
        if req.exists():
            try:
                for line in req.read_text(encoding="utf-8").splitlines():
                    line = line.strip()
                    if line and not line.startswith(("#", "-", "git+")):
                        pkg = re.split(r"[=<>!;\[]", line)[0].strip()
                        if pkg:
                            deps.add(pkg.lower())
            except Exception as exc:
                logger.debug("requirements.txt read error: %s", exc)

        # pyproject.toml
        ppt = root / "pyproject.toml"
        if ppt.exists():
            try:
                text = ppt.read_text(encoding="utf-8")
                for m in re.finditer(r'"([\w-]+)\s*(?:[>=<!][^"]*)?"\s*[,\]]', text):
                    deps.add(m.group(1).lower())
            except Exception:
                pass

        return sorted(deps)[:80]

    def _extract_npm_deps(self, root: Path) -> list[str]:
        deps: set[str] = set()
        pkg = root / "package.json"
        if pkg.exists():
            try:
                data = json.loads(pkg.read_text(encoding="utf-8"))
                deps.update(data.get("dependencies", {}).keys())
                deps.update(data.get("devDependencies", {}).keys())
            except Exception as exc:
                logger.debug("package.json read error: %s", exc)
        return sorted(deps)[:80]

    # ---- Tech summary -------------------------------------------------------

    def _build_tech_summary(
        self,
        frameworks: list[str],
        python_deps: list[str],
        npm_deps: list[str],
    ) -> str:
        parts: list[str] = []
        be = [f for f in frameworks if f in ("fastapi", "flask", "django", "express", "nestjs")]
        fe = [f for f in frameworks if f in ("react", "vue", "nextjs")]
        db = [f for f in frameworks if f in ("sqlalchemy", "prisma", "alembic")]
        cache = [f for f in frameworks if f in ("redis", "celery")]

        if be:
            parts.append(f"Backend: {', '.join(be)}")
        if fe:
            parts.append(f"Frontend: {', '.join(fe)}")
        if db:
            parts.append(f"Database ORM: {', '.join(db)}")
        if cache:
            parts.append(f"Queue/Cache: {', '.join(cache)}")
        if "tailwindcss" in frameworks:
            parts.append("Styling: Tailwind CSS")
        if python_deps:
            parts.append(f"Python packages: {len(python_deps)}")
        if npm_deps:
            parts.append(f"NPM packages: {len(npm_deps)}")

        return " | ".join(parts) or "Tech stack not detected"

    # ---- Empty fallback ----------------------------------------------------

    def _empty_structure(self, workspace_path: str) -> ProjectStructure:
        return ProjectStructure(
            root_path=workspace_path,
            total_files=0, total_lines=0,
            languages={}, frameworks=[], patterns=[],
            entry_points=[], files=[], directories=[],
            source_files=[], test_files=[], config_files=[],
            models=[], routes=[], components=[], services=[], utils=[],
            python_dependencies=[], npm_dependencies=[],
            import_graph={},
            tech_stack_summary="No project found",
        )
