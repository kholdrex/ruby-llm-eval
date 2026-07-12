import shutil
import subprocess

import pytest

from ruby_llm_eval.evaluate import (
    IMAGE_TAG,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    _classify,
    run_sample,
)
from ruby_llm_eval.generate import Sample
from ruby_llm_eval.tasks import Task


def _docker_sandbox_ready():
    if shutil.which("docker") is None:
        return False
    daemon = subprocess.run(["docker", "info"], capture_output=True, timeout=5)
    if daemon.returncode != 0:
        return False
    image = subprocess.run(
        ["docker", "image", "inspect", IMAGE_TAG], capture_output=True, timeout=5
    )
    return image.returncode == 0


def test_exit_zero_is_passed():
    assert _classify(0, 3) == STATUS_PASSED


def test_exit_124_is_timeout():
    assert _classify(124, None) == STATUS_TIMEOUT


def test_failed_assertion_is_failed():
    assert _classify(1, 3) == STATUS_FAILED


def test_load_error_is_error():
    assert _classify(1, None) == STATUS_ERROR


def test_timeout_is_authoritative_even_with_zero_test_summary():
    assert _classify(124, 0) == STATUS_TIMEOUT


@pytest.mark.parametrize(
    ("stdout", "reason"),
    [
        ("0 runs, 0 assertions, 0 failures, 0 errors, 0 skips\n", "test summary missing"),
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


@pytest.mark.parametrize(
    ("stdout", "stderr"),
    [
        ("3 runs, 9 assertions, 0 failures, 0 errors, 0 skips", ""),
        ("", "3 runs, 9 assertions, 0 failures, 0 errors, 0 skips"),
    ],
)
def test_run_sample_rejects_forged_output_when_exit_bypasses_reporter(
    tmp_path, monkeypatch, stdout, stderr
):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    task = Task("001_test", task_dir, "prompt", "minitest", "test.rb", "test source")
    sample = Sample(0, 'puts "forged"; exit! 0', 0, 0)
    monkeypatch.setattr(
        "ruby_llm_eval.evaluate.subprocess.run",
        lambda *_args, **_kwargs: subprocess.CompletedProcess(["docker", "run"], 0, stdout, stderr),
    )

    result = run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("test summary missing\n")


@pytest.mark.parametrize("framework", ["minitest", "rspec"])
def test_run_sample_accepts_nonce_bound_reporter_evidence(tmp_path, monkeypatch, framework):
    task_dir = tmp_path / "task"
    task_dir.mkdir()
    filename = "test.rb" if framework == "minitest" else "spec.rb"
    task = Task("001_test", task_dir, "prompt", framework, filename, "test source")
    sample = Sample(0, "def answer = 42", 0, 0)

    def fake_run(cmd, **_kwargs):
        result_mount = next(arg for arg in cmd if arg.endswith(":/rle-result:rw"))
        result_dir = result_mount.removesuffix(":/rle-result:rw")
        nonce_arg = next(arg for arg in cmd if arg.startswith("RLE_RESULT_NONCE="))
        nonce = nonce_arg.partition("=")[2]
        (type(tmp_path)(result_dir) / "result.json").write_text(
            f'{{"nonce":"{nonce}","test_count":2}}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, "candidate output", "")

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    result = run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_PASSED


@pytest.mark.parametrize("framework,filename", [("minitest", "test.rb"), ("rspec", "spec.rb")])
def test_run_sample_stages_support_tree_read_only_and_cleans_it(
    tmp_path, monkeypatch, framework, filename
):
    task_dir = tmp_path / "task"
    fixture = task_dir / "support" / "nested" / "record.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"answer":42}\n', encoding="utf-8")
    task = Task("001_test", task_dir, "prompt", framework, filename, "test source")
    sample = Sample(0, "def answer = 42", 0, 0)
    staged_work = None

    def fake_run(cmd, **_kwargs):
        nonlocal staged_work
        work_mount = next(arg for arg in cmd if arg.endswith(":/work:ro"))
        staged_work = type(tmp_path)(work_mount.removesuffix(":/work:ro"))
        assert (staged_work / "support/nested/record.json").read_text(encoding="utf-8") == (
            '{"answer":42}\n'
        )
        assert (staged_work / "support/nested/record.json").stat().st_mode & 0o777 == 0o644
        result_mount = next(arg for arg in cmd if arg.endswith(":/rle-result:rw"))
        nonce = next(arg for arg in cmd if arg.startswith("RLE_RESULT_NONCE=")).partition("=")[2]
        (type(tmp_path)(result_mount.removesuffix(":/rle-result:rw")) / "result.json").write_text(
            f'{{"nonce":"{nonce}","test_count":1}}', encoding="utf-8"
        )
        return subprocess.CompletedProcess(cmd, 0, "", "")

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    assert run_sample(task, sample, scratch_dir=tmp_path / "scratch").status == STATUS_PASSED
    assert staged_work is not None and not staged_work.exists()


@pytest.mark.skipif(not _docker_sandbox_ready(), reason="Docker sandbox image unavailable")
@pytest.mark.parametrize(
    ("framework", "filename", "test_source"),
    [
        (
            "minitest",
            "test.rb",
            'require "minitest/autorun"\nrequire_relative "solution"\n'
            "class AnswerTest < Minitest::Test\n"
            '  def test_answer; assert_equal "42", File.read("support/answer.txt").strip; '
            "assert_equal 42, answer; end\n"
            "end\n",
        ),
        (
            "rspec",
            "spec.rb",
            'require_relative "solution"\nRSpec.describe "answer" do\n'
            '  it("is 42") { expect(File.read("support/answer.txt").strip).to eq("42"); '
            "expect(answer).to eq(42) }\nend\n",
        ),
    ],
)
def test_run_sample_executes_generated_framework_reporter(
    tmp_path, framework, filename, test_source
):
    fixture = tmp_path / "support" / "answer.txt"
    fixture.parent.mkdir(exist_ok=True)
    fixture.write_text("42\n", encoding="utf-8")
    task = Task("001_test", tmp_path, "prompt", framework, filename, test_source)
    sample = Sample(0, "def answer = 42", 0, 0)

    result = run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_PASSED


def test_run_sample_cleans_work_dir_when_result_dir_creation_fails(tmp_path, monkeypatch):
    task = Task("001_test", tmp_path, "prompt", "minitest", "test.rb", "test source")
    sample = Sample(0, "def answer = 42", 0, 0)
    real_mkdtemp = __import__("tempfile").mkdtemp
    calls = 0

    def fail_second_mkdtemp(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise OSError("result directory unavailable")
        return real_mkdtemp(*args, **kwargs)

    monkeypatch.setattr("ruby_llm_eval.evaluate.tempfile.mkdtemp", fail_second_mkdtemp)

    with pytest.raises(OSError, match="result directory unavailable"):
        run_sample(task, sample, scratch_dir=tmp_path / "scratch")

    assert not list((tmp_path / "scratch").iterdir())


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
