from pathlib import Path

import pytest

from ruby_llm_eval.tasks import discover_tasks, load_task, read_version

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"


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


def test_version_is_recorded():
    assert read_version(TASKS_DIR) == "0.1.0"
