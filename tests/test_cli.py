import json
import subprocess
from pathlib import Path

import pytest

from ruby_llm_eval.cli import build_parser, main

TASKS_DIR = str(Path(__file__).resolve().parent.parent / "tasks")


def test_docker_readiness_distinguishes_missing_binary(monkeypatch):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _name: None)
    assert cli._docker_readiness() == (False, "docker not found on PATH")


def test_docker_readiness_times_out(monkeypatch):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/docker")

    def timeout(*args, **kwargs):
        assert kwargs["timeout"] == cli.DOCKER_INFO_TIMEOUT_SECONDS
        raise subprocess.TimeoutExpired(args[0], kwargs["timeout"])

    monkeypatch.setattr(cli.subprocess, "run", timeout)
    ok, detail = cli._docker_readiness()
    assert ok is False
    assert "timed out" in detail


def test_docker_readiness_reports_daemon_failure_not_missing_binary(monkeypatch):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli.shutil, "which", lambda _name: "/usr/bin/docker")
    monkeypatch.setattr(
        cli.subprocess,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(args[0], 1, "", "permission denied\n"),
    )
    assert cli._docker_readiness() == (False, "permission denied")


def write_private_task(tasks_dir: Path, task_id: str, method_name: str) -> Path:
    task_dir = tasks_dir / task_id
    task_dir.mkdir(parents=True)
    (task_dir / "prompt.md").write_text(f"Implement {method_name}(a, b).\n", encoding="utf-8")
    (task_dir / "test.rb").write_text('require_relative "solution"\n', encoding="utf-8")
    (task_dir / "solution_ref.rb").write_text(
        f"def {method_name}(a, b)\n  a + b\nend\n", encoding="utf-8"
    )
    return task_dir


def test_parser_accepts_run_flags():
    args = build_parser().parse_args(
        ["run", "--model", "m", "--jobs", "4", "-n", "10", "-k", "3", "--style"]
    )
    assert args.n == 10
    assert args.k == 3
    assert args.jobs == 4
    assert args.style is True


def test_parser_accepts_offline_stub_flag():
    args = build_parser().parse_args(["run", "--model", "stub", "--offline-stub"])
    assert args.offline_stub is True


def test_parser_accepts_doctor_flags():
    args = build_parser().parse_args(
        ["doctor", "--provider", "anthropic", "--config-dir", "/tmp/cfg"]
    )
    assert args.provider == "anthropic"
    assert args.config_dir == "/tmp/cfg"


def test_style_defaults_off():
    args = build_parser().parse_args(["run", "--model", "m"])
    assert args.style is False


def test_list_tasks_lists_frameworks(capsys):
    rc = main(["list-tasks", "--tasks", TASKS_DIR])
    assert rc == 0
    out = capsys.readouterr().out
    assert "001_fizzbuzz" in out
    assert "minitest" in out
    assert "016_stack" in out
    assert "rspec" in out


def test_list_tasks_filter(capsys):
    rc = main(["list-tasks", "--tasks", TASKS_DIR, "--task", "001_fizzbuzz"])
    assert rc == 0
    out = capsys.readouterr().out
    assert "001_fizzbuzz" in out
    assert "002_palindrome" not in out


def test_validate_tasks_runs_reference_solutions_in_sandbox(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    first = write_private_task(tasks_dir, "001_private_add", "add")
    second = write_private_task(tasks_dir, "002_private_sum", "sum_values")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_FAILED, STATUS_PASSED, SampleResult

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)
    (tmp_path / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")
    seen = []

    def fake_run(task, sample, **kwargs):
        seen.append((task.id, sample.code, kwargs))
        status = STATUS_PASSED if task.id == first.name else STATUS_FAILED
        return SampleResult(
            task.id, 0, status, "assertion failed" if status == STATUS_FAILED else ""
        )

    monkeypatch.setattr(cli, "run_sample", fake_run)
    rc = main(
        [
            "validate-tasks",
            "--tasks",
            str(tasks_dir),
            "--sandbox",
            str(tmp_path),
            "--timeout",
            "7",
            "--memory",
            "128m",
            "--cpus",
            "0.5",
        ]
    )

    assert rc == 1
    assert [item[0] for item in seen] == [first.name, second.name]
    assert "def add" in seen[0][1]
    assert seen[0][2]["timeout"] == 7
    out = capsys.readouterr().out
    assert "[PASS] 001_private_add" in out
    assert "[FAIL] 002_private_sum: assertion failed" in out
    assert "1 passed, 1 failed" in out


def test_validate_tasks_supports_repeatable_task_filter(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    write_private_task(tasks_dir, "002_private_sum", "sum_values")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_PASSED, SampleResult

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)
    seen = []

    def fake_run(task, sample, **kwargs):
        seen.append(task.id)
        return SampleResult(task.id, 0, STATUS_PASSED, "")

    monkeypatch.setattr(cli, "run_sample", fake_run)
    rc = main(["validate-tasks", "--tasks", str(tasks_dir), "--task", "002_private_sum"])

    assert rc == 0
    assert seen == ["002_private_sum"]
    assert "1 passed, 0 failed" in capsys.readouterr().out


def test_validate_tasks_shows_zero_test_reason_on_first_line(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_ERROR, SampleResult

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)
    monkeypatch.setattr(
        cli,
        "run_sample",
        lambda task, sample, **kwargs: SampleResult(
            task.id, 0, STATUS_ERROR, "zero tests ran\n0 runs, 0 assertions"
        ),
    )

    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 1
    assert "[FAIL] 001_private_add: zero tests ran" in capsys.readouterr().out


def test_validate_tasks_requires_docker_before_build(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: False)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: pytest.fail("must not build"))
    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 2
    assert (
        "Docker is required to validate task reference solutions safely" in capsys.readouterr().err
    )


