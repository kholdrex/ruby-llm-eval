import os
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from ruby_llm_eval.evaluate import (
    _RESULT_EXPORT_RUBY,
    _RESULT_MAX_BYTES,
    IMAGE_TAG,
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    _classify,
    _docker_create_cmd,
    _export_result_evidence,
    run_sample,
)
from ruby_llm_eval.generate import Sample
from ruby_llm_eval.tasks import Task


class DockerSandbox:
    """Stateful Docker orchestration fake that preserves tmpfs lifecycle rules."""

    def __init__(
        self,
        *,
        evidence="valid",
        exec_returncode=0,
        export_returncode=0,
        failures=(),
        exec_timeout=False,
    ):
        self.evidence = evidence
        self.exec_returncode = exec_returncode
        self.export_returncode = export_returncode
        self.failures = set(failures)
        self.exec_timeout = exec_timeout
        self.calls = []
        self.state = None
        self.container = None
        self.env = {}
        self.work = None
        self.tmpfs_result = None

    @property
    def operations(self):
        return ["export" if self._is_export(call) else call[1] for call in self.calls]

    @staticmethod
    def _is_export(cmd):
        return cmd[1:4] == ["exec", "--user", "0:0"]

    def _result(self, cmd, operation, stdout="", stderr=""):
        if operation in self.failures:
            return subprocess.CompletedProcess(
                cmd,
                125 if operation in {"exec", "export"} else 1,
                stdout,
                f"{operation} failed",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout, stderr)

    def _write_tmpfs_evidence(self):
        if self.evidence == "valid":
            self.tmpfs_result = f'{{"nonce":"{self.env["RLE_RESULT_NONCE"]}","test_count":2}}'
        elif self.evidence == "zero":
            self.tmpfs_result = f'{{"nonce":"{self.env["RLE_RESULT_NONCE"]}","test_count":0}}'
        elif self.evidence == "wrong_nonce":
            self.tmpfs_result = '{"nonce":"wrong","test_count":2}'
        elif self.evidence == "malformed":
            self.tmpfs_result = "not json"
        elif self.evidence == "missing":
            self.tmpfs_result = None
        else:
            raise AssertionError(f"unknown evidence mode: {self.evidence}")

    def __call__(self, cmd, **kwargs):
        self.calls.append(cmd)
        operation = cmd[1]

        if operation == "create":
            assert self.state is None
            assert kwargs["timeout"] == 15
            assert cmd[-3:] == ["tail", "-f", "/dev/null"]
            self.container = cmd[cmd.index("--name") + 1]
            assert re.fullmatch(r"rle_[0-9a-f]{32}", self.container)
            assert "/rle-result:size=1m" in [
                cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--tmpfs"
            ]
            assert [cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--cap-drop"] == [
                "ALL"
            ]
            assert [cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--security-opt"] == [
                "no-new-privileges"
            ]
            assert not any(arg.endswith(":/rle-result:rw") for arg in cmd)
            self.env = {
                cmd[index + 1].partition("=")[0]: cmd[index + 1].partition("=")[2]
                for index, arg in enumerate(cmd)
                if arg == "-e" and "=" in cmd[index + 1]
            }
            mount = next(arg for arg in cmd if arg.endswith(":/work:ro"))
            self.work = Path(mount.removesuffix(":/work:ro"))
            result = self._result(cmd, operation)
            if result.returncode == 0:
                self.state = "created"
            return result

        if operation == "start":
            assert cmd == ["docker", "start", self.container]
            assert self.state == "created"
            result = self._result(cmd, operation)
            if result.returncode == 0:
                self.state = "running"
            return result

        if operation == "exec":
            assert self.state == "running"
            if self._is_export(cmd):
                assert kwargs == {"capture_output": True, "timeout": 5}
                assert cmd[:10] == [
                    "docker",
                    "exec",
                    "--user",
                    "0:0",
                    "--env",
                    "RUBYOPT=",
                    "--env",
                    "RUBYLIB=",
                    self.container,
                    "/usr/local/bin/ruby",
                ]
                assert cmd[10:13] == ["--disable=gems,rubyopt", "-e", _RESULT_EXPORT_RUBY]
                assert cmd[13:] == ["/rle-result/result.json", str(_RESULT_MAX_BYTES)]
                result = self._result(cmd, "export")
                if result.returncode:
                    return subprocess.CompletedProcess(
                        cmd, result.returncode, b"", result.stderr.encode()
                    )
                if self.export_returncode:
                    return subprocess.CompletedProcess(
                        cmd, self.export_returncode, b"", b"exporter terminated"
                    )
                if self.tmpfs_result is None:
                    return subprocess.CompletedProcess(
                        cmd, 65, b"", b"result evidence rejected: Errno::ENOENT\n"
                    )
                return subprocess.CompletedProcess(cmd, 0, self.tmpfs_result.encode(), b"")
            assert cmd[2] == self.container
            assert cmd[3:5] == ["timeout", "10s"]
            if self.exec_timeout:
                raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
            result = self._result(cmd, operation, stdout="candidate output")
            if result.returncode:
                return result
            self._write_tmpfs_evidence()
            return subprocess.CompletedProcess(
                cmd, self.exec_returncode, "candidate output", "candidate warning"
            )

        if operation == "rm":
            assert cmd == ["docker", "rm", "-f", self.container]
            result = self._result(cmd, operation)
            if result.returncode == 0:
                self.state = "removed"
            return result

        raise AssertionError(f"unexpected Docker command: {cmd}")


