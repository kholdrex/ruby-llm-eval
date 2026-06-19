import filecmp
from pathlib import Path

from ruby_llm_eval.config import find_tasks_dir
from ruby_llm_eval.tasks import discover_tasks, read_version

REPO_ROOT = Path(__file__).resolve().parent.parent


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
    (task_dir / "prompt.md").write_text(prompt, encoding="utf-8")
    (task_dir / "test.rb").write_text(test, encoding="utf-8")
    (task_dir / "solution_ref.rb").write_text(reference, encoding="utf-8")
    return task_dir


def test_explicit_tasks_dir_does_not_require_version_file(tmp_path):
    write_task(tmp_path, "001_private")

    tasks_dir = find_tasks_dir(str(tmp_path))
    tasks = discover_tasks(tasks_dir)

    assert tasks_dir == tmp_path
    assert [task.id for task in tasks] == ["001_private"]
    assert read_version(tasks_dir) == "unknown"


def test_default_tasks_dir_prefers_local_tasks_without_version_file(tmp_path, monkeypatch):
    local_tasks = tmp_path / "tasks"
    write_task(local_tasks, "001_local")
    monkeypatch.chdir(tmp_path)

    tasks_dir = find_tasks_dir()
    tasks = discover_tasks(tasks_dir)

    assert tasks_dir == local_tasks
    assert [task.id for task in tasks] == ["001_local"]
    assert read_version(tasks_dir) == "unknown"


def test_default_tasks_dir_ignores_empty_local_tasks_dir(tmp_path, monkeypatch):
    empty_tasks = tmp_path / "tasks"
    empty_tasks.mkdir()
    monkeypatch.chdir(tmp_path)

    tasks_dir = find_tasks_dir()
    tasks = discover_tasks(tasks_dir)

    assert tasks_dir != empty_tasks
    assert tasks[0].id == "001_fizzbuzz"


def test_bundled_assets_match_source_assets():
    for name in ("configs", "sandbox", "tasks"):
        assert_asset_trees_match(REPO_ROOT / name, REPO_ROOT / "ruby_llm_eval" / "assets" / name)


def assert_asset_trees_match(source: Path, bundled: Path) -> None:
    comparison = filecmp.dircmp(source, bundled)
    assert comparison.left_only == []
    assert comparison.right_only == []
    assert comparison.diff_files == []
    assert comparison.funny_files == []
    for common_file in comparison.common_files:
        assert filecmp.cmp(source / common_file, bundled / common_file, shallow=False)
    for common_dir in comparison.common_dirs:
        assert_asset_trees_match(source / common_dir, bundled / common_dir)
