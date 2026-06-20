import json
from pathlib import Path

import pytest

from ruby_llm_eval.cli import build_parser, main

TASKS_DIR = str(Path(__file__).resolve().parent.parent / "tasks")


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
            "--output",
            str(tmp_path / "results"),
            "-n",
            "1",
        ]
    )

    assert rc == 0
    assert calls == {"docker_available": 1, "ensure_image": 1, "run_sample": 1}


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