def _task(tmp_path, framework="minitest"):
    filename = "test.rb" if framework == "minitest" else "spec.rb"
    return Task("001_test", tmp_path, "prompt", framework, filename, "test source")


def _sample(index=0):
    return Sample(index, "def answer = 42", 0, 0)


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


@pytest.mark.parametrize(
    ("returncode", "test_count", "expected"),
    [
        (0, 3, STATUS_PASSED),
        (124, None, STATUS_TIMEOUT),
        (1, 3, STATUS_FAILED),
        (1, None, STATUS_ERROR),
        (124, 0, STATUS_TIMEOUT),
    ],
)
def test_classify(returncode, test_count, expected):
    assert _classify(returncode, test_count) == expected


def test_docker_create_uses_locked_down_tmpfs_without_writable_result_mount(tmp_path):
    cmd = _docker_create_cmd(
        "rle_0123456789abcdef0123456789abcdef",
        IMAGE_TAG,
        tmp_path,
        memory="256m",
        cpus=1.0,
    )

    assert cmd[:2] == ["docker", "create"]
    assert cmd[-3:] == ["tail", "-f", "/dev/null"]
    assert "--rm" not in cmd
    assert [cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--cap-drop"] == ["ALL"]
    assert [cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--security-opt"] == [
        "no-new-privileges"
    ]
    assert [cmd[index + 1] for index, arg in enumerate(cmd) if arg == "--tmpfs"] == [
        "/tmp:size=64m",
        "/rle-result:size=1m",
    ]
    assert not any("/rle-result:rw" in arg for arg in cmd)


def test_export_command_uses_distinct_uid_fixed_ruby_and_sanitized_startup(monkeypatch):
    captured = None

    def fake_run(cmd, **kwargs):
        nonlocal captured
        captured = cmd
        assert kwargs == {"capture_output": True, "timeout": 5}
        return subprocess.CompletedProcess(cmd, 65, b"", b"result evidence rejected")

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    assert _export_result_evidence("rle_container") == (None, "result evidence rejected")
    assert captured == [
        "docker",
        "exec",
        "--user",
        "0:0",
        "--env",
        "RUBYOPT=",
        "--env",
        "RUBYLIB=",
        "rle_container",
        "/usr/local/bin/ruby",
        "--disable=gems,rubyopt",
        "-e",
        _RESULT_EXPORT_RUBY,
        "/rle-result/result.json",
        str(_RESULT_MAX_BYTES),
    ]


def _run_export_helper(path):
    return subprocess.run(
        ["ruby", "-e", _RESULT_EXPORT_RUBY, str(path), str(_RESULT_MAX_BYTES)],
        capture_output=True,
        timeout=2,
    )


def test_result_export_helper_accepts_normal_evidence_and_ignores_extra_contents(tmp_path):
    evidence = b'{"nonce":"abc","test_count":2}'
    (tmp_path / "result.json").write_bytes(evidence)
    (tmp_path / "attacker-extra").write_bytes(b"must not be exported")

    proc = _run_export_helper(tmp_path / "result.json")

    assert proc.returncode == 0
    assert proc.stdout == evidence
    assert b"must not be exported" not in proc.stdout


@pytest.mark.parametrize("target", ["/dev/zero", "real-result.json"])
def test_result_export_helper_rejects_absolute_and_relative_symlinks(tmp_path, target):
    if not target.startswith("/"):
        (tmp_path / target).write_bytes(b"{}")
    (tmp_path / "result.json").symlink_to(target)

    proc = _run_export_helper(tmp_path / "result.json")

    assert proc.returncode == 65
    assert b"symbolic link" in proc.stderr
    assert proc.stdout == b""


def test_result_export_helper_rejects_fifo_without_blocking(tmp_path):
    artifact = tmp_path / "result.json"
    os.mkfifo(artifact)

    proc = _run_export_helper(artifact)

    assert proc.returncode == 65
    assert b"not a regular file" in proc.stderr


def test_result_export_helper_rejects_device():
    proc = _run_export_helper("/dev/null")

    assert proc.returncode == 65
    assert b"not a regular file" in proc.stderr


def test_result_export_helper_rejects_oversized_sparse_file(tmp_path):
    artifact = tmp_path / "result.json"
    with artifact.open("wb") as stream:
        stream.truncate(_RESULT_MAX_BYTES + 1)

    proc = _run_export_helper(artifact)

    assert proc.returncode == 65
    assert str(_RESULT_MAX_BYTES).encode() in proc.stderr
    assert proc.stdout == b""


@pytest.mark.parametrize("framework", ["minitest", "rspec"])
def test_success_orders_create_start_exec_export_rm_and_targets_test_command(
    tmp_path, monkeypatch, framework
):
    docker = DockerSandbox()
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path, framework), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_PASSED
    assert docker.operations == ["create", "start", "exec", "export", "rm"]
    exec_cmd = docker.calls[2]
    if framework == "minitest":
        assert exec_cmd[5:] == ["ruby", "-r", "/work/rle_evidence.rb", "test.rb"]
    else:
        assert exec_cmd[5:] == [
            "rspec",
            "--require",
            "/work/rle_evidence.rb",
            "--format",
            "RleEvidenceFormatter",
            "--format",
            "progress",
            "spec.rb",
        ]


