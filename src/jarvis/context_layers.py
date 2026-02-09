"""Context layers: hierarchical metadata representation of a codebase.

Six layers of context (PRD §6.3):
  L1: Repo Structure - language, framework, file tree
  L2: Module Graph - package dependencies, import flow
  L3: Interface Signatures - function/class signatures (no implementations)
  L4: Test & Quality - test coverage, failure patterns, quality metrics
  L5: Learned Corrections - per-repo quirks (populated by self_learning.py)
  L6: Runtime State - git status, container state (populated by orchestrator)

This module implements L1-L4 (static analysis layers).
L5-L6 are populated by other modules at runtime.
"""

import ast
import json
import logging
import os
import re
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# ---- L1: Repo Structure ----

def build_l1_repo_structure(project_path: str) -> dict[str, Any]:
    """Build L1 context: repo structure analysis.

    Detects language, framework, file tree, and project conventions.
    """
    root = Path(project_path)
    result: dict[str, Any] = {
        "layer": "L1",
        "project_path": project_path,
        "languages": [],
        "frameworks": [],
        "package_manager": None,
        "test_runner": None,
        "file_counts": {},
        "entry_points": [],
        "config_files": [],
    }

    # Count files by extension
    ext_counts: dict[str, int] = {}
    total_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Skip irrelevant directories
        dirnames[:] = [
            d for d in dirnames
            if d not in {".git", "node_modules", "__pycache__", ".venv",
                         "venv", "dist", "build", ".build", "target",
                         ".next", "coverage", ".tox"}
        ]
        for f in filenames:
            ext = Path(f).suffix.lower()
            if ext:
                ext_counts[ext] = ext_counts.get(ext, 0) + 1
                total_files += 1

    result["file_counts"] = ext_counts
    result["total_files"] = total_files

    # Detect languages
    lang_map = {
        ".py": "python", ".js": "javascript", ".ts": "typescript",
        ".jsx": "javascript", ".tsx": "typescript", ".rs": "rust",
        ".go": "go", ".java": "java", ".swift": "swift",
        ".rb": "ruby", ".php": "php", ".c": "c", ".cpp": "cpp",
    }
    detected_langs = set()
    for ext, lang in lang_map.items():
        if ext in ext_counts:
            detected_langs.add(lang)
    result["languages"] = sorted(detected_langs)

    # Detect frameworks and package managers
    config_markers = {
        "package.json": ("javascript", "npm"),
        "pyproject.toml": ("python", "pip"),
        "requirements.txt": ("python", "pip"),
        "Cargo.toml": ("rust", "cargo"),
        "go.mod": ("go", "go"),
        "Gemfile": ("ruby", "bundler"),
        "pom.xml": ("java", "maven"),
        "build.gradle": ("java", "gradle"),
        "Package.swift": ("swift", "spm"),
    }

    for marker, (lang, pkg_mgr) in config_markers.items():
        if (root / marker).exists():
            result["config_files"].append(marker)
            if not result["package_manager"]:
                result["package_manager"] = pkg_mgr

    # Refine package manager
    if (root / "pnpm-lock.yaml").exists():
        result["package_manager"] = "pnpm"
    elif (root / "yarn.lock").exists():
        result["package_manager"] = "yarn"
    elif (root / "bun.lockb").exists():
        result["package_manager"] = "bun"
    elif (root / "uv.lock").exists():
        result["package_manager"] = "uv"

    # Detect frameworks
    framework_markers = {
        "next.config": "Next.js",
        "nuxt.config": "Nuxt",
        "angular.json": "Angular",
        "vite.config": "Vite",
        "webpack.config": "Webpack",
        "tsconfig.json": "TypeScript",
    }
    for marker, framework in framework_markers.items():
        for f in os.listdir(root):
            if f.startswith(marker):
                result["frameworks"].append(framework)
                break

    # Check package.json for framework dependencies
    pkg_json = root / "package.json"
    if pkg_json.exists():
        try:
            pkg = json.loads(pkg_json.read_text())
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
            fw_deps = {
                "react": "React", "vue": "Vue", "svelte": "Svelte",
                "express": "Express", "fastify": "Fastify", "koa": "Koa",
                "next": "Next.js", "nuxt": "Nuxt",
            }
            for dep, fw in fw_deps.items():
                if dep in deps and fw not in result["frameworks"]:
                    result["frameworks"].append(fw)
        except (json.JSONDecodeError, OSError):
            pass

    # Check pyproject.toml for Python frameworks
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            py_fw = {
                "flask": "Flask", "django": "Django", "fastapi": "FastAPI",
                "starlette": "Starlette", "pytest": "pytest",
            }
            for dep, fw in py_fw.items():
                if dep in content.lower() and fw not in result["frameworks"]:
                    result["frameworks"].append(fw)
            if "pytest" in content:
                result["test_runner"] = "pytest"
        except OSError:
            pass

    # Detect test runner
    if not result["test_runner"]:
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                test_cmd = pkg.get("scripts", {}).get("test", "")
                if "vitest" in test_cmd:
                    result["test_runner"] = "vitest"
                elif "jest" in test_cmd:
                    result["test_runner"] = "jest"
                elif "mocha" in test_cmd:
                    result["test_runner"] = "mocha"
            except (json.JSONDecodeError, OSError):
                pass

    # Detect entry points
    entry_candidates = [
        "src/main.py", "src/app.py", "main.py", "app.py",
        "src/index.ts", "src/index.js", "index.ts", "index.js",
        "src/main.rs", "main.go", "cmd/main.go",
    ]
    for entry in entry_candidates:
        if (root / entry).exists():
            result["entry_points"].append(entry)

    return result


