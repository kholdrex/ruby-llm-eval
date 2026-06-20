"""Discover and load benchmark tasks from a tasks directory.

A task is a directory named like ``001_fizzbuzz`` containing:

    prompt.md        the problem description + exact Ruby signature to implement
    test.rb          a Minitest suite, OR
    spec.rb          an RSpec suite (use exactly one of test.rb / spec.rb)
    solution_ref.rb  a reference solution (never shown to the model)

Both test frameworks ``require_relative "solution"``. This is the entire
contribution surface — adding a task means adding a folder; there is no
registry to edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROMPT_FILE = "prompt.md"
REFERENCE_FILE = "solution_ref.rb"

# Map each supported framework to the test filename that selects it.
TEST_FILES = {"minitest": "test.rb", "rspec": "spec.rb"}


@dataclass(frozen=True)
class Task:
    """A single benchmark task loaded from disk."""

    id: str
    path: Path
    prompt: str
    framework: str  # "minitest" or "rspec"
    test_filename: str  # "test.rb" or "spec.rb"
    test: str

    def reference(self) -> str:
        """Read the reference solution. Used to self-test tasks and the stub."""
        return (self.path / REFERENCE_FILE).read_text(encoding="utf-8")


def _read_required(task_dir: Path, filename: str) -> str:
    try:
        return (task_dir / filename).read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Task '{task_dir.name}' required file {filename} must be UTF-8 text "
            f"(invalid byte at offset {exc.start})."
        ) from None


def _detect_framework(task_dir: Path) -> tuple[str, str]:
    """Return (framework, test_filename) for a task, requiring exactly one."""
    present = [(fw, fn) for fw, fn in TEST_FILES.items() if (task_dir / fn).is_file()]
    options = " / ".join(TEST_FILES.values())
    if not present:
        raise ValueError(f"Task '{task_dir.name}' has no test file (expected one of: {options}).")
    if len(present) > 1:
        raise ValueError(
            f"Task '{task_dir.name}' has multiple test files; include exactly one of {options}."
        )
    return present[0]


def load_task(task_dir: Path) -> Task:
    """Load a task directory, validating required files exist and are non-empty."""
    if not (task_dir / PROMPT_FILE).is_file():
        raise ValueError(f"Task '{task_dir.name}' is missing {PROMPT_FILE}.")
    if not (task_dir / REFERENCE_FILE).is_file():
        raise ValueError(f"Task '{task_dir.name}' is missing {REFERENCE_FILE}.")

    framework, test_filename = _detect_framework(task_dir)

    required = (PROMPT_FILE, REFERENCE_FILE, test_filename)
    contents = {name: _read_required(task_dir, name) for name in required}
    empty = [name for name, content in contents.items() if not content.strip()]
    if empty:
        raise ValueError(f"Task '{task_dir.name}' has empty required file(s): {', '.join(empty)}")

    return Task(
        id=task_dir.name,
        path=task_dir,
        prompt=contents[PROMPT_FILE],
        framework=framework,
        test_filename=test_filename,
        test=contents[test_filename],
    )


def _format_invalid_selected_task_id(task_id: str) -> str:
    if task_id == "":
        return "<empty>"
    if not task_id.strip():
        return "<blank>"
    return task_id


def _invalid_selected_task_ids(task_ids: list[str]) -> list[str]:
    invalid: list[str] = []
    seen: set[str] = set()
    for task_id in task_ids:
        if (
            not task_id.strip()
            or task_id != task_id.strip()
            or task_id in {".", ".."}
            or "/" in task_id
            or "\\" in task_id
        ):
            label = _format_invalid_selected_task_id(task_id)
            if label not in seen:
                invalid.append(label)
                seen.add(label)
    return invalid


def discover_tasks(tasks_dir: Path, only: list[str] | None = None) -> list[Task]:
    """Load every task in ``tasks_dir``, sorted by id for deterministic runs.

    By default, a directory is treated as a task if it contains a ``prompt.md``.
    The optional ``only`` list filters to exact task ids and validates matching
    directories even when they are malformed, so selected private tasks get
    actionable file-level diagnostics.
    """
    if not tasks_dir.is_dir():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    if only:
        invalid = _invalid_selected_task_ids(only)
        if invalid:
            raise ValueError(
                f"Invalid selected task id(s): {', '.join(invalid)}. "
                "Task ids must be non-empty directory names, not paths, and must not "
                "have leading or trailing whitespace."
            )

        seen: set[str] = set()
        duplicates: list[str] = []
        duplicate_seen: set[str] = set()
        for task_id in only:
            if task_id in seen and task_id not in duplicate_seen:
                duplicates.append(task_id)
                duplicate_seen.add(task_id)
            seen.add(task_id)
        if duplicates:
            raise ValueError(f"Duplicate task id(s): {', '.join(duplicates)}")

    selected = set(only) if only else None
    if selected:
        non_directories = sorted(
            name
            for name in selected
            if (tasks_dir / name).exists() and not (tasks_dir / name).is_dir()
        )
        if non_directories:
            raise ValueError(
                f"Selected task id(s) are not directories: {', '.join(non_directories)}"
            )

    tasks: list[Task] = []
    for child in sorted(tasks_dir.iterdir()):
        if selected:
            if child.name not in selected:
                continue
        else:
            if not child.is_dir():
                continue
            if not (child / PROMPT_FILE).is_file():
                continue
        tasks.append(load_task(child))

    if only:
        found = {t.id for t in tasks}
        unknown = [name for name in only if name not in found]
        if unknown:
            raise ValueError(f"Unknown task id(s): {', '.join(unknown)}")

    if not tasks:
        raise ValueError(f"No tasks found in {tasks_dir}")
    return tasks


def read_version(tasks_dir: Path) -> str:
    """Read the task-set VERSION file (recorded in every run for reproducibility)."""
    version_file = tasks_dir / "VERSION"
    if version_file.is_file():
        return version_file.read_text(encoding="utf-8").strip()
    return "unknown"
