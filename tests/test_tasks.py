from pathlib import Path

import pytest

from ruby_llm_eval.tasks import (
    PROMPT_FILE,
    REFERENCE_FILE,
    TEST_FILE,
    discover_tasks,
    load_task,
    read_version,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"


def write_task(
    tasks_dir: Path,
    task_id: str,
    *,
    prompt: str = "Implement add(a, b).\n",
    test: str = 'require_relative "solution"\n',
    reference: str = "def add(a, b)\n  a + b\nend\n",
) -> Path:
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    (task_dir / PROMPT_FILE).write_text(prompt, encoding="utf-8")
    (task_dir / TEST_FILE).write_text(test, encoding="utf-8")
    (task_dir / REFERENCE_FILE).write_text(reference, encoding="utf-8")
    return task_dir


def test_discovers_all_seed_tasks_sorted():
    tasks = discover_tasks(TASKS_DIR)
    assert len(tasks) >= 8
    ids = [t.id for t in tasks]
    assert ids == sorted(ids)
    assert "001_fizzbuzz" in ids


def test_only_filter():
    tasks = discover_tasks(TASKS_DIR, only=["001_fizzbuzz"])
    assert [t.id for t in tasks] == ["001_fizzbuzz"]


def test_unknown_task_id_raises():
    with pytest.raises(ValueError):
        discover_tasks(TASKS_DIR, only=["999_nope"])


def test_task_has_reference_and_test():
    task = load_task(TASKS_DIR / "001_fizzbuzz")
    assert "fizzbuzz" in task.prompt.lower()
    assert "require_relative" in task.test
    assert "def fizzbuzz" in task.reference()


def test_discovers_valid_custom_task(tmp_path):
    write_task(tmp_path, "002_second")
    write_task(tmp_path, "001_first")

    tasks = discover_tasks(tmp_path)

    assert [task.id for task in tasks] == ["001_first", "002_second"]
    assert tasks[0].prompt == "Implement add(a, b).\n"
    assert tasks[0].test == 'require_relative "solution"\n'
    assert tasks[0].reference() == "def add(a, b)\n  a + b\nend\n"


@pytest.mark.parametrize(
    ("filename", "overrides"),
    [
        ("prompt.md", {"prompt": "\n\t  \n"}),
        ("test.rb", {"test": "\n\t  \n"}),
        ("solution_ref.rb", {"reference": "\n\t  \n"}),
    ],
)
def test_load_task_rejects_blank_required_files(tmp_path, filename, overrides):
    task_dir = write_task(tmp_path, "001_blank", **overrides)

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_blank" in message
    assert filename in message
    assert "empty required file" in message


def test_version_is_recorded():
    assert read_version(TASKS_DIR) == "0.1.0"
