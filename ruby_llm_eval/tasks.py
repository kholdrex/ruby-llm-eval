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

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path

import yaml

PROMPT_FILE = "prompt.md"
REFERENCE_FILE = "solution_ref.rb"
# Optional per-task metadata (e.g. `category: rails`); absent => general.
META_FILE = "meta.yml"
DEFAULT_CATEGORY = "general"
SUPPORTED_META_KEYS = {"category"}

# Map each supported framework to the test filename that selects it.
TEST_FILES = {"minitest": "test.rb", "rspec": "spec.rb"}
SOLUTION_REQUIREMENT_PATTERN = re.compile(
    r'^\s*require_relative(?:\s+|\s*\()\s*["\']solution["\']\s*\)?\s*(?:#.*)?$',
    re.MULTILINE,
)


@dataclass(frozen=True)
class Task:
    """A single benchmark task loaded from disk."""

    id: str
    path: Path
    prompt: str
    framework: str  # "minitest" or "rspec"
    test_filename: str  # "test.rb" or "spec.rb"
    test: str
    category: str = DEFAULT_CATEGORY

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


def _read_category(task_dir: Path) -> str:
    """Read the optional task category from meta.yml (defaults to 'general')."""
    meta_path = task_dir / META_FILE
    if not meta_path.is_file():
        return DEFAULT_CATEGORY
    try:
        text = meta_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} must be UTF-8 text "
            f"(invalid byte at offset {exc.start})."
        ) from None

    try:
        loaded = yaml.safe_load(text)
    except yaml.YAMLError as exc:
        detail = getattr(exc, "problem", None) or (str(exc).splitlines() or [""])[0]
        suffix = f" ({detail})." if detail else "."
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} must be valid YAML{suffix}"
        ) from None

    if loaded is None:
        data = {}
    elif not isinstance(loaded, dict):
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} must contain a YAML mapping/object."
        ) from None
    else:
        data = loaded

    non_string_keys = sorted((key for key in data if not isinstance(key, str)), key=str)
    if non_string_keys:
        formatted_keys = ", ".join(str(key) for key in non_string_keys)
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} contains non-string key(s): "
            f"{formatted_keys}. All {META_FILE} keys must be strings."
        )

    unknown_keys = sorted((key for key in data if key not in SUPPORTED_META_KEYS), key=str)
    if unknown_keys:
        formatted_keys = ", ".join(str(key) for key in unknown_keys)
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} contains unknown key(s): "
            f"{formatted_keys}. Supported key(s): {', '.join(sorted(SUPPORTED_META_KEYS))}."
        )

    category = data.get("category", DEFAULT_CATEGORY)
    if category is None:
        return DEFAULT_CATEGORY
    if not isinstance(category, str):
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} field 'category' "
            f"must be a string, got {type(category).__name__}."
        )
    category = category.strip()
    if not category:
        return DEFAULT_CATEGORY
    if (
        "|" in category
        or category.splitlines() != [category]
        or any(unicodedata.category(char).startswith("C") for char in category)
    ):
        raise ValueError(
            f"Task '{task_dir.name}' optional file {META_FILE} field 'category' "
            "must be a single-line report label without control characters or '|'."
        )
    return category


def _format_task_id_for_message(task_id: str) -> str:
    if task_id == "":
        return "<empty>"
    if not task_id.strip():
        return "<blank>"
    if _has_non_printable_characters(task_id):
        return repr(task_id)
    return task_id


def _validate_task_directory_id(task_dir: Path) -> None:
    task_id = task_dir.name
    if (
        not task_id.strip()
        or task_id != task_id.strip()
        or "|" in task_id
        or _has_non_printable_characters(task_id)
    ):
        label = _format_task_id_for_message(task_id)
        raise ValueError(
            f"Task directory id {label} must be a nonblank single-line report label "
            "without leading or trailing whitespace, control or non-printable "
            "characters, or the '|' character."
        )


def _detect_framework(task_dir: Path) -> tuple[tuple[str, str] | None, list[str]]:
    """Return (framework, test_filename) for a task, collecting any framework errors."""
    present = [(fw, fn) for fw, fn in TEST_FILES.items() if (task_dir / fn).is_file()]
    options = " / ".join(TEST_FILES.values())
    if not present:
        return None, [f"has no test file (expected one of: {options})."]
    if len(present) > 1:
        return None, [f"has multiple test files; include exactly one of {options}."]
    return present[0], []


def _collect_task_file_errors(task_dir: Path) -> tuple[list[str], str | None, str | None]:
    """Collect malformed-file problems before reading task contents."""
    issues: list[str] = []
    for filename in (PROMPT_FILE, REFERENCE_FILE):
        if not (task_dir / filename).is_file():
            issues.append(f"missing {filename}")

    framework_and_file, framework_errors = _detect_framework(task_dir)
    issues.extend(framework_errors)

    framework = test_filename = None
    if framework_and_file:
        framework, test_filename = framework_and_file

    return issues, framework, test_filename


