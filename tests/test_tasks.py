from pathlib import Path

import pytest

from ruby_llm_eval.tasks import (
    PROMPT_FILE,
    REFERENCE_FILE,
    TEST_FILES,
    discover_tasks,
    load_task,
    read_version,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = REPO_ROOT / "tasks"
MINITEST_FILE = TEST_FILES["minitest"]


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
    (task_dir / MINITEST_FILE).write_text(test, encoding="utf-8")
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


def test_selected_malformed_task_reports_missing_prompt(tmp_path):
    (tmp_path / "001_missing_prompt").mkdir()

    with pytest.raises(ValueError) as exc_info:
        discover_tasks(tmp_path, only=["001_missing_prompt"])

    message = str(exc_info.value)
    assert "001_missing_prompt" in message
    assert "missing prompt.md" in message


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


@pytest.mark.parametrize("filename", [PROMPT_FILE, MINITEST_FILE, REFERENCE_FILE])
def test_load_task_rejects_required_files_with_invalid_utf8(tmp_path, filename):
    task_dir = write_task(tmp_path, "001_bad_encoding")
    (task_dir / filename).write_bytes(b"valid prefix\xff\xfe\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_encoding" in message
    assert filename in message
    assert "must be UTF-8 text" in message
    assert "offset" in message
    assert exc_info.value.__cause__ is None


def test_load_task_rejects_rspec_required_file_with_invalid_utf8(tmp_path):
    task_dir = write_task(tmp_path, "001_bad_rspec_encoding")
    (task_dir / MINITEST_FILE).unlink()
    spec_file = TEST_FILES["rspec"]
    (task_dir / spec_file).write_bytes(b"valid prefix\xff\xfe\n")

    with pytest.raises(ValueError) as exc_info:
        load_task(task_dir)

    message = str(exc_info.value)
    assert "001_bad_rspec_encoding" in message
    assert spec_file in message
    assert "must be UTF-8 text" in message
    assert "offset" in message


def test_detects_minitest_framework():
    task = load_task(TASKS_DIR / "001_fizzbuzz")
    assert task.framework == "minitest"
    assert task.test_filename == "test.rb"


def test_detects_rspec_framework():
    task = load_task(TASKS_DIR / "016_stack")
    assert task.framework == "rspec"
    assert task.test_filename == "spec.rb"
    assert "RSpec.describe" in task.test


def test_activerecord_task_present():
    task = load_task(TASKS_DIR / "017_ar_scopes")
    assert task.framework == "minitest"
    assert "ActiveRecord::Base" in task.reference()
    assert "active_record" in task.test


def test_version_is_recorded():
    assert read_version(TASKS_DIR) == "0.3.0"