@pytest.mark.parametrize(
    "failure",
    [
        subprocess.CalledProcessError(1, ["docker", "build"], stderr="daemon unavailable"),
        OSError("docker executable could not be launched"),
    ],
)
def test_validate_tasks_reports_image_setup_failures_as_usage_errors(
    tmp_path, monkeypatch, capsys, failure
):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)

    def fail_setup(_sandbox):
        raise failure

    monkeypatch.setattr(cli, "ensure_image", fail_setup)
    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 2
    captured = capsys.readouterr()
    assert "Error: Docker sandbox setup failed:" in captured.err
    detail = failure.stderr if isinstance(failure, subprocess.CalledProcessError) else str(failure)
    assert detail in captured.err


def test_validate_tasks_reports_sandbox_process_launch_failure_as_usage_error(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)

    def fail_launch(*_args, **_kwargs):
        raise OSError("cannot start docker process")

    monkeypatch.setattr(cli, "run_sample", fail_launch)
    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 2
    captured = capsys.readouterr()
    assert "Error: Docker sandbox process failed:" in captured.err
    assert "cannot start docker process" in captured.err
    assert "Validated" not in captured.out


def test_validate_tasks_maps_docker_run_exit_125_to_infrastructure_error(
    tmp_path, monkeypatch, capsys
):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)

    def fail_invocation(*_args, **_kwargs):
        raise subprocess.CalledProcessError(
            125, ["docker", "run"], stderr="docker: Error response from daemon"
        )

    monkeypatch.setattr(cli, "run_sample", fail_invocation)
    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 2
    captured = capsys.readouterr()
    assert "Docker sandbox process failed" in captured.err
    assert "Error response from daemon" in captured.err
    assert "[FAIL]" not in captured.out


@pytest.mark.parametrize("outcome", ["success", "failure"])
def test_validate_tasks_cleans_scratch_directory(tmp_path, monkeypatch, outcome):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_FAILED, STATUS_PASSED, SampleResult

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)
    status = STATUS_PASSED if outcome == "success" else STATUS_FAILED
    monkeypatch.setattr(
        cli, "run_sample", lambda task, sample, **kwargs: SampleResult(task.id, 0, status, "")
    )

    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == (0 if outcome == "success" else 1)
    assert not list(tmp_path.glob(".ruby-llm-eval-validation-*"))


@pytest.mark.parametrize(
    ("read_error", "detail"),
    [(FileNotFoundError("missing"), "missing"), (PermissionError("denied"), "denied")],
)
def test_validate_tasks_reports_unreadable_reference_as_task_failure(
    tmp_path, monkeypatch, capsys, read_error, detail
):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.tasks import Task

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox: None)
    monkeypatch.setattr(Task, "reference", lambda _self: (_ for _ in ()).throw(read_error))
    monkeypatch.setattr(cli, "run_sample", lambda *_args, **_kwargs: pytest.fail("must not run"))

    rc = main(["validate-tasks", "--tasks", str(tasks_dir)])

    assert rc == 1
    captured = capsys.readouterr()
    assert f"[FAIL] 001_private_add: cannot read solution_ref.rb: {detail}" in captured.out
    assert "0 passed, 1 failed" in captured.out
    assert "Traceback" not in captured.err