@pytest.mark.parametrize("evidence", ["missing", "malformed", "wrong_nonce"])
def test_missing_or_invalid_evidence_is_a_test_execution_error(tmp_path, monkeypatch, evidence):
    docker = DockerSandbox(evidence=evidence)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    expected_reason = (
        "result evidence rejected" if evidence == "missing" else "test summary missing"
    )
    assert result.stderr.startswith(expected_reason)
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


def test_zero_test_evidence_has_specific_error(tmp_path, monkeypatch):
    docker = DockerSandbox(evidence="zero")
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("zero tests ran")


@pytest.mark.parametrize("operation", ["create", "start", "exec", "export"])
def test_docker_lifecycle_failure_is_infrastructure_error_and_container_is_removed(
    tmp_path, monkeypatch, operation
):
    docker = DockerSandbox(failures={operation})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    expected_command_operation = "exec" if operation == "export" else operation
    assert exc_info.value.cmd[1] == expected_command_operation
    expected_stderr = f"{operation} failed"
    actual_stderr = exc_info.value.stderr
    if isinstance(actual_stderr, bytes):
        actual_stderr = actual_stderr.decode()
    assert actual_stderr == expected_stderr
    prefixes = {
        "create": ["create", "rm"],
        "start": ["create", "start", "rm"],
        "exec": ["create", "start", "exec", "rm"],
        "export": ["create", "start", "exec", "export", "rm"],
    }
    assert docker.operations == prefixes[operation]


def test_exec_docker_exit_125_is_infrastructure_error(tmp_path, monkeypatch):
    docker = DockerSandbox(exec_returncode=125)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert exc_info.value.returncode == 125
    assert exc_info.value.cmd[:3] == ["docker", "exec", docker.container]
    assert docker.operations == ["create", "start", "exec", "rm"]


def test_unexpected_exporter_exit_is_sample_error_and_container_is_removed(tmp_path, monkeypatch):
    docker = DockerSandbox(export_returncode=137, failures={"rm"})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith(
        "result evidence exporter exited with status 137: exporter terminated"
    )
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


@pytest.mark.parametrize("returncode", [125, 127])
def test_reserved_export_docker_failure_is_infrastructure_error_and_cleans_up(
    tmp_path, monkeypatch, returncode
):
    docker = DockerSandbox(export_returncode=returncode)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert exc_info.value.returncode == returncode
    assert exc_info.value.cmd[:4] == ["docker", "exec", "--user", "0:0"]
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