def _heredoc_labels_for_line(line: str) -> list[str]:
    labels: list[str] = []
    in_single_quote = False
    in_double_quote = False
    escape = False
    index = 0
    length = len(line)

    while index < length:
        char = line[index]

        if in_single_quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == "'":
                in_single_quote = False
            index += 1
            continue

        if in_double_quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_double_quote = False
            index += 1
            continue

        if char == "#":
            break
        if char == "'":
            in_single_quote = True
            index += 1
            continue
        if char == '"':
            in_double_quote = True
            index += 1
            continue
        if line[index : index + 2] != "<<":
            index += 1
            continue

        candidate_index = index + 2
        if candidate_index < length and line[candidate_index] in {"-", "~"}:
            candidate_index += 1
        if candidate_index >= length:
            break

        quote = line[candidate_index] if line[candidate_index] in {"'", '"'} else None
        if quote is not None:
            candidate_index += 1

        label_start = candidate_index
        while candidate_index < length and (
            line[candidate_index].isalnum() or line[candidate_index] == "_"
        ):
            candidate_index += 1
        label = line[label_start:candidate_index]
        if not label or not (label[0].isalpha() or label[0] == "_"):
            index += 1
            continue

        if quote is not None:
            if candidate_index >= length or line[candidate_index] != quote:
                index += 1
                continue
            candidate_index += 1

        labels.append(label)
        index = candidate_index

    return labels


def _test_requires_solution(test_contents: str) -> bool:
    heredoc_labels: list[str] = []
    in_block_comment = False

    for line in test_contents.splitlines():
        if in_block_comment:
            if line == "=end":
                in_block_comment = False
            continue

        if line == "=begin":
            in_block_comment = True
            continue

        if line == "__END__":
            return False

        stripped = line.strip()
        if heredoc_labels:
            if stripped == heredoc_labels[0]:
                heredoc_labels.pop(0)
            continue

        if SOLUTION_REQUIREMENT_PATTERN.fullmatch(line):
            return True

        heredoc_labels = _heredoc_labels_for_line(line)

    return False


def _validate_test_contents(task_dir: Path, test_filename: str, test_contents: str) -> None:
    if _test_requires_solution(test_contents):
        return

    raise ValueError(
        f"Task '{task_dir.name}' file {test_filename} must include a standalone "
        'require_relative "solution" line so benchmark tests execute solution.rb.'
    )


def load_task(task_dir: Path) -> Task:
    """Load a task directory, validating required files exist and are non-empty."""
    _validate_task_directory_id(task_dir)

    file_errors, framework, test_filename = _collect_task_file_errors(task_dir)
    if file_errors:
        raise ValueError(f"Task '{task_dir.name}' has malformed file(s): {', '.join(file_errors)}")

    if framework is None or test_filename is None:
        raise RuntimeError(f"Task '{task_dir.name}' has malformed test files.")

    required = (PROMPT_FILE, REFERENCE_FILE, test_filename)
    contents = {name: _read_required(task_dir, name) for name in required}
    empty = [name for name, content in contents.items() if not content.strip()]
    if empty:
        raise ValueError(f"Task '{task_dir.name}' has empty required file(s): {', '.join(empty)}")

    _validate_test_contents(task_dir, test_filename, contents[test_filename])

    return Task(
        id=task_dir.name,
        path=task_dir,
        prompt=contents[PROMPT_FILE],
        framework=framework,
        test_filename=test_filename,
        test=contents[test_filename],
        category=_read_category(task_dir),
    )


def _format_invalid_selected_task_id(task_id: str) -> str:
    return _format_task_id_for_message(task_id)


def _has_non_printable_characters(value: str) -> bool:
    return any(unicodedata.category(char).startswith("C") for char in value)


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
            or "|" in task_id
            or _has_non_printable_characters(task_id)
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
                "Task ids must be non-empty directory names, not paths, must not "
                "have leading or trailing whitespace, and must not contain control or "
                "non-printable characters or '|'."
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
    if not version_file.is_file():
        return "unknown"
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError(
            f"Task set VERSION file at {version_file} must be UTF-8 text "
            f"(invalid byte at offset {exc.start})."
        ) from None
    if not version:
        return "unknown"
    if (
        "|" in version
        or version.splitlines() != [version]
        or _has_non_printable_characters(version)
    ):
        raise ValueError(
            f"Task set VERSION file at {version_file} must be a single-line "
            "report label without control characters or '|'."
        )
    return version
