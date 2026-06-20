from pathlib import Path

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
