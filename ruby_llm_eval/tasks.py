"""Discover and load benchmark tasks from a tasks directory.

A task is a directory named like ``001_fizzbuzz`` containing three files:

    prompt.md        the problem description + exact Ruby signature to implement
    test.rb          a Minitest suite that ``require_relative "solution"``
    solution_ref.rb  a reference solution (never shown to the model)

This is the entire contribution surface. Adding a task means adding a folder;
there is no registry to edit.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PROMPT_FILE = "prompt.md"
TEST_FILE = "test.rb"
REFERENCE_FILE = "solution_ref.rb"


@dataclass(frozen=True)
class Task:
    """A single benchmark task loaded from disk."""

    id: str
    path: Path
    prompt: str
    test: str

    def reference(self) -> str:
        """Read the reference solution. Used to self-test tasks and the stub."""
        return (self.path / REFERENCE_FILE).read_text(encoding="utf-8")


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_task(task_dir: Path) -> Task:
    """Load a single task directory, validating that required files exist and are non-empty."""
    missing = [
        name for name in (PROMPT_FILE, TEST_FILE, REFERENCE_FILE) if not (task_dir / name).is_file()
    ]
    if missing:
        raise ValueError(
            f"Task '{task_dir.name}' is missing required file(s): {', '.join(missing)}"
        )

    contents = {name: _read(task_dir / name) for name in (PROMPT_FILE, TEST_FILE, REFERENCE_FILE)}
    empty = [name for name, content in contents.items() if not content.strip()]
    if empty:
        raise ValueError(f"Task '{task_dir.name}' has empty required file(s): {', '.join(empty)}")

    return Task(
        id=task_dir.name,
        path=task_dir,
        prompt=contents[PROMPT_FILE],
        test=contents[TEST_FILE],
    )


def discover_tasks(tasks_dir: Path, only: list[str] | None = None) -> list[Task]:
    """Load every task in ``tasks_dir``, sorted by id for deterministic runs.

    A directory is treated as a task if it contains a ``prompt.md``. The
    optional ``only`` list filters to specific task ids (exact match).
    """
    if not tasks_dir.is_dir():
        raise FileNotFoundError(f"Tasks directory not found: {tasks_dir}")

    tasks: list[Task] = []
    for child in sorted(tasks_dir.iterdir()):
        if not child.is_dir() or not (child / PROMPT_FILE).is_file():
            continue
        if only and child.name not in only:
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
