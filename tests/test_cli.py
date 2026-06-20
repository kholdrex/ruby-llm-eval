from pathlib import Path

import pytest

from ruby_llm_eval.cli import build_parser, main

TASKS_DIR = str(Path(__file__).resolve().parent.parent / "tasks")


def test_parser_accepts_run_flags():
    args = build_parser().parse_args(
        ["run", "--model", "m", "--jobs", "4", "-n", "10", "-k", "3", "--style"]
    )
    assert args.n == 10
    assert args.k == 3
    assert args.jobs == 4
    assert args.style is True


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
