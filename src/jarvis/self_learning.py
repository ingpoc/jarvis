"""Self-learning system: extract patterns from execution records and save as learnings.

The learning loop:
1. On error: Hash error message, check learnings table for known pattern
2. On fix: Calculate file diffs, save as new learning with confidence=0.7
3. Flag as skill_candidate if pattern count >= 3

This module implements the core learning logic for Jarvis to improve over time.
"""

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from jarvis.memory import MemoryStore


def hash_error_pattern(error_message: str) -> str:
    """Generate a stable hash for an error pattern.

    Normalizes error messages by removing variable parts like:
    - Line numbers
    - File paths (keeps only filename)
    - Timestamps
    - Memory addresses
    - Variable names in some cases
    """
    # Normalize error message
    normalized = error_message.lower()

    # Remove line numbers
    normalized = re.sub(r'line \d+', 'line N', normalized)
    normalized = re.sub(r':\d+:', ':N:', normalized)

    # Remove file paths, keep only filenames
    normalized = re.sub(r'/[\w/.-]+/(\w+\.\w+)', r'\1', normalized)
    normalized = re.sub(r'[a-z]:\\[\w\\.-]+\\(\w+\.\w+)', r'\1', normalized)

    # Remove timestamps
    normalized = re.sub(r'\d{4}-\d{2}-\d{2}', 'DATE', normalized)
    normalized = re.sub(r'\d{2}:\d{2}:\d{2}', 'TIME', normalized)

    # Remove memory addresses
    normalized = re.sub(r'0x[0-9a-f]+', '0xADDR', normalized)

    # Remove numbers in general (but keep error codes that might be specific)
    # normalized = re.sub(r'\b\d+\b', 'N', normalized)

    # Generate hash
    return hashlib.sha256(normalized.encode()).hexdigest()[:16]


def extract_error_from_execution(execution_record: dict) -> str | None:
    """Extract error message from an execution record."""
    if execution_record.get("error_message"):
        return execution_record["error_message"]

    # Check tool output for errors
    output = execution_record.get("tool_output", "")
    if isinstance(output, str):
        # Common error patterns
        error_patterns = [
            r'error:(.+?)(?:\n|$)',
            r'exception:(.+?)(?:\n|$)',
            r'failed:(.+?)(?:\n|$)',
            r'traceback[^\n]*\n(.+?)(?:\n\n|$)',
        ]
        for pattern in error_patterns:
            match = re.search(pattern, output, re.IGNORECASE | re.DOTALL)
            if match:
                return match.group(1).strip()[:500]  # Limit length

    # Check exit code
    if execution_record.get("exit_code", 0) != 0:
        return f"Command failed with exit code {execution_record['exit_code']}"

    return None


def detect_language(project_path: str, files_touched: list[str]) -> str:
    """Detect programming language from files touched."""
    if not files_touched:
        # Fallback: check project structure
        project = Path(project_path)
        if (project / "package.json").exists():
            return "javascript"
        if (project / "requirements.txt").exists() or (project / "pyproject.toml").exists():
            return "python"
        if (project / "Cargo.toml").exists():
            return "rust"
        if (project / "go.mod").exists():
            return "go"
        return "unknown"

    # Check file extensions
    extensions = {Path(f).suffix for f in files_touched}
    if '.py' in extensions:
        return "python"
    if '.js' in extensions or '.ts' in extensions or '.jsx' in extensions or '.tsx' in extensions:
        return "javascript"
    if '.rs' in extensions:
        return "rust"
    if '.go' in extensions:
        return "go"
    if '.java' in extensions:
        return "java"
    if '.swift' in extensions:
        return "swift"

    return "unknown"


def extract_fix_description(execution_records: list[dict]) -> str:
    """Extract fix description from a sequence of execution records.

    Looks for Edit/Write tool calls that happened after an error.
    """
    fixes = []
    for record in execution_records:
        tool_name = record.get("tool_name", "")
        if tool_name in ["Edit", "Write", "mcp__jarvis-git__git_commit"]:
            tool_input = record.get("tool_input", {})
            if isinstance(tool_input, dict):
                if "old_string" in tool_input and "new_string" in tool_input:
                    fixes.append(f"Changed '{tool_input['old_string'][:50]}...' to '{tool_input['new_string'][:50]}...'")
                elif "content" in tool_input:
                    fixes.append(f"Wrote content to file")
                elif "message" in tool_input:
                    fixes.append(f"Committed: {tool_input['message']}")

    return "; ".join(fixes) if fixes else "Applied fix"