# ---- L2: Module Graph ----

def build_l2_module_graph(project_path: str) -> dict[str, Any]:
    """Build L2 context: module dependency graph.

    Analyzes imports to build a dependency graph between modules.
    Currently supports Python files.
    """
    root = Path(project_path)
    result: dict[str, Any] = {
        "layer": "L2",
        "modules": {},
        "import_edges": [],
        "external_deps": set(),
    }

    py_files = list(root.rglob("*.py"))
    # Filter out venv/build directories
    py_files = [
        f for f in py_files
        if not any(
            part in f.parts
            for part in {"venv", ".venv", "node_modules", ".git", "__pycache__",
                         "dist", "build", ".tox"}
        )
    ]

    for py_file in py_files:
        try:
            rel_path = str(py_file.relative_to(root))
            module_name = rel_path.replace("/", ".").replace(".py", "")
            if module_name.endswith(".__init__"):
                module_name = module_name[:-9]

            source = py_file.read_text(errors="ignore")
            tree = ast.parse(source, filename=str(py_file))

            imports = []
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        imports.append(node.module)

            # Classify imports
            internal_imports = []
            external_imports = []
            for imp in imports:
                # Check if import is internal to this project
                imp_path = root / imp.replace(".", "/")
                if (imp_path.with_suffix(".py").exists() or
                        (imp_path / "__init__.py").exists()):
                    internal_imports.append(imp)
                    result["import_edges"].append({
                        "from": module_name,
                        "to": imp,
                    })
                else:
                    external_imports.append(imp)
                    result["external_deps"].add(imp.split(".")[0])

            result["modules"][module_name] = {
                "file": rel_path,
                "internal_imports": internal_imports,
                "external_imports": external_imports,
                "lines": len(source.splitlines()),
            }

        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    # Convert set to list for serialization
    result["external_deps"] = sorted(result["external_deps"])
    return result


# ---- L3: Interface Signatures ----

