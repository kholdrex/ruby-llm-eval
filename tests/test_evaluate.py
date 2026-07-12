import subprocess

import pytest

from ruby_llm_eval.evaluate import (
    FRAMEWORKS,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    _classify,
    run_sample,
)
from ruby_llm_eval.generate import Sample
from ruby_llm_eval.tasks import Task

MINITEST = FRAMEWORKS["minitest"]["summary"]
RSPEC = FRAMEWORKS["rspec"]["summary"]

MINITEST_OK = "3 runs, 9 assertions, 0 failures, 0 errors, 0 skips"
MINITEST_FAIL = "3 runs, 9 assertions, 1 failures, 0 errors, 0 skips"
RSPEC_FAIL = "5 examples, 1 failure"
RSPEC_OK = "5 examples, 0 failures"


def test_exit_zero_is_passed():
    assert _classify(0, MINITEST_OK, "", MINITEST) == STATUS_PASSED


def test_exit_124_is_timeout():
    assert _classify(124, "", "", MINITEST) == STATUS_TIMEOUT


def test_failed_assertion_is_failed():
    assert _classify(1, MINITEST_FAIL, "", MINITEST) == STATUS_FAILED


def test_load_error_is_error():
    # No framework summary printed => the file blew up before tests ran.
    stderr = "solution.rb:1: syntax error, unexpected end-of-input"
    assert _classify(1, "", stderr, MINITEST) == STATUS_ERROR


def test_rspec_failure_is_failed():
    assert _classify(1, RSPEC_FAIL, "", RSPEC) == STATUS_FAILED


@pytest.mark.parametrize(
    ("summary", "framework"),
    [
        ("0 runs, 0 assertions, 0 failures, 0 errors, 0 skips", MINITEST),
        ("0 examples, 0 failures", RSPEC),
    ],
)
def test_zero_test_summary_is_error_even_with_exit_zero(summary, framework):
    assert _classify(0, summary, "", framework) == STATUS_ERROR


@pytest.mark.parametrize("returncode", [0, 1])
def test_missing_summary_is_error_regardless_of_exit_code(returncode):
    assert _classify(returncode, "test output", "warning", MINITEST) == STATUS_ERROR


@pytest.mark.parametrize("summary", [MINITEST_OK, RSPEC_OK])
def test_positive_test_summary_with_exit_zero_is_passed(summary):
    framework = MINITEST if "runs" in summary else RSPEC
    assert _classify(0, summary, "", framework) == STATUS_PASSED


def test_timeout_is_authoritative_even_with_zero_test_summary():
    assert _classify(124, "0 runs, 0 assertions", "", MINITEST) == STATUS_TIMEOUT


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        ("0 runs, 0 assertions, 0 failures, 0 errors, 0 skips\n", "zero tests ran"),
        ("runner stopped before reporting\n", "test summary missing"),
    ],
)
def test_run_sample_reports_empty_suite_reason_before_bounded_output(
    tmp_path, monkeypatch, stdout, reason
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    task = Task("001_test", task_dir, "prompt", "minitest", "test.rb", "test source")
    sample = Sample(0, "def answer = 42", 0, 0)
    monkeypatch.setattr(
        "ruby_llm_eval.evaluate.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["docker", "run"], 0, stdout + ("x" * 5000), "warning"
        ),
    )

    result = run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.splitlines()[0] == reason
    assert stdout.strip() in result.stderr
    assert len(result.stderr) == 4000


def test_minitest_regex_does_not_match_rspec_output():
    # A Minitest task whose output only has RSpec-style text never ran Minitest.
    assert _classify(1, RSPEC_FAIL, "", MINITEST) == STATUS_ERROR


def test_run_sample_raises_infrastructure_error_for_docker_exit_125(tmp_path, monkeypatch):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    task = Task("001_test", task_dir, "prompt", "minitest", "test.rb", "test source")
    sample = Sample(0, "def answer = 42", 0, 0)

    monkeypatch.setattr(
        "ruby_llm_eval.evaluate.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(
            ["docker", "run"], 125, "", "daemon unavailable"
        ),
    )

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert exc_info.value.returncode == 125
    assert exc_info.value.stderr == "daemon unavailable"
    assert not list((tmp_path / "scratch").glob("rle_*"))
