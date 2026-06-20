import json
import subprocess
import sys
import venv
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def run(command: list[str], *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    result = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        raise AssertionError(
            f"Command failed with exit code {result.returncode}: {command}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def test_wheel_installs_bundled_runtime_assets(tmp_path):
    dist_dir = tmp_path / "dist"
    dist_dir.mkdir()
    run([sys.executable, "-m", "pip", "wheel", ".", "-w", str(dist_dir)], cwd=REPO_ROOT)
    wheel = next(dist_dir.glob("ruby_llm_eval-*.whl"))

    venv_dir = tmp_path / "venv"
    venv.EnvBuilder(with_pip=True).create(venv_dir)
    scripts_dir = "Scripts" if sys.platform == "win32" else "bin"
    python = venv_dir / scripts_dir / "python"
    pip = venv_dir / scripts_dir / "pip"
    run([str(pip), "install", str(wheel)])

    probe = """
import json
from ruby_llm_eval.config import (
    find_config_dir,
    find_sandbox_dir,
    find_tasks_dir,
    load_rubocop_config,
)
from ruby_llm_eval.tasks import discover_tasks, read_version

config_dir = find_config_dir()
tasks_dir = find_tasks_dir()
sandbox_dir = find_sandbox_dir()
tasks = discover_tasks(tasks_dir)
# Use a bundled Rails task as a stable smoke fixture so the installed-wheel
# probe catches stale or incomplete package task assets.
selected_tasks = discover_tasks(tasks_dir, only=["017_ar_scopes"])
rubocop_config = load_rubocop_config(config_dir)
print(json.dumps({
    "config_dir": str(config_dir),
    "has_providers": (config_dir / "providers.yaml").is_file(),
    "has_rubocop_config": bool(rubocop_config),
    "rubocop_config_is_text": isinstance(rubocop_config, str),
    "rubocop_config_includes_all_cops": "AllCops" in (rubocop_config or ""),
    "tasks_dir": str(tasks_dir),
    "sandbox_dir": str(sandbox_dir),
    "has_sandbox_dockerfile": (sandbox_dir / "Dockerfile").is_file(),
    "task_count": len(tasks),
    "first_task": tasks[0].id,
    "selected_task_count": len(selected_tasks),
    "selected_task": selected_tasks[0].id,
    "selected_task_uses_active_record": "ActiveRecord::Base" in selected_tasks[0].reference(),
    "version": read_version(tasks_dir),
}))
"""
    outside_source = tmp_path / "outside-source"
    outside_source.mkdir()
    result = run([str(python), "-c", probe], cwd=outside_source)
    payload = json.loads(result.stdout)
    list_tasks = run([str(python), "-m", "ruby_llm_eval.cli", "list-tasks"], cwd=outside_source)
    selected_task = run(
        [str(python), "-m", "ruby_llm_eval.cli", "list-tasks", "--task", "017_ar_scopes"],
        cwd=outside_source,
    )

    assert "001_fizzbuzz" in list_tasks.stdout
    assert "016_stack" in list_tasks.stdout
    assert "ruby_llm_eval/assets/tasks" in list_tasks.stdout
    assert "017_ar_scopes" in selected_task.stdout
    assert "001_fizzbuzz" not in selected_task.stdout
    assert payload["config_dir"].endswith("ruby_llm_eval/assets/configs")
    assert payload["has_providers"] is True
    assert payload["has_rubocop_config"] is True
    assert payload["rubocop_config_is_text"] is True
    assert payload["rubocop_config_includes_all_cops"] is True
    assert payload["tasks_dir"].endswith("ruby_llm_eval/assets/tasks")
    assert payload["sandbox_dir"].endswith("ruby_llm_eval/assets/sandbox")
    assert payload["has_sandbox_dockerfile"] is True
    assert payload["task_count"] >= 19
    assert payload["first_task"] == "001_fizzbuzz"
    assert payload["selected_task_count"] == 1
    assert payload["selected_task"] == "017_ar_scopes"
    assert payload["selected_task_uses_active_record"] is True
    expected_version = (REPO_ROOT / "tasks" / "VERSION").read_text(encoding="utf-8").strip()
    assert payload["version"] == expected_version
