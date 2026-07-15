"""Run candidate solutions inside a locked-down Docker sandbox.

SAFETY: model-generated code is never executed on the host. Each sample runs in
a throwaway container with:

- ``--network none``        no network access
- read-only mounted code    the work directory is mounted read-only
- non-root user             the image runs as an unprivileged user
- no capabilities           all Linux capabilities are dropped
- no privilege escalation  ``no-new-privileges`` is enforced
- ``--memory`` / ``--cpus`` resource caps
- ``--pids-limit``          fork-bomb protection
- capped result tmpfs       test evidence is bounded and validated on export
- per-test timeout          enforced inside (coreutils ``timeout``) and outside

Each sample gets one of four statuses: ``passed``, ``failed``, ``timeout``,
``error``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from .generate import Sample
from .tasks import Task

IMAGE_TAG = "ruby-llm-eval-sandbox:latest"

FRAMEWORKS = {
    "minitest": {"command": ["ruby"]},
    "rspec": {"command": ["rspec"]},
}

# coreutils `timeout` exits 124 when it has to kill the command.
_TIMEOUT_EXIT_CODE = 124
_RESULT_TMPFS_SIZE = "1m"
_RESULT_MAX_BYTES = 16 * 1024
_RESULT_EXPORT_TIMEOUT = 5
_RESULT_EXPORT_REJECTED = 65
_RESULT_EXPORT_INFRA_EXIT_CODES = frozenset({125, 127})
_RESULT_EXPORT_RUBY_BINARY = "/usr/local/bin/ruby"
_CREATE_TIMEOUT_CLEANUP_ATTEMPTS = 11
_CREATE_TIMEOUT_CLEANUP_INTERVAL = 0.5
_CONTAINER_CLEANUP_BUDGET = 5.0

# Do not use ``docker cp`` here. Its archive extraction can materialize an
# attacker-controlled symlink on the host before host-side validation gets a
# chance to inspect it. This helper runs from the image's trusted Ruby runtime,
# opens only the expected path without following links or blocking on a FIFO,
# validates the opened descriptor with fstat, and emits at most the byte limit.
_RESULT_EXPORT_RUBY = r"""
path = ARGV.fetch(0)
limit = Integer(ARGV.fetch(1), 10)
io = nil
begin
  flags = File::RDONLY | File::NOFOLLOW | File::NONBLOCK
  io = IO.new(IO.sysopen(path, flags), "rb")
  stat = io.stat
  raise "artifact is not a regular file" unless stat.file?
  raise "artifact exceeds #{limit} bytes" if stat.size > limit
  bytes = io.read(limit + 1) || "".b
  raise "artifact exceeds #{limit} bytes" if bytes.bytesize > limit
  final_stat = io.stat
  raise "artifact changed type while reading" unless final_stat.file?
  raise "artifact exceeds #{limit} bytes" if final_stat.size > limit
  STDOUT.binmode
  STDOUT.write(bytes)
rescue Errno::ELOOP
  warn "result evidence rejected: artifact is a symbolic link"
  exit 65
rescue SystemCallError => error
  warn "result evidence rejected: #{error.class.name}"
  exit 65
rescue RuntimeError => error
  warn "result evidence rejected: #{error.message}"
  exit 65
ensure
  io&.close
end
"""


def _is_missing_container_error(stderr: str | bytes | None, container: str) -> bool:
    """Recognize only Docker's benign response when ``rm -f`` finds no container."""
    if isinstance(stderr, bytes):
        stderr = stderr.decode(errors="replace")
    if not isinstance(stderr, str):
        return False

    message = stderr.strip()
    daemon_prefix = "Error response from daemon: "
    if message.startswith(daemon_prefix):
        message = message.removeprefix(daemon_prefix)
    return message in {"No such container", f"No such container: {container}"}