@pytest.mark.parametrize("selected", [None, "999_unknown"])
def test_validate_tasks_rejects_empty_or_unknown_task_set(tmp_path, monkeypatch, capsys, selected):
    monkeypatch.chdir(tmp_path)
    tasks_dir = tmp_path / "tasks"
    tasks_dir.mkdir()
    argv = ["validate-tasks", "--tasks", str(tasks_dir)]
    if selected:
        argv.extend(["--task", selected])

    rc = main(argv)

    assert rc == 2
    error = capsys.readouterr().err
    assert ("Unknown task id(s)" if selected else "No tasks found") in error


def test_doctor_reports_healthy_install(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n"
        "  stub:\n"
        "    type: stub\n"
        "  anthropic:\n"
        "    type: anthropic\n"
        "    base_url: https://api.anthropic.com\n"
        "    api_key_env: ANTHROPIC_API_KEY\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text("models: {}\n", encoding="utf-8")

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: False)
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
            "--provider",
            "anthropic",
        ]
    )

    assert rc == 0
    out = capsys.readouterr().out
    assert "[OK] config:" in out
    assert "[OK] providers:" in out
    assert "[OK] pricing:" in out
    assert "[OK] tasks:" in out
    assert "test-version" in out
    assert "[OK] docker:" in out
    assert "missing (will build on first run)" in out
    assert "[OK] provider anthropic: API key available" in out


def test_doctor_fails_when_explicit_sandbox_path_is_missing(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text("models: {}\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(tmp_path / "missing-sandbox"),
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] sandbox: Explicit sandbox path does not exist:" in out


def test_doctor_fails_when_explicit_config_path_is_missing(tmp_path, monkeypatch, capsys):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    missing_config = tmp_path / "missing-config"
    rc = main(["doctor", "--config-dir", str(missing_config)])

    assert rc == 1
    out = capsys.readouterr().out
    assert f"[FAIL] config: Explicit configs path does not exist: {missing_config}" in out


def test_doctor_fails_when_explicit_sandbox_path_has_no_dockerfile(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text("models: {}\n", encoding="utf-8")

    sandbox_dir = tmp_path / "sandbox-without-dockerfile"
    sandbox_dir.mkdir()

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] sandbox: Could not find 'Dockerfile' in explicit sandbox path:" in out


def test_doctor_fails_when_provider_key_missing(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n"
        "  anthropic:\n"
        "    type: anthropic\n"
        "    base_url: https://api.anthropic.com\n"
        "    api_key_env: ANTHROPIC_API_KEY\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text("models: {}\n", encoding="utf-8")

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
            "--provider",
            "anthropic",
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] provider anthropic: set ANTHROPIC_API_KEY or pass --api-key" in out


def test_doctor_fails_when_docker_daemon_unavailable(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text("models: {}\n", encoding="utf-8")

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(
        cli,
        "_docker_readiness",
        lambda: (False, "Docker daemon unreachable: permission denied"),
    )
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] docker: Docker daemon unreachable: permission denied" in out


def test_doctor_fails_when_pricing_config_invalid(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text(
        "models:\n  stub:\n    input: 0.0\n",
        encoding="utf-8",
    )

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] pricing:" in out
    assert "missing output" in out


def test_doctor_fails_when_pricing_value_is_boolean(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    (tasks_dir / "VERSION").write_text("test-version\n", encoding="utf-8")

    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n",
        encoding="utf-8",
    )
    (config_dir / "pricing.yaml").write_text(
        "models:\n  stub:\n    input: true\n    output: 0.0\n",
        encoding="utf-8",
    )

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "_docker_readiness", lambda: (True, "Docker daemon reachable"))
    monkeypatch.setattr(cli, "image_exists", lambda image=cli.IMAGE_TAG: True)

    rc = main(
        [
            "doctor",
            "--tasks",
            str(tasks_dir),
            "--config-dir",
            str(config_dir),
            "--sandbox",
            str(sandbox_dir),
        ]
    )

    assert rc == 1
    out = capsys.readouterr().out
    assert "[FAIL] pricing:" in out
    assert "non-numeric input price: True" in out