def test_export_exit_126_is_sample_error_and_container_is_removed(tmp_path, monkeypatch):
    docker = DockerSandbox(export_returncode=126, failures={"rm"})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith(
        "result evidence exporter exited with status 126: exporter terminated"
    )
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


@pytest.mark.parametrize("framework", ["minitest", "rspec"])
@pytest.mark.parametrize("returncode", [126, 127])
def test_exec_exit_126_or_127_with_valid_evidence_is_failed_test(
    tmp_path, monkeypatch, framework, returncode
):
    docker = DockerSandbox(exec_returncode=returncode)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path, framework), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_FAILED
    assert "candidate output" in result.stderr
    assert "candidate warning" in result.stderr
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


@pytest.mark.parametrize("returncode", [126, 127])
def test_exec_exit_126_or_127_without_evidence_is_test_execution_error(
    tmp_path, monkeypatch, returncode
):
    docker = DockerSandbox(exec_returncode=returncode, evidence="missing")
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("result evidence rejected: Errno::ENOENT\ncandidate output")
    assert "candidate warning" in result.stderr
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


def test_host_side_exec_timeout_skips_export_and_forcibly_removes_container(tmp_path, monkeypatch):
    docker = DockerSandbox(exec_timeout=True)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_TIMEOUT
    assert result.stderr == "host-side timeout"
    assert docker.operations == ["create", "start", "exec", "rm"]


def test_inner_timeout_is_authoritative_and_skips_export(tmp_path, monkeypatch):
    docker = DockerSandbox(exec_returncode=124, evidence="missing")
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_TIMEOUT
    assert docker.operations == ["create", "start", "exec", "rm"]


def test_failed_test_uses_evidence_and_reports_candidate_output(tmp_path, monkeypatch):
    docker = DockerSandbox(exec_returncode=1)
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_FAILED
    assert "candidate output" in result.stderr
    assert "candidate warning" in result.stderr
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


def test_rm_failure_after_success_is_infrastructure_error(tmp_path, monkeypatch):
    docker = DockerSandbox(failures={"rm"})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert exc_info.value.cmd == ["docker", "rm", "-f", docker.container]
    assert exc_info.value.stderr == "rm failed"


@pytest.mark.parametrize(
    ("evidence", "exec_returncode", "expected"),
    [("malformed", 0, STATUS_ERROR), ("valid", 1, STATUS_FAILED)],
)
def test_rm_failure_does_not_mask_primary_test_failure(
    tmp_path, monkeypatch, evidence, exec_returncode, expected
):
    docker = DockerSandbox(evidence=evidence, exec_returncode=exec_returncode, failures={"rm"})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == expected


def test_rm_failure_does_not_mask_primary_infrastructure_failure(tmp_path, monkeypatch):
    docker = DockerSandbox(failures={"export", "rm"})
    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)

    with pytest.raises(subprocess.CalledProcessError) as exc_info:
        run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert exc_info.value.cmd[:4] == ["docker", "exec", "--user", "0:0"]
    assert exc_info.value.stderr == b"export failed"


def test_support_tree_is_staged_read_only_and_cleaned(tmp_path, monkeypatch):
    fixture = tmp_path / "support" / "nested" / "record.json"
    fixture.parent.mkdir(parents=True)
    fixture.write_text('{"answer":42}\n', encoding="utf-8")
    docker = DockerSandbox()

    def fake_run(cmd, **kwargs):
        result = docker(cmd, **kwargs)
        if cmd[1] == "create":
            assert docker.work is not None
            staged = docker.work / "support" / "nested" / "record.json"
            assert staged.read_text(encoding="utf-8") == '{"answer":42}\n'
            assert staged.stat().st_mode & 0o777 == 0o644
        return result

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_PASSED
    assert docker.work is not None
    assert not docker.work.exists()
    assert not list((tmp_path / "scratch").glob("rle_*"))


def test_missing_summary_reason_precedes_bounded_candidate_output(tmp_path, monkeypatch):
    docker = DockerSandbox(evidence="missing")

    def fake_run(cmd, **kwargs):
        result = docker(cmd, **kwargs)
        if cmd[1] == "exec":
            return subprocess.CompletedProcess(cmd, 0, "runner stopped\n" + "x" * 5000, "warning")
        return result

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("test summary missing\nrunner stopped")
    assert len(result.stderr) == 4000