_MINITEST_EVIDENCE_REPORTER = r"""require "json"
require "minitest"

class RleEvidenceReporter < Minitest::AbstractReporter
  def initialize; super; @count = 0; end
  def record(result); @count += 1; end
  def report
    File.write(ENV.fetch("RLE_RESULT_FILE"), JSON.generate(
      {"nonce" => ENV.fetch("RLE_RESULT_NONCE"), "test_count" => @count}))
  end
end

module Minitest
  extensions << "rle_evidence"
  def self.plugin_rle_evidence_init(options)
    reporter << RleEvidenceReporter.new
  end
end
"""

_RSPEC_EVIDENCE_FORMATTER = r"""require "json"

class RleEvidenceFormatter
  RSpec::Core::Formatters.register self, :example_finished, :close
  def initialize(output); @count = 0; end
  def example_finished(notification); @count += 1; end
  def close(notification)
    File.write(ENV.fetch("RLE_RESULT_FILE"), JSON.generate(
      {"nonce" => ENV.fetch("RLE_RESULT_NONCE"), "test_count" => @count}))
  end
end
"""

STATUS_PASSED = "passed"
STATUS_FAILED = "failed"
STATUS_TIMEOUT = "timeout"
STATUS_ERROR = "error"


@dataclass
class SampleResult:
    task_id: str
    index: int
    status: str
    stderr: str = ""


def docker_available() -> bool:
    return shutil.which("docker") is not None