def build_l3_signatures(project_path: str) -> dict[str, Any]:
    """Build L3 context: function and class signatures.

    Extracts public interfaces without implementation bodies.
    Currently supports Python files.
    """
    root = Path(project_path)
    result: dict[str, Any] = {
        "layer": "L3",
        "classes": [],
        "functions": [],
        "total_signatures": 0,
    }

    py_files = list(root.rglob("*.py"))
    py_files = [
        f for f in py_files
        if not any(
            part in f.parts
            for part in {"venv", ".venv", "node_modules", ".git", "__pycache__",
                         "dist", "build", ".tox"}
        )
    ]

    for py_file in py_files:
        try:
            rel_path = str(py_file.relative_to(root))
            source = py_file.read_text(errors="ignore")
            tree = ast.parse(source, filename=str(py_file))

            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    # Skip private classes
                    if node.name.startswith("_") and not node.name.startswith("__"):
                        continue

                    bases = []
                    for base in node.bases:
                        if isinstance(base, ast.Name):
                            bases.append(base.id)
                        elif isinstance(base, ast.Attribute):
                            bases.append(ast.dump(base))

                    methods = []
                    for item in node.body:
                        if isinstance(item, ast.FunctionDef):
                            if item.name.startswith("_") and not item.name.startswith("__"):
                                continue
                            sig = _extract_function_signature(item)
                            methods.append(sig)

                    class_info = {
                        "name": node.name,
                        "file": rel_path,
                        "line": node.lineno,
                        "bases": bases,
                        "methods": methods,
                        "docstring": ast.get_docstring(node) or "",
                    }
                    result["classes"].append(class_info)
                    result["total_signatures"] += 1 + len(methods)

                elif isinstance(node, ast.FunctionDef):
                    # Only top-level functions (not methods)
                    if node.col_offset == 0:
                        if node.name.startswith("_") and not node.name.startswith("__"):
                            continue
                        sig = _extract_function_signature(node)
                        sig["file"] = rel_path
                        result["functions"].append(sig)
                        result["total_signatures"] += 1

        except (SyntaxError, OSError, UnicodeDecodeError):
            continue

    return result


def _extract_function_signature(node: ast.FunctionDef) -> dict[str, Any]:
    """Extract a function signature from an AST node."""
    args = []
    for arg in node.args.args:
        arg_info: dict[str, Any] = {"name": arg.arg}
        if arg.annotation:
            try:
                arg_info["type"] = ast.unparse(arg.annotation)
            except (AttributeError, ValueError):
                pass
        args.append(arg_info)

    return_type = None
    if node.returns:
        try:
            return_type = ast.unparse(node.returns)
        except (AttributeError, ValueError):
            pass

    return {
        "name": node.name,
        "line": node.lineno,
        "args": args,
        "return_type": return_type,
        "docstring": ast.get_docstring(node) or "",
        "is_async": isinstance(node, ast.AsyncFunctionDef),
    }


# ---- L4: Test & Quality ----

def build_l4_test_quality(project_path: str) -> dict[str, Any]:
    """Build L4 context: test coverage and quality metrics.

    Scans for test files and extracts test structure.
    """
    root = Path(project_path)
    result: dict[str, Any] = {
        "layer": "L4",
        "test_files": [],
        "test_count": 0,
        "test_frameworks": [],
        "quality_config": {},
    }

    # Find test files
    test_patterns = [
        "test_*.py", "*_test.py", "*.test.js", "*.test.ts",
        "*.spec.js", "*.spec.ts", "*.test.jsx", "*.test.tsx",
    ]

    test_dirs = ["tests", "test", "spec", "__tests__", "src/tests"]

    for pattern in test_patterns:
        for test_file in root.rglob(pattern):
            if any(part in test_file.parts for part in {
                "node_modules", ".venv", "venv", ".git"
            }):
                continue

            rel_path = str(test_file.relative_to(root))
            test_info = {
                "file": rel_path,
                "test_names": [],
            }

            try:
                content = test_file.read_text(errors="ignore")

                # Python: extract test function names
                if test_file.suffix == ".py":
                    for match in re.finditer(r"def (test_\w+)", content):
                        test_info["test_names"].append(match.group(1))
                    if "pytest" not in result["test_frameworks"]:
                        if "import pytest" in content or "from pytest" in content:
                            result["test_frameworks"].append("pytest")

                # JavaScript/TypeScript: extract test names
                elif test_file.suffix in (".js", ".ts", ".jsx", ".tsx"):
                    for match in re.finditer(
                        r'(?:it|test)\s*\(\s*[\'"](.+?)[\'"]', content
                    ):
                        test_info["test_names"].append(match.group(1))
                    for match in re.finditer(
                        r'describe\s*\(\s*[\'"](.+?)[\'"]', content
                    ):
                        test_info["test_names"].append(f"describe: {match.group(1)}")
            except OSError:
                continue

            result["test_count"] += len(test_info["test_names"])
            result["test_files"].append(test_info)

    # Detect quality tools
    quality_configs = {
        ".eslintrc": "eslint", ".eslintrc.json": "eslint", ".eslintrc.js": "eslint",
        "eslint.config.js": "eslint", "eslint.config.mjs": "eslint",
        ".prettierrc": "prettier", ".prettierrc.json": "prettier",
        "ruff.toml": "ruff", ".flake8": "flake8",
        "mypy.ini": "mypy", ".mypy.ini": "mypy",
        "tox.ini": "tox", ".coveragerc": "coverage",
        "jest.config.js": "jest", "jest.config.ts": "jest",
        "vitest.config.ts": "vitest", "vitest.config.js": "vitest",
    }

    for config_file, tool in quality_configs.items():
        if (root / config_file).exists():
            result["quality_config"][tool] = config_file

    # Check pyproject.toml for tool configs
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text()
            if "[tool.ruff]" in content:
                result["quality_config"]["ruff"] = "pyproject.toml"
            if "[tool.mypy]" in content:
                result["quality_config"]["mypy"] = "pyproject.toml"
            if "[tool.pytest]" in content:
                result["quality_config"]["pytest"] = "pyproject.toml"
        except OSError:
            pass

    return result