def test_stub_provider_smoke_selects_private_task_without_docker(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private_add", "add")
    write_private_task(tasks_dir, "002_private_subtract", "subtract")
    output_dir = tmp_path / "results"

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))
    monkeypatch.setattr(
        cli,
        "ensure_image",
        lambda _sandbox_dir: pytest.fail("Docker image was built"),
    )
    monkeypatch.setattr(
        cli,
        "run_sample",
        lambda *_args, **_kwargs: pytest.fail("Docker sample ran"),
    )

    list_rc = main(["list-tasks", "--tasks", str(tasks_dir), "--task", "002_private_subtract"])
    assert list_rc == 0
    listed = capsys.readouterr().out
    assert "002_private_subtract" in listed
    assert "001_private_add" not in listed

    run_rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--offline-stub",
            "--tasks",
            str(tasks_dir),
            "--task",
            "002_private_subtract",
            "--output",
            str(output_dir),
            "-n",
            "1",
        ]
    )

    assert run_rc == 0
    run_output = capsys.readouterr()
    assert "Tasks: 1" in run_output.err
    assert "002_private_subtract" in run_output.err
    assert "001_private_add" not in run_output.err
    assert "Offline stub provider" in run_output.err

    generated_root = output_dir / "stub"
    assert (generated_root / "002_private_subtract" / "sample_0.rb").is_file()
    assert not (generated_root / "001_private_add").exists()

    report_path = next(output_dir.glob("*.json"))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert [task["task_id"] for task in report["tasks"]] == ["002_private_subtract"]
    assert report["provider"] == "stub"
    assert report["model"] == "stub"
    assert report["evaluation_mode"] == "offline_stub"
    assert report["sandboxed"] is False
    assert report["categories"]["general"]["tasks"] == 1
    assert report["cost"]["priced"] is True
    assert report["cost"]["usd"] == 0.0
    md_path = next(output_dir.glob("*.md"))
    md = md_path.read_text(encoding="utf-8")
    assert "OFFLINE STUB REPORT" in md
    assert "NOT A REAL SANDBOXED EVALUATION" in md
    assert not (output_dir / ".sandbox").exists()


def test_stub_provider_model_without_offline_stub_uses_docker(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private", "add")

    sandbox_dir = tmp_path / "sandbox"
    sandbox_dir.mkdir()
    (sandbox_dir / "Dockerfile").write_text("FROM scratch\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_PASSED, SampleResult

    calls = {"docker_available": 0, "ensure_image": 0, "run_sample": 0}

    def fake_docker_available():
        calls["docker_available"] += 1
        return True

    monkeypatch.setattr(cli, "docker_available", fake_docker_available)
    monkeypatch.setattr(
        cli,
        "ensure_image",
        lambda _sandbox_dir: calls.__setitem__("ensure_image", 1),
    )

    def fake_run_sample(task, sample, **_kwargs):
        calls["run_sample"] += 1
        return SampleResult(task.id, sample.index, STATUS_PASSED)

    monkeypatch.setattr(cli, "run_sample", fake_run_sample)

    rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--tasks",
            str(tasks_dir),
            "--sandbox",
            str(sandbox_dir),
            "--output",
            str(tmp_path / "results"),
            "-n",
            "1",
        ]
    )

    assert rc == 0
    assert calls == {"docker_available": 1, "ensure_image": 1, "run_sample": 1}


def test_run_fails_when_explicit_sandbox_path_is_missing(tmp_path, monkeypatch, capsys):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private", "add")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(
        cli,
        "ensure_image",
        lambda *_args, **_kwargs: pytest.fail("ensure_image ran"),
    )

    rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--tasks",
            str(tasks_dir),
            "--sandbox",
            str(tmp_path / "missing-sandbox"),
            "--output",
            str(tmp_path / "results"),
            "-n",
            "1",
        ]
    )

    assert rc == 2
    err = capsys.readouterr().err
    assert "Explicit sandbox path does not exist:" in err


def test_offline_stub_rejects_style_without_checking_docker(monkeypatch):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))

    rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--offline-stub",
            "--style",
            "--tasks",
            TASKS_DIR,
            "--task",
            "001_fizzbuzz",
            "-n",
            "1",
        ]
    )

    assert rc == 2


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--timeout", "0", "--timeout must be >= 1"),
        ("--cpus", "0", "--cpus must be > 0"),
        ("--cpus", "nan", "--cpus must be > 0"),
        ("--memory", "", "--memory must be a positive integer"),
        ("--memory", "0", "--memory must be a positive integer"),
        ("--memory", "256mb", "--memory must be a positive integer"),
        ("--memory", " 256m ", "--memory must be a positive integer"),
        ("--jobs", "0", "--jobs must be >= 1"),
    ],
)
def test_run_rejects_invalid_sandbox_limits_before_docker(
    option, value, message, monkeypatch, capsys
):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))
    rc = main(["run", "--model", "stub", option, value])

    assert rc == 2
    assert message in capsys.readouterr().err


@pytest.mark.parametrize(
    ("option", "value", "message"),
    [
        ("--timeout", "-1", "--timeout must be >= 1"),
        ("--cpus", "-0.5", "--cpus must be > 0"),
        ("--memory", "", "--memory must be a positive integer"),
    ],
)
def test_validate_tasks_rejects_invalid_sandbox_limits_before_discovery(
    option, value, message, monkeypatch, capsys
):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "find_tasks_dir", lambda *_args: pytest.fail("tasks were discovered"))
    rc = main(["validate-tasks", option, value])

    assert rc == 2
    assert message in capsys.readouterr().err