def test_result_export_timeout_is_error_and_container_is_removed(tmp_path, monkeypatch):
    docker = DockerSandbox(failures={"rm"})

    def timeout_export(cmd, **kwargs):
        if DockerSandbox._is_export(cmd):
            docker.calls.append(cmd)
            raise subprocess.TimeoutExpired(cmd, kwargs["timeout"])
        return docker(cmd, **kwargs)

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", timeout_export)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("result evidence export timed out after 5s")
    assert docker.operations == ["create", "start", "exec", "export", "rm"]


def test_host_work_result_file_is_not_accepted_as_container_evidence(tmp_path, monkeypatch):
    docker = DockerSandbox(evidence="missing")

    def fake_run(cmd, **kwargs):
        result = docker(cmd, **kwargs)
        if cmd[1] == "exec":
            assert docker.work is not None
            (docker.work / "result.json").write_text(
                f'{{"nonce":"{docker.env["RLE_RESULT_NONCE"]}","test_count":99}}',
                encoding="utf-8",
            )
        return result

    monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", fake_run)

    result = run_sample(_task(tmp_path), _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_ERROR
    assert result.stderr.startswith("result evidence rejected")


def test_container_names_are_unique_safe_full_uuids(tmp_path, monkeypatch):
    names = []

    for index in range(2):
        docker = DockerSandbox(evidence="missing")
        monkeypatch.setattr("ruby_llm_eval.evaluate.subprocess.run", docker)
        result = run_sample(_task(tmp_path), _sample(index), scratch_dir=tmp_path / "scratch")
        assert result.status == STATUS_ERROR
        names.append(docker.container)

    assert len(set(names)) == 2
    assert all(re.fullmatch(r"rle_[0-9a-f]{32}", name) for name in names)


@pytest.mark.skipif(
    os.environ.get("RLE_RUN_DOCKER_PID_EXHAUSTION") != "1" or not _docker_sandbox_ready(),
    reason="opt-in Docker PID-exhaustion regression unavailable",
)
def test_live_pid_exhaustion_export_failure_is_contained_and_cleaned_up(tmp_path, monkeypatch):
    container = "rle_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(
        "ruby_llm_eval.evaluate.uuid.uuid4",
        lambda: type("FixedUuid", (), {"hex": container.removeprefix("rle_")})(),
    )
    task = Task(
        "001_pid_exhaustion",
        tmp_path,
        "prompt",
        "minitest",
        "test.rb",
        'require "minitest/autorun"\nrequire_relative "solution"\n'
        "class AnswerTest < Minitest::Test\n"
        "  def test_answer; assert_equal 42, answer; end\n"
        "end\n",
    )
    sample = Sample(
        0,
        "fork do\n"
        "  loop do\n"
        "    begin\n"
        "      fork { sleep 60 }\n"
        "    rescue Errno::EAGAIN\n"
        "      sleep 0.001\n"
        "    end\n"
        "  end\n"
        "end\n"
        "def answer = 42\n",
        0,
        0,
    )

    try:
        result = run_sample(task, sample, timeout=5, scratch_dir=tmp_path / "scratch")
        assert result.status == STATUS_ERROR
        assert "result evidence exporter exited with status 126" in result.stderr
    finally:
        # A second cleanup guard keeps this destructive opt-in regression safe
        # even if orchestration regresses before run_sample's finally block.
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=15)

    inspect = subprocess.run(
        ["docker", "container", "inspect", container], capture_output=True, timeout=5
    )
    assert inspect.returncode != 0


@pytest.mark.skipif(not _docker_sandbox_ready(), reason="Docker sandbox image unavailable")
@pytest.mark.parametrize(
    ("framework", "filename", "test_source"),
    [
        (
            "minitest",
            "test.rb",
            'require "minitest/autorun"\nrequire_relative "solution"\n'
            "class AnswerTest < Minitest::Test\n"
            "  def test_answer; assert_equal 42, answer; end\n"
            "end\n",
        ),
        (
            "rspec",
            "spec.rb",
            'require_relative "solution"\nRSpec.describe "answer" do\n'
            '  it("is 42") { expect(answer).to eq(42) }\nend\n',
        ),
    ],
)
def test_run_sample_executes_generated_framework_reporter(
    tmp_path, framework, filename, test_source
):
    task = Task("001_test", tmp_path, "prompt", framework, filename, test_source)

    result = run_sample(task, _sample(), scratch_dir=tmp_path / "scratch")

    assert result.status == STATUS_PASSED
