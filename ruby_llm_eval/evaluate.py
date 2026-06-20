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
import re
import shutil
import subprocess
import tempfile
import uuid
from dataclasses import dataclass
from pathlib import Path

from .generate import Sample
from .tasks import Task

IMAGE_TAG = "ruby-llm-eval-sandbox:latest"

# Each framework prints a one-line summary when it actually runs — Minitest
# "3 runs, 9 assertions, ..." or RSpec "5 examples, 1 failure". Its presence
# means a non-zero exit is a real test failure; its absence means the file blew
# up before testing (a load/syntax error). `command` is how the test file is
# executed inside the container.
FRAMEWORKS = {
    "minitest": {
        "command": ["ruby"],
        "summary": re.compile(r"\d+ runs?, \d+ assertions?"),
    },
    "rspec": {
        "command": ["rspec"],
        "summary": re.compile(r"\d+ examples?, \d+ failures?"),
    },
}

# coreutils `timeout` exits 124 when it has to kill the command.
_TIMEOUT_EXIT_CODE = 124

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


def _classify(returncode: int, stdout: str, stderr: str, summary_re: re.Pattern) -> str:
    if returncode == 0:
        return STATUS_PASSED
    if returncode == _TIMEOUT_EXIT_CODE:
        return STATUS_TIMEOUT
    if summary_re.search(stdout + "\n" + stderr):
        return STATUS_FAILED
    return STATUS_ERROR


def _docker_cmd(container, image, work, *, timeout, memory, cpus, inner):
    """Build the locked-down ``docker run`` command wrapping ``inner`` (argv)."""
    return [
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

    framework = FRAMEWORKS[task.framework]

    scratch_root = Path(scratch_dir) if scratch_dir else Path.cwd() / ".rle_sandbox"
    scratch_root.mkdir(parents=True, exist_ok=True)
    # Absolute path: `docker -v` requires an absolute bind-mount source, and the
    # output dir (hence scratch_dir) is often a relative path like "results".
    work = Path(tempfile.mkdtemp(prefix="rle_", dir=str(scratch_root))).resolve()
    try:
        solution = work / "solution.rb"
        test = work / task.test_filename
        solution.write_text(sample.code, encoding="utf-8")
        test.write_text(task.test, encoding="utf-8")

        # The container runs as a non-root user whose uid differs from the host
        # on native Linux. mkdtemp creates the dir as 0700, so without this the
        # container could not read /work and every sample would error. Make the
        # mounted dir and files world-readable.
        work.chmod(0o755)
        solution.chmod(0o644)
        test.chmod(0o644)

        container = f"rle_{uuid.uuid4().hex[:12]}"
        cmd = _docker_cmd(
            container,
            image,
            work,
            timeout=timeout,
            memory=memory,
            cpus=cpus,
            inner=[*framework["command"], task.test_filename],
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

        status = _classify(proc.returncode, proc.stdout, proc.stderr, framework["summary"])
        stderr = "" if status == STATUS_PASSED else (proc.stdout + proc.stderr).strip()
        return SampleResult(task.id, sample.index, status, stderr[:4000])
    finally:
        shutil.rmtree(work, ignore_errors=True)


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

        try:
            data = json.loads(proc.stdout)
            return int(data["summary"]["offense_count"])
        except (json.JSONDecodeError, KeyError, TypeError, ValueError):
            return None
    finally:
        shutil.rmtree(work, ignore_errors=True)
