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
from ruby_llm_eval.config import find_config_dir, find_sandbox_dir, find_tasks_dir
from ruby_llm_eval.tasks import discover_tasks, read_version

config_dir = find_config_dir()
tasks_dir = find_tasks_dir()
sandbox_dir = find_sandbox_dir()
tasks = discover_tasks(tasks_dir)
print(json.dumps({
    "config_dir": str(config_dir),
    "tasks_dir": str(tasks_dir),
    "sandbox_dir": str(sandbox_dir),
    "task_count": len(tasks),
    "first_task": tasks[0].id,
    "version": read_version(tasks_dir),
}))
"""
    outside_source = tmp_path / "outside-source"
    outside_source.mkdir()
    result = run([str(python), "-c", probe], cwd=outside_source)
    payload = json.loads(result.stdout)

    assert payload["config_dir"].endswith("ruby_llm_eval/assets/configs")
    assert payload["tasks_dir"].endswith("ruby_llm_eval/assets/tasks")
    assert payload["sandbox_dir"].endswith("ruby_llm_eval/assets/sandbox")
    assert payload["task_count"] >= 10
    assert payload["first_task"] == "001_fizzbuzz"
    expected_version = (REPO_ROOT / "tasks" / "VERSION").read_text(encoding="utf-8").strip()
    assert payload["version"] == expected_version