def test_offline_stub_requires_stub_provider_and_model(monkeypatch):
    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))

    rc = main(
        [
            "run",
            "--model",
            "demo-model",
            "--provider",
            "stub",
            "--offline-stub",
            "--tasks",
            TASKS_DIR,
            "--task",
            "001_fizzbuzz",
            "-n",
            "1",
        ]
    )

    assert rc == 2


def test_offline_stub_requires_stub_provider_and_model_before_loading_config(
    tmp_path, monkeypatch, capsys
):
    import ruby_llm_eval.cli as cli

    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text(
        "providers:\n  stub:\n    type: stub\n", encoding="utf-8"
    )

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))

    rc = main(
        [
            "run",
            "--model",
            "demo-model",
            "--provider",
            "stub",
            "--offline-stub",
            "--config-dir",
            str(config_dir),
            "--tasks",
            TASKS_DIR,
            "--task",
            "001_fizzbuzz",
            "-n",
            "1",
        ]
    )

    assert rc == 2
    assert "--offline-stub requires --provider stub --model stub" in capsys.readouterr().err


def test_offline_stub_uses_builtin_stub_config_without_loading_config(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    write_private_task(tasks_dir, "001_private", "add")
    config_dir = tmp_path / "config"
    config_dir.mkdir()
    (config_dir / "providers.yaml").write_text("providers: {}\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: pytest.fail("Docker was checked"))

    output_dir = tmp_path / "results"
    rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--offline-stub",
            "--config-dir",
            str(config_dir),
            "--tasks",
            str(tasks_dir),
            "--output",
            str(output_dir),
            "-n",
            "1",
        ]
    )

    assert rc == 0
    report = json.loads(next(output_dir.glob("*.json")).read_text(encoding="utf-8"))
    assert report["evaluation_mode"] == "offline_stub"
    assert report["cost"] == {
        "input_tokens": 0,
        "output_tokens": 0,
        "usd": 0.0,
        "priced": True,
    }


def test_run_cleans_sandbox_scratch_after_evaluation_failure(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "001_private"
    task_dir.mkdir(parents=True)
    (task_dir / "prompt.md").write_text("Implement add(a, b).\n", encoding="utf-8")
    (task_dir / "test.rb").write_text('require_relative "solution"\n', encoding="utf-8")
    (task_dir / "solution_ref.rb").write_text("def add(a, b)\n  a + b\nend\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox_dir: None)

    def fail_run_sample(*_args, **_kwargs):
        raise RuntimeError("container runtime failed")

    monkeypatch.setattr(cli, "run_sample", fail_run_sample)

    output_dir = tmp_path / "results"
    with pytest.raises(RuntimeError, match="container runtime failed"):
        main(
            [
                "run",
                "--model",
                "stub",
                "--provider",
                "stub",
                "--tasks",
                str(tasks_dir),
                "--output",
                str(output_dir),
                "-n",
                "1",
            ]
        )

    assert not (output_dir / ".sandbox").exists()


def test_run_cleans_sandbox_scratch_after_success(tmp_path, monkeypatch):
    tasks_dir = tmp_path / "tasks"
    task_dir = tasks_dir / "001_private"
    task_dir.mkdir(parents=True)
    (task_dir / "prompt.md").write_text("Implement add(a, b).\n", encoding="utf-8")
    (task_dir / "test.rb").write_text('require_relative "solution"\n', encoding="utf-8")
    (task_dir / "solution_ref.rb").write_text("def add(a, b)\n  a + b\nend\n", encoding="utf-8")

    import ruby_llm_eval.cli as cli
    from ruby_llm_eval.evaluate import STATUS_PASSED, SampleResult

    monkeypatch.setattr(cli, "docker_available", lambda: True)
    monkeypatch.setattr(cli, "ensure_image", lambda _sandbox_dir: None)
    monkeypatch.setattr(
        cli,
        "run_sample",
        lambda task, sample, **_kwargs: SampleResult(task.id, sample.index, STATUS_PASSED),
    )

    output_dir = tmp_path / "results"
    rc = main(
        [
            "run",
            "--model",
            "stub",
            "--provider",
            "stub",
            "--tasks",
            str(tasks_dir),
            "--output",
            str(output_dir),
            "-n",
            "1",
        ]
    )

    assert rc == 0
    assert list(output_dir.glob("*.json"))
    assert list(output_dir.glob("*.md"))
    assert not (output_dir / ".sandbox").exists()
