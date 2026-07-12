"""Run candidate solutions inside a locked-down Docker sandbox.

SAFETY: model-generated code is never executed on the host. Each sample runs in
a throwaway container with:

- ``--network none``        no network access
- read-only mounted code    the work directory is mounted read-only
- non-root user             the image runs as an unprivileged user
- ``--memory`` / ``--cpus`` resource caps
- ``--pids-limit``          fork-bomb protection
- per-test timeout          enforced inside (coreutils ``timeout``) and outside

Each sample gets one of four statuses: ``passed``, ``failed``, ``timeout``,
``error``.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
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


def _docker_cmd(container, image, work, *, timeout, memory, cpus, inner, result_dir=None, env=None):
    """Build the locked-down ``docker run`` command wrapping ``inner`` (argv)."""
    cmd = [
        "docker",
        "run",
        "--rm",
        "--name",
        container,
        "--network",
        "none",
        "--memory",
        memory,
        "--cpus",
        str(cpus),
        "--pids-limit",
        "128",
        "--read-only",
        "--tmpfs",
        "/tmp:size=64m",
        "-e",
        "HOME=/tmp",
        "-v",
        f"{work}:/work:ro",
        "-w",
        "/work",
    ]
    if result_dir is not None:
        cmd += ["-v", f"{result_dir}:/rle-result:rw"]
    for key, value in (env or {}).items():
        cmd += ["-e", f"{key}={value}"]
    return cmd + [
        image,
        "timeout",
        f"{timeout}s",
        *inner,
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
    result_dir = None
    try:
        result_dir = Path(tempfile.mkdtemp(prefix="rle_result_", dir=str(scratch_root))).resolve()
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
        result_dir.chmod(0o777)

        container = f"rle_{uuid.uuid4().hex[:12]}"
        nonce = uuid.uuid4().hex
        result_file = result_dir / "result.json"
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
        cmd = _docker_cmd(
            container,
            image,
            work,
            timeout=timeout,
            memory=memory,
            cpus=cpus,
            inner=inner,
            result_dir=result_dir,
            env={"RLE_RESULT_FILE": "/rle-result/result.json", "RLE_RESULT_NONCE": nonce},
        )

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                # Outer backstop in case the docker client itself hangs.
                timeout=timeout + 15,
            )
        except subprocess.TimeoutExpired:
            subprocess.run(["docker", "kill", container], capture_output=True)
            return SampleResult(task.id, sample.index, STATUS_TIMEOUT, "host-side timeout")

        # Docker reserves 125 for failures to invoke the container (for
        # example, an unavailable daemon or an invalid bind mount).  This is
        # infrastructure failure, not a test result, so let CLI callers map it
        # to their infrastructure-error exit code.
        if proc.returncode == 125:
            raise subprocess.CalledProcessError(
                proc.returncode, cmd, output=proc.stdout, stderr=proc.stderr
            )

        # Do not infer execution from output: the trusted task's framework hook
        # records a count in a dedicated result file. The nonce associates that
        # file with this run; it is not a boundary against an adversarial task.
        test_count = None
        try:
            evidence = json.loads(result_file.read_text(encoding="utf-8"))
            value = evidence.get("test_count")
            if (
                evidence.get("nonce") == nonce
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value >= 0
            ):
                test_count = value
        except (OSError, json.JSONDecodeError, AttributeError):
            pass
        status = _classify(proc.returncode, test_count)
        output = (proc.stdout + proc.stderr).strip()
        if status == STATUS_ERROR:
            reason = _test_execution_error(test_count)
            stderr = f"{reason}\n{output}" if output else reason
        else:
            stderr = "" if status == STATUS_PASSED else output
        return SampleResult(task.id, sample.index, status, stderr[:4000])
    finally:
        shutil.rmtree(work, ignore_errors=True)
        if result_dir is not None:
            shutil.rmtree(result_dir, ignore_errors=True)


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