def calculate_fix_diff(execution_records: list[dict]) -> str:
    """Calculate the diff representing the fix.

    Extracts Edit/Write operations that represent the fix.
    """
    diffs = []
    for record in execution_records:
        tool_name = record.get("tool_name", "")
        if tool_name == "Edit":
            tool_input = record.get("tool_input", {})
            if isinstance(tool_input, dict):
                old = tool_input.get("old_string", "")
                new = tool_input.get("new_string", "")
                diffs.append(f"--- old\n+++ new\n-{old}\n+{new}")
        elif tool_name == "Write":
            tool_input = record.get("tool_input", {})
            if isinstance(tool_input, dict):
                content = tool_input.get("content", "")
                diffs.append(f"+++ new file\n{content[:500]}")

    return "\n\n".join(diffs) if diffs else "No diff captured"


async def learn_from_task(
    task_id: str,
    project_path: str,
    memory: MemoryStore,
) -> dict[str, Any]:
    """Analyze a completed task and extract learnings.

    Returns:
        dict with learning statistics (errors_found, learnings_saved, skills_flagged)
    """
    # Get execution records for this task
    records = memory.get_execution_records(task_id=task_id)

    if not records:
        return {"errors_found": 0, "learnings_saved": 0, "skills_flagged": 0}

    errors_found = 0
    learnings_saved = 0
    skills_flagged = 0

    # Scan for error→fix sequences.
    # An error sequence starts at the first error record and continues until we
    # see a successful "resolution" tool call (Edit/Write/Bash with exit_code 0).
    # Intermediate non-error records (e.g., Read calls used to investigate) are
    # included in the sequence so the full context is preserved.
    FIX_TOOLS = {"Edit", "Write", "Bash", "mcp__jarvis-git__git_commit"}
    error_sequences = []
    current_sequence: list[dict] = []
    in_error = False

    for record in records:
        error = extract_error_from_execution(record)
        if error:
            if not in_error:
                # Start of new error sequence
                current_sequence = [record]
                in_error = True
            else:
                current_sequence.append(record)
            errors_found += 1
        elif in_error:
            # Non-error record while in an error sequence — could be
            # investigation (Read/Grep) or the actual fix (Edit/Write/Bash).
            current_sequence.append(record)
            # Only close the sequence when we see a successful fix tool
            tool_name = record.get("tool_name", "")
            if record.get("exit_code", -1) == 0 and tool_name in FIX_TOOLS:
                error_sequences.append(current_sequence)
                current_sequence = []
                in_error = False

    # Process error-fix sequences to create learnings
    for sequence in error_sequences:
        if len(sequence) < 2:
            continue  # Need at least error + fix

        # Extract error from first record
        error_record = sequence[0]
        error_message = extract_error_from_execution(error_record)
        if not error_message:
            continue

        # Generate error pattern hash
        error_hash = hash_error_pattern(error_message)

        # Check if we already have this learning
        existing = memory.get_learnings(
            project_path=project_path,
            error_pattern_hash=error_hash,
        )

        # Extract fix information
        fix_records = sequence[1:]
        fix_description = extract_fix_description(fix_records)
        fix_diff = calculate_fix_diff(fix_records)

        # Detect language
        files_touched = []
        for record in sequence:
            if record.get("files_touched"):
                files_touched.extend(record["files_touched"])
        language = detect_language(project_path, files_touched)

        # Save learning
        learning_id = memory.save_learning(
            project_path=project_path,
            language=language,
            error_pattern_hash=error_hash,
            error_message=error_message[:500],
            fix_description=fix_description[:500],
            fix_diff=fix_diff[:2000],
            confidence=0.7,
        )
        learnings_saved += 1

        # Check if we should flag as skill candidate
        if existing and existing[0]["occurrence_count"] >= 2:
            # This is the 3rd+ occurrence - flag for skill generation
            pattern_desc = f"Fix for: {error_message[:100]}"
            pattern_hash = hashlib.sha256(pattern_desc.encode()).hexdigest()[:16]

            memory.record_skill_candidate(
                pattern_hash=pattern_hash,
                pattern_description=pattern_desc,
                example_task=task_id,
                project_path=project_path,
            )
            skills_flagged += 1

    return {
        "errors_found": errors_found,
        "learnings_saved": learnings_saved,
        "skills_flagged": skills_flagged,
        "error_sequences": len(error_sequences),
    }


def get_relevant_learnings(
    project_path: str,
    error_message: str,
    memory: MemoryStore,
) -> list[dict]:
    """Retrieve relevant learnings for a given error message.

    Returns matching learnings sorted by confidence.
    """
    error_hash = hash_error_pattern(error_message)

    # Exact match by hash
    learnings = memory.get_learnings(
        project_path=project_path,
        error_pattern_hash=error_hash,
        min_confidence=0.5,
    )

    return learnings


def format_learning_for_context(learning: dict) -> str:
    """Format a learning for injection into agent context.

    Returns a formatted string suitable for system prompt.
    """
    return f"""
## Known Error Pattern (Confidence: {learning['confidence']:.1f}, Seen {learning['occurrence_count']}x)

**Error**: {learning['error_message'][:200]}

**Fix**: {learning['fix_description']}

**Diff**:
```
{learning['fix_diff'][:500]}
```
"""