def image_exists(image: str = IMAGE_TAG) -> bool:
    result = subprocess.run(
        ["docker", "image", "inspect", image],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def build_image(dockerfile_dir: Path, image: str = IMAGE_TAG) -> None:
    """Build the sandbox image from sandbox/Dockerfile."""
    subprocess.run(
        ["docker", "build", "-t", image, str(dockerfile_dir)],
        check=True,
    )


def ensure_image(dockerfile_dir: Path, image: str = IMAGE_TAG) -> None:
    if not image_exists(image):
        build_image(dockerfile_dir, image)


def _classify(returncode: int, test_count: int | None) -> str:
    if returncode == _TIMEOUT_EXIT_CODE:
        return STATUS_TIMEOUT
    if test_count is None or test_count == 0:
        return STATUS_ERROR
    return STATUS_PASSED if returncode == 0 else STATUS_FAILED


def _test_execution_error(test_count: int | None) -> str:
    return "zero tests ran" if test_count == 0 else "test summary missing"


def _export_result_evidence(container: str) -> tuple[bytes | None, str | None]:
    """Return bounded, descriptor-validated evidence from the live container.

    The project image installs Ruby at the fixed path below and its root-owned,
    read-only image layers keep that executable outside candidate control. Run
    the helper as root so persistent uid-1000 candidate descendants cannot send
    it signals, and suppress Ruby's environment-controlled startup/load hooks.
    """
    cmd = [
        "docker",
        "exec",
        "--user",
        "0:0",
        "--env",
        "RUBYOPT=",
        "--env",
        "RUBYLIB=",
        container,
        _RESULT_EXPORT_RUBY_BINARY,
        "--disable=gems,rubyopt",
        "-e",
        _RESULT_EXPORT_RUBY,
        "/rle-result/result.json",
        str(_RESULT_MAX_BYTES),
    ]
    try:
        proc = subprocess.run(cmd, capture_output=True, timeout=_RESULT_EXPORT_TIMEOUT)
    except subprocess.TimeoutExpired:
        return None, f"result evidence export timed out after {_RESULT_EXPORT_TIMEOUT}s"

    if proc.returncode == 0:
        # Retain a host-side invariant in case a future helper edit weakens its bound.
        if len(proc.stdout) > _RESULT_MAX_BYTES:
            return None, f"result evidence exceeds {_RESULT_MAX_BYTES} bytes"
        return proc.stdout, None
    if proc.returncode == _RESULT_EXPORT_REJECTED:
        detail = proc.stderr.decode("utf-8", errors="replace").strip()
        return None, detail[:500] or "result evidence rejected"
    # Docker's reserved 125 remains an infrastructure failure. Exit 127 also
    # means infrastructure here: the absolute Ruby executable is in a root-owned
    # read-only image layer, outside candidate control. Exit 126 is deliberately
    # *not* infrastructure: candidate descendants can exhaust the container's
    # PID allowance and make OCI exporter startup fail with that status. Contain
    # it (like signal-style 137 and other exporter failures) to this sample.
    if proc.returncode in _RESULT_EXPORT_INFRA_EXIT_CODES:
        raise subprocess.CalledProcessError(
            proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
        )
    detail = proc.stderr.decode("utf-8", errors="replace").strip()[:500]
    reason = f"result evidence exporter exited with status {proc.returncode}"
    return None, f"{reason}: {detail}" if detail else reason


def _docker_sandbox_options(container, work, *, memory, cpus, env=None):
    options = [
        "--name",
        container,
        "--network",
        "none",
        "--cap-drop",
        "ALL",
        "--security-opt",
        "no-new-privileges",
        "--memory",
        memory,
        "--cpus",
        str(cpus),
        "--pids-limit",
        "128",
        "--read-only",
        "--tmpfs",
        "/tmp:size=64m",
        "--tmpfs",
        f"/rle-result:size={_RESULT_TMPFS_SIZE}",
        "-e",
        "HOME=/tmp",
        "-v",
        f"{work}:/work:ro",
        "-w",
        "/work",
    ]
    for key, value in (env or {}).items():
        options += ["-e", f"{key}={value}"]
    return options


def _docker_cmd(
    container, image, work, *, timeout, memory, cpus, inner, env=None, auto_remove=True
):
    """Build the locked-down ``docker run`` command wrapping ``inner`` (argv)."""
    cmd = ["docker", "run"]
    if auto_remove:
        cmd.append("--rm")
    return [
        *cmd,
        *_docker_sandbox_options(container, work, memory=memory, cpus=cpus, env=env),
        image,
        "timeout",
        f"{timeout}s",
        *inner,
    ]


def _docker_create_cmd(container, image, work, *, memory, cpus, env=None):
    """Build a sandbox container that stays alive while evidence is exported."""
    # The test is launched separately with ``docker exec`` so the result tmpfs
    # remains mounted for validated export after the test command exits.
    return [
        "docker",
        "create",
        *_docker_sandbox_options(container, work, memory=memory, cpus=cpus, env=env),
        image,
        "tail",
        "-f",
        "/dev/null",
    ]


def run_sample(
    task: Task,
    sample: Sample,
    *,
    image: str = IMAGE_TAG,
    timeout: int = 10,
    memory: str = "256m",
    cpus: float = 1.0,
    scratch_dir: Path | None = None,
) -> SampleResult:
    """Evaluate a single candidate solution inside the sandbox.

    ``scratch_dir`` is where the per-sample work directory (mounted read-only
    into the container) is created. It must live somewhere your container
    runtime is allowed to bind-mount: on Docker Desktop (macOS/Windows) the
    system temp dir is *not* shared by default, so we keep scratch inside the
    project tree rather than using ``/tmp``.
    """
    if sample.error:
        return SampleResult(task.id, sample.index, STATUS_ERROR, sample.error)
    if not sample.code.strip():
        return SampleResult(task.id, sample.index, STATUS_ERROR, "empty completion")

    scratch_root = Path(scratch_dir) if scratch_dir else Path.cwd() / ".rle_sandbox"
    scratch_root.mkdir(parents=True, exist_ok=True)
    # Absolute path: `docker -v` requires an absolute bind-mount source, and the
    # output dir (hence scratch_dir) is often a relative path like "results".
    work = Path(tempfile.mkdtemp(prefix="rle_", dir=str(scratch_root))).resolve()
    container = None
    container_cleanup_required = False
    create_outcome_ambiguous = False
    primary_result = None
    try:
        solution = work / "solution.rb"
        test = work / task.test_filename
        reporter = work / "rle_evidence.rb"
        solution.write_text(sample.code, encoding="utf-8")
        test.write_text(task.test, encoding="utf-8")
        reporter.write_text(
            _MINITEST_EVIDENCE_REPORTER
            if task.framework == "minitest"
            else _RSPEC_EVIDENCE_FORMATTER,
            encoding="utf-8",
        )
        if task.support_dir is not None:
            shutil.copytree(task.support_dir, work / "support")

        # The container runs as a non-root user whose uid differs from the host
        # on native Linux. mkdtemp creates the dir as 0700, so without this the
        # container could not read /work and every sample would error. Make the
        # mounted dir and files world-readable.
        work.chmod(0o755)
        solution.chmod(0o644)
        test.chmod(0o644)
        reporter.chmod(0o644)
        support = work / "support"
        if support.is_dir():
            for entry in support.rglob("*"):
                entry.chmod(0o755 if entry.is_dir() else 0o644)
            support.chmod(0o755)

        container = f"rle_{uuid.uuid4().hex}"
        nonce = uuid.uuid4().hex
        if task.framework == "minitest":
            inner = ["ruby", "-r", "/work/rle_evidence.rb", task.test_filename]
        else:
            inner = [
                "rspec",
                "--require",
                "/work/rle_evidence.rb",
                "--format",
                "RleEvidenceFormatter",
                "--format",
                "progress",
                task.test_filename,
            ]
        create_cmd = _docker_create_cmd(
            container,
            image,
            work,
            memory=memory,
            cpus=cpus,
            env={"RLE_RESULT_FILE": "/rle-result/result.json", "RLE_RESULT_NONCE": nonce},
        )

        try:
            create_proc = subprocess.run(
                create_cmd,
                capture_output=True,
                text=True,
                timeout=15,
            )
        except subprocess.TimeoutExpired:
            # The daemon may have created the named container before the client
            # timed out, so cleanup is still required for this ambiguous case.
            container_cleanup_required = True
            create_outcome_ambiguous = True
            raise
        if create_proc.returncode != 0:
            raise subprocess.CalledProcessError(
                create_proc.returncode,
                create_cmd,
                output=create_proc.stdout,
                stderr=create_proc.stderr,
            )
        container_cleanup_required = True

        start_cmd = ["docker", "start", container]
        start_proc = subprocess.run(
            start_cmd,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if start_proc.returncode != 0:
            raise subprocess.CalledProcessError(
                start_proc.returncode,
                start_cmd,
                output=start_proc.stdout,
                stderr=start_proc.stderr,
            )

        exec_cmd = ["docker", "exec", container, "timeout", f"{timeout}s", *inner]
        try:
            proc = subprocess.run(
                exec_cmd,
                capture_output=True,
                text=True,
                # Outer backstop in case the docker client itself hangs.
                timeout=timeout + 15,
            )
        except subprocess.TimeoutExpired:
            primary_result = SampleResult(
                task.id, sample.index, STATUS_TIMEOUT, "host-side timeout"
            )
            return primary_result

        # Docker reserves 125 for client/daemon failures. ``docker exec`` also
        # propagates the test command's status, so 126 and 127 must be judged
        # using framework evidence like any other non-zero test exit.
        if proc.returncode == 125:
            raise subprocess.CalledProcessError(
                proc.returncode, exec_cmd, output=proc.stdout, stderr=proc.stderr
            )

        # A timeout is authoritative and does not require evidence. Otherwise,
        # export only the expected file through the bounded non-following helper.
        evidence_bytes = None
        evidence_error = None
        if proc.returncode != _TIMEOUT_EXIT_CODE:
            evidence_bytes, evidence_error = _export_result_evidence(container)

        # Do not infer execution from output: the trusted task's framework hook
        # records a count in a dedicated result file. The nonce associates that
        # file with this run; it is not a boundary against an adversarial task.
        test_count = None
        try:
            evidence = json.loads(evidence_bytes) if evidence_bytes is not None else {}
            value = evidence.get("test_count")
            if (
                evidence.get("nonce") == nonce
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                test_count = value
        except (ValueError, RecursionError, AttributeError):
            pass
        status = _classify(proc.returncode, test_count)
        output = (proc.stdout + proc.stderr).strip()
        if status == STATUS_ERROR:
            reason = evidence_error or _test_execution_error(test_count)
            stderr = f"{reason}\n{output}" if output else reason
        else:
            stderr = "" if status == STATUS_PASSED else output
        primary_result = SampleResult(task.id, sample.index, status, stderr[:4000])
        return primary_result
    finally:
        cleanup_error = None
        if container_cleanup_required and container is not None:
            cleanup_cmd = ["docker", "rm", "-f", container]
            cleanup_deadline = time.monotonic() + _CONTAINER_CLEANUP_BUDGET
            try:
                attempts = _CREATE_TIMEOUT_CLEANUP_ATTEMPTS if create_outcome_ambiguous else 1
                for attempt in range(attempts):
                    remaining_budget = cleanup_deadline - time.monotonic()
                    if remaining_budget <= 0:
                        break
                    cleanup_proc = subprocess.run(
                        cleanup_cmd,
                        capture_output=True,
                        text=True,
                        timeout=remaining_budget,
                    )
                    missing_container = (
                        cleanup_proc.args == cleanup_cmd
                        and _is_missing_container_error(cleanup_proc.stderr, container)
                    )
                    if cleanup_proc.returncode != 0 and not missing_container:
                        cleanup_error = subprocess.CalledProcessError(
                            cleanup_proc.returncode,
                            cleanup_cmd,
                            output=cleanup_proc.stdout,
                            stderr=cleanup_proc.stderr,
                        )
                        break
                    if not missing_container:
                        break
                    # A timed-out create request can still be in flight in the
                    # daemon. Reconcile for a bounded grace period so a late
                    # named container is removed without retrying forever.
                    if attempt + 1 < attempts:
                        remaining_budget = cleanup_deadline - time.monotonic()
                        if remaining_budget <= 0:
                            break
                        time.sleep(min(_CREATE_TIMEOUT_CLEANUP_INTERVAL, remaining_budget))
            except BaseException as exc:
                cleanup_error = exc
        shutil.rmtree(work, ignore_errors=True)

        if cleanup_error is not None:
            # A pending return has no exception context for Python to retain, so
            # preserve its result directly on the cleanup failure. If evaluation
            # raised, normal exception chaining keeps that failure as context.
            if primary_result is not None:
                cleanup_error.__dict__["primary_result"] = primary_result
            raise cleanup_error


def run_rubocop(
    task: Task,
    sample: Sample,
    *,
    rubocop_config: str,
    image: str = IMAGE_TAG,
    timeout: int = 10,
    memory: str = "256m",
    cpus: float = 1.0,
    scratch_dir: Path | None = None,
) -> int | None:
    """Return a sample's RuboCop offense count, or None if it could not be linted.

    Style is an axis independent of correctness; this only lints the candidate
    inside the sandbox, it never executes it. RuboCop exits non-zero when it
    finds offenses, so we ignore the exit code and parse the JSON summary.
    """
    if sample.error or not sample.code.strip():
        return None

    scratch_root = Path(scratch_dir) if scratch_dir else Path.cwd() / ".rle_sandbox"
    scratch_root.mkdir(parents=True, exist_ok=True)
    work = Path(tempfile.mkdtemp(prefix="rle_rc_", dir=str(scratch_root))).resolve()
    try:
        solution = work / "solution.rb"
        config = work / ".rubocop.yml"
        solution.write_text(sample.code, encoding="utf-8")
        config.write_text(rubocop_config, encoding="utf-8")
        work.chmod(0o755)
        solution.chmod(0o644)
        config.chmod(0o644)

        container = f"rle_rc_{uuid.uuid4().hex[:12]}"
        cmd = _docker_cmd(
            container,
            image,
            work,
            timeout=timeout,
            memory=memory,
            cpus=cpus,
            inner=["rubocop", "--cache", "false", "--format", "json", "solution.rb"],
        )
        try:
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout + 15)
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", container], capture_output=True)
            return None

        if proc.returncode == 125:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
            )

        try:
            data = json.loads(proc.stdout)
            return int(data["summary"]["offense_count"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
