"""Universal heuristics for cold start: known patterns for common frameworks.

Provides pre-built learnings that apply to any project using a given framework,
so Jarvis can offer useful advice even before it has seen any errors in this
specific project.

These heuristics encode hard-won operational knowledge:
- Jest retry patterns (flaky tests)
- Node.js memory tuning
- Python migration ordering
- Rust borrow checker common patterns
- Docker layer caching
- Git conflict resolution heuristics
"""

import logging
from typing import Any

from jarvis.memory import MemoryStore
from jarvis.self_learning import hash_error_pattern

logger = logging.getLogger(__name__)

# Each heuristic is a pre-built learning ready for injection
UNIVERSAL_HEURISTICS: list[dict[str, Any]] = [
    # --- JavaScript/Node.js ---
    {
        "language": "javascript",
        "error_pattern": "FATAL ERROR: Reached heap limit Allocation failed",
        "fix_description": "Increase Node.js heap size: NODE_OPTIONS='--max-old-space-size=4096'",
        "fix_diff": "+NODE_OPTIONS='--max-old-space-size=4096' node script.js",
        "confidence": 0.9,
        "tags": ["node", "memory", "heap"],
    },
    {
        "language": "javascript",
        "error_pattern": "Jest has detected the following 1 open handle potentially keeping Jest from exiting",
        "fix_description": "Add --forceExit or --detectOpenHandles flag to Jest, or close open DB/server connections in afterAll()",
        "fix_diff": "+jest --forceExit --detectOpenHandles",
        "confidence": 0.85,
        "tags": ["jest", "testing", "hanging"],
    },
    {
        "language": "javascript",
        "error_pattern": "ENOSPC: System limit for number of file watchers reached",
        "fix_description": "Increase inotify watchers: echo fs.inotify.max_user_watches=524288 | sudo tee -a /etc/sysctl.conf && sudo sysctl -p",
        "fix_diff": "+fs.inotify.max_user_watches=524288",
        "confidence": 0.95,
        "tags": ["node", "watcher", "linux"],
    },
    {
        "language": "javascript",
        "error_pattern": "ERR_REQUIRE_ESM: require() of ES Module",
        "fix_description": "Either add \"type\": \"module\" to package.json or use dynamic import() instead of require()",
        "fix_diff": '+  "type": "module"  // in package.json\n// OR use: const mod = await import("package")',
        "confidence": 0.9,
        "tags": ["esm", "commonjs", "module"],
    },
    # --- Python ---
    {
        "language": "python",
        "error_pattern": "ModuleNotFoundError: No module named",
        "fix_description": "Install the missing package: pip install <package> or add to requirements.txt/pyproject.toml",
        "fix_diff": "+pip install <missing_module>\n# OR add to pyproject.toml dependencies",
        "confidence": 0.85,
        "tags": ["python", "import", "deps"],
    },
    {
        "language": "python",
        "error_pattern": "django.db.utils.OperationalError: no such table",
        "fix_description": "Run migrations in correct order: python manage.py makemigrations && python manage.py migrate",
        "fix_diff": "+python manage.py makemigrations\n+python manage.py migrate",
        "confidence": 0.9,
        "tags": ["django", "migrations", "database"],
    },
    {
        "language": "python",
        "error_pattern": "RecursionError: maximum recursion depth exceeded",
        "fix_description": "Check for circular imports or infinite recursion. Use iterative approach or increase limit with sys.setrecursionlimit()",
        "fix_diff": "+import sys\n+sys.setrecursionlimit(3000)  # temporary; fix the recursion",
        "confidence": 0.75,
        "tags": ["python", "recursion"],
    },
    {
        "language": "python",
        "error_pattern": "alembic.util.exc.CommandError: Target database is not up to date",
        "fix_description": "Stamp the current revision first: alembic stamp head, then generate new migration",
        "fix_diff": "+alembic stamp head\n+alembic revision --autogenerate -m 'migration message'\n+alembic upgrade head",
        "confidence": 0.85,
        "tags": ["alembic", "migrations", "database"],
    },
    # --- Rust ---
    {
        "language": "rust",
        "error_pattern": "cannot borrow .* as mutable because it is also borrowed as immutable",
        "fix_description": "Clone the immutable borrow before the mutable borrow, or restructure to avoid overlapping borrows",
        "fix_diff": "+let val = data.clone();  // Clone before mutable borrow\n+do_something_mut(&mut data);",
        "confidence": 0.8,
        "tags": ["rust", "borrow-checker"],
    },
    {
        "language": "rust",
        "error_pattern": "the trait bound .* Send .* is not satisfied",
        "fix_description": "Wrap non-Send types in Arc<Mutex<T>> for thread-safe sharing, or use tokio::spawn_local for !Send futures",
        "fix_diff": "+use std::sync::{Arc, Mutex};\n+let shared = Arc::new(Mutex::new(value));",
        "confidence": 0.75,
        "tags": ["rust", "async", "send"],
    },
    # --- Go ---
    {
        "language": "go",
        "error_pattern": "fatal error: concurrent map writes",
        "fix_description": "Use sync.Mutex to protect map access, or use sync.Map for concurrent access",
        "fix_diff": "+var mu sync.Mutex\n+mu.Lock()\n+myMap[key] = value\n+mu.Unlock()",
        "confidence": 0.9,
        "tags": ["go", "concurrency", "map"],
    },
    # --- Docker ---
    {
        "language": "docker",
        "error_pattern": "no space left on device",
        "fix_description": "Clean Docker cache: docker system prune -a --volumes. Check disk usage with docker system df",
        "fix_diff": "+docker system prune -a --volumes\n+docker system df",
        "confidence": 0.9,
        "tags": ["docker", "disk", "cleanup"],
    },
    {
        "language": "docker",
        "error_pattern": "COPY failed: file not found in build context",
        "fix_description": "Check .dockerignore for excluded files, verify file path relative to Dockerfile context",
        "fix_diff": "# Ensure file is not in .dockerignore\n# Verify COPY path is relative to build context, not Dockerfile location",
        "confidence": 0.85,
        "tags": ["docker", "build", "context"],
    },
    # --- Git ---
    {
        "language": "git",
        "error_pattern": "error: Your local changes to the following files would be overwritten by merge",
        "fix_description": "Stash changes first: git stash, then pull, then apply: git stash pop",
        "fix_diff": "+git stash\n+git pull origin main\n+git stash pop",
        "confidence": 0.9,
        "tags": ["git", "merge", "stash"],
    },
    {
        "language": "git",
        "error_pattern": "fatal: refusing to merge unrelated histories",
        "fix_description": "Use --allow-unrelated-histories flag: git pull origin main --allow-unrelated-histories",
        "fix_diff": "+git pull origin main --allow-unrelated-histories",
        "confidence": 0.85,
        "tags": ["git", "merge", "history"],
    },
]