# ---- Combined Builder ----

async def build_context_layers(
    project_path: str,
    layers: list[str] | None = None,
) -> dict[str, Any]:
    """Build all requested context layers for a project.

    Args:
        project_path: Path to the project
        layers: Which layers to build (default: all L1-L4)

    Returns:
        Dict with layer results keyed by layer name.
    """
    if layers is None:
        layers = ["L1", "L2", "L3", "L4"]

    result: dict[str, Any] = {}

    if "L1" in layers:
        result["L1"] = build_l1_repo_structure(project_path)
        logger.info(f"L1: {len(result['L1'].get('languages', []))} languages detected")

    if "L2" in layers:
        result["L2"] = build_l2_module_graph(project_path)
        logger.info(f"L2: {len(result['L2'].get('modules', {}))} modules mapped")

    if "L3" in layers:
        result["L3"] = build_l3_signatures(project_path)
        logger.info(f"L3: {result['L3'].get('total_signatures', 0)} signatures extracted")

    if "L4" in layers:
        result["L4"] = build_l4_test_quality(project_path)
        logger.info(f"L4: {result['L4'].get('test_count', 0)} tests found")

    return result


def format_context_for_prompt(layers: dict[str, Any], max_length: int = 4000) -> str:
    """Format context layers for injection into agent system prompt.

    Produces a concise summary suitable for LLM context.
    """
    parts = []

    l1 = layers.get("L1")
    if l1:
        langs = ", ".join(l1.get("languages", []))
        fws = ", ".join(l1.get("frameworks", []))
        parts.append(f"**Languages**: {langs}")
        if fws:
            parts.append(f"**Frameworks**: {fws}")
        if l1.get("package_manager"):
            parts.append(f"**Package Manager**: {l1['package_manager']}")
        if l1.get("test_runner"):
            parts.append(f"**Test Runner**: {l1['test_runner']}")
        if l1.get("entry_points"):
            parts.append(f"**Entry Points**: {', '.join(l1['entry_points'])}")

    l2 = layers.get("L2")
    if l2 and l2.get("modules"):
        module_count = len(l2["modules"])
        ext_deps = l2.get("external_deps", [])
        parts.append(f"**Modules**: {module_count} internal modules")
        if ext_deps:
            parts.append(f"**External Deps**: {', '.join(ext_deps[:15])}")

    l3 = layers.get("L3")
    if l3:
        parts.append(
            f"**Interfaces**: {len(l3.get('classes', []))} classes, "
            f"{len(l3.get('functions', []))} functions"
        )
        # Include key class names
        class_names = [c["name"] for c in l3.get("classes", [])[:10]]
        if class_names:
            parts.append(f"**Key Classes**: {', '.join(class_names)}")

    l4 = layers.get("L4")
    if l4:
        parts.append(f"**Tests**: {l4.get('test_count', 0)} tests in {len(l4.get('test_files', []))} files")
        if l4.get("quality_config"):
            tools = ", ".join(l4["quality_config"].keys())
            parts.append(f"**Quality Tools**: {tools}")

    text = "\n".join(parts)
    if len(text) > max_length:
        text = text[:max_length - 3] + "..."

    return text