def seed_universal_heuristics(
    memory: MemoryStore,
    project_path: str,
    languages: list[str] | None = None,
) -> dict[str, Any]:
    """Seed a project's learnings with universal heuristics.

    Only adds heuristics for the specified languages (or all if None).
    Skips any heuristic that already exists in the database.

    Args:
        memory: MemoryStore instance
        project_path: Project path for scoping
        languages: Optional list of languages to seed (e.g., ["python", "javascript"])

    Returns:
        dict with seeding statistics
    """
    seeded = 0
    skipped = 0

    for heuristic in UNIVERSAL_HEURISTICS:
        lang = heuristic["language"]
        if languages and lang not in languages:
            skipped += 1
            continue

        error_hash = hash_error_pattern(heuristic["error_pattern"])

        # Check if already exists
        existing = memory.get_learnings(
            project_path=project_path,
            error_pattern_hash=error_hash,
            min_confidence=0.0,
        )
        if existing:
            skipped += 1
            continue

        memory.save_learning(
            project_path=project_path,
            language=lang,
            error_pattern_hash=error_hash,
            error_message=heuristic["error_pattern"],
            fix_description=heuristic["fix_description"],
            fix_diff=heuristic["fix_diff"],
            confidence=heuristic["confidence"],
        )
        seeded += 1

    logger.info(f"Seeded {seeded} universal heuristics for {project_path} (skipped {skipped})")
    return {"seeded": seeded, "skipped": skipped, "total_available": len(UNIVERSAL_HEURISTICS)}


def detect_project_languages(project_path: str) -> list[str]:
    """Auto-detect project languages from files and config.

    Returns list of detected language identifiers.
    """
    from pathlib import Path

    project = Path(project_path)
    languages = set()

    # Check config files
    if (project / "package.json").exists():
        languages.add("javascript")
    if (project / "tsconfig.json").exists():
        languages.add("javascript")
    if (project / "requirements.txt").exists() or (project / "pyproject.toml").exists():
        languages.add("python")
    if (project / "setup.py").exists():
        languages.add("python")
    if (project / "Cargo.toml").exists():
        languages.add("rust")
    if (project / "go.mod").exists():
        languages.add("go")
    if (project / "Dockerfile").exists() or (project / "docker-compose.yml").exists():
        languages.add("docker")

    # Always include git heuristics
    if (project / ".git").exists():
        languages.add("git")

    # Scan for source files if no config files found
    if not languages:
        ext_map = {
            ".py": "python", ".js": "javascript", ".ts": "javascript",
            ".rs": "rust", ".go": "go", ".java": "java", ".swift": "swift",
        }
        for ext, lang in ext_map.items():
            if list(project.rglob(f"*{ext}"))[:1]:
                languages.add(lang)

    return sorted(languages)


async def auto_seed_project(memory: MemoryStore, project_path: str) -> dict[str, Any]:
    """Auto-detect project languages and seed universal heuristics.

    Called on first task for a new project or during idle mode.
    """
    languages = detect_project_languages(project_path)
    if not languages:
        return {"seeded": 0, "skipped": 0, "languages": [], "total_available": 0}

    result = seed_universal_heuristics(memory, project_path, languages)
    result["languages"] = languages
    return result
