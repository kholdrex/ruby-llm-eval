"""Command-line entrypoint: ``ruby-llm-eval run --model <name> ...``."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .config import (
    find_config_dir,
    find_sandbox_dir,
    find_tasks_dir,
    load_pricing,
    load_providers,
    load_rubocop_config,
)
from .evaluate import (
    IMAGE_TAG,
    STATUS_ERROR,
    STATUS_PASSED,
    SampleResult,
    docker_available,
    ensure_image,
    image_exists,
    run_rubocop,
    run_sample,
)
from .generate import PROMPT_TEMPLATE, Sample, generate_for_task, safe_model_dir
from .model_client import DEFAULT_MAX_TOKENS, build_client
from .report import build_report, summarize_task, write_reports
from .tasks import discover_tasks, read_version

# ANSI status glyphs (degrade gracefully — they are just decoration).
_GLYPH = {"passed": "✓", "failed": "✗", "timeout": "⏱", "error": "!"}
DOCKER_INFO_TIMEOUT_SECONDS = 5


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def _validate_sandbox_limits(args: argparse.Namespace) -> bool:
    """Reject invalid Docker limits before provider loading or Docker setup."""
    if args.timeout < 1:
        _eprint(f"Error: --timeout must be >= 1 (got {args.timeout}).")
        return False
    if not math.isfinite(args.cpus) or args.cpus <= 0:
        _eprint(f"Error: --cpus must be > 0 (got {args.cpus}).")
        return False
    if not re.fullmatch(r"[1-9]\d*[bkmg]?", args.memory, re.IGNORECASE):
        _eprint(
            f"Error: --memory must be a positive integer with optional b/k/m/g suffix "
            f"(got {args.memory!r})."
        )
        return False
    return True


def _report_docker_failure(stage: str, exc: subprocess.SubprocessError | OSError) -> None:
    """Print a concise diagnostic for Docker client/build launch failures."""
    detail = ""
    if isinstance(exc, subprocess.CalledProcessError):
        output = exc.stderr or exc.stdout
        if output:
            detail = str(output).strip()
    if not detail:
        detail = str(exc)
    _eprint(f"Error: Docker sandbox {stage} failed: {detail}")


def _process_sample(task, sample, *, timeout, memory, cpus, scratch_dir, rubocop_config):
    """Evaluate a sample for correctness and, if requested, RuboCop style."""
    result = run_sample(
        task, sample, timeout=timeout, memory=memory, cpus=cpus, scratch_dir=scratch_dir
    )
    offenses = None
    if rubocop_config is not None:
        offenses = run_rubocop(
            task,
            sample,
            rubocop_config=rubocop_config,
            timeout=timeout,
            memory=memory,
            cpus=cpus,
            scratch_dir=scratch_dir,
        )
    return result, offenses


def _evaluate_samples(task, samples, *, timeout, memory, cpus, scratch_dir, jobs, rubocop_config):
    """Run a task's samples in the sandbox, optionally in parallel.

    Each sample is fully isolated (its own work dir + container name), so
    concurrent runs are safe. ``pool.map`` preserves order, so results stay
    aligned with ``samples``. Returns a list of ``(SampleResult, offenses)``.
    """

    def run_one(sample):
        return _process_sample(
            task,
            sample,
            timeout=timeout,
            memory=memory,
            cpus=cpus,
            scratch_dir=scratch_dir,
            rubocop_config=rubocop_config,
        )

    if jobs <= 1 or len(samples) <= 1:
        return [run_one(sample) for sample in samples]
    with ThreadPoolExecutor(max_workers=min(jobs, len(samples))) as pool:
        return list(pool.map(run_one, samples))


def _evaluate_stub_samples(task, samples):
    """Return deterministic no-Docker results for the offline stub provider."""
    pairs = []
    for sample in samples:
        status = STATUS_ERROR if sample.error else STATUS_PASSED
        stderr = sample.error or ""
        pairs.append((SampleResult(task.id, sample.index, status, stderr), None))
    return pairs


def cmd_run(args: argparse.Namespace) -> int:
    if args.offline_stub and args.style:
        _eprint(
            "Error: --offline-stub cannot be combined with --style; style scoring requires Docker."
        )
        return 2
    if args.offline_stub and (args.provider != "stub" or args.model != "stub"):
        _eprint("Error: --offline-stub requires --provider stub --model stub.")
        return 2
    if not args.offline_stub and not _validate_sandbox_limits(args):
        return 2

    if args.offline_stub:
        config_dir = None
        providers = {"stub": {"type": "stub"}}
        pricing = {"stub": {"input": 0.0, "output": 0.0}}
    else:
        config_dir = find_config_dir(args.config_dir)
        providers = load_providers(config_dir)
        pricing = load_pricing(config_dir)

    if args.n < 1:
        _eprint(f"Error: -n/--samples must be >= 1 (got {args.n}).")
        return 2
    if args.max_tokens < 1:
        _eprint("Error: --max-tokens must be >= 1.")
        return 2
    if args.k < 1 or args.k > args.n:
        _eprint(f"Error: -k must be between 1 and -n/--samples ({args.n}); got {args.k}.")
        return 2
    if args.jobs < 1:
        _eprint(f"Error: --jobs must be >= 1 (got {args.jobs}).")
        return 2
    jobs = args.jobs

    tasks_dir = find_tasks_dir(args.tasks)
    tasks = discover_tasks(tasks_dir, only=args.task or None)
    task_set_version = read_version(tasks_dir)

    client = build_client(
        args.provider,
        args.model,
        providers,
        base_url=args.base_url,
        api_key=args.api_key,
    )
    offline_stub = args.offline_stub

    if not offline_stub and not docker_available():
        _eprint(
            "Error: Docker is required to run evaluations safely but was not "
            "found on PATH. Install Docker Desktop or the Docker Engine and "
            "try again."
        )
        return 2

    rubocop_config = None
    if args.style:
        rubocop_config = load_rubocop_config(config_dir)
        if rubocop_config is None:
            _eprint("Error: --style needs configs/rubocop.yml but it was not found.")
            return 2

    if offline_stub:
        _eprint(
            "Offline stub provider: skipping Docker sandbox; "
            "stub reference samples are marked passed."
        )
    else:
        _eprint(f"Building/locating sandbox image {IMAGE_TAG} ...")
        try:
            ensure_image(find_sandbox_dir(args.sandbox, strict_explicit=True))
        except (subprocess.CalledProcessError, OSError) as exc:
            _report_docker_failure("setup", exc)
            return 2

    out_root = Path(args.output)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    run_id = f"{timestamp}_{uuid.uuid4().hex[:8]}"
    run_dir = out_root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=False)
    samples_dir = run_dir / "samples" / safe_model_dir(args.model)
    # Preserve the exact evaluation inputs before generation starts. A task-set
    # version alone cannot identify edits to a private or uncommitted task set.
    snapshot_root = run_dir / "tasks"
    task_hashes = {}
    for task in tasks:
        shutil.copytree(task.path, snapshot_root / task.id)
        for path in sorted((snapshot_root / task.id).rglob("*")):
            if path.is_file():
                key = path.relative_to(snapshot_root).as_posix()
                task_hashes[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    (run_dir / "prompt_template.txt").write_text(PROMPT_TEMPLATE, encoding="utf-8")
    tasks = discover_tasks(snapshot_root)
    manifest = {
        "run_id": run_id,
        "started_at_utc": timestamp,
        "state": "started",
        "package_version": __version__,
        "python_version": sys.version,
        "provider": args.provider,
        "model": args.model,
        "task_set_version": task_set_version,
        "task_sha256": task_hashes,
        "requested_temperature": args.temperature,
        "requested_max_tokens": args.max_tokens,
        "n": args.n,
        "k": args.k,
        "timeout_seconds": args.timeout,
        "memory": args.memory,
        "cpus": args.cpus,
        "jobs": jobs,
        "evaluation_mode": "offline_stub" if offline_stub else "sandbox",
        "pricing": pricing.get(args.model),
        "limitations": [
            "Response metadata records sent settings; provider defaults can remain unknown.",
            "The sandbox image tag is mutable; freeze its digest before research runs.",
        ],
    }
    if rubocop_config:
        (run_dir / "rubocop.yml").write_text(rubocop_config, encoding="utf-8")
    manifest_path = run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    # Sandbox scratch lives inside the output tree so container runtimes can
    # bind-mount it (Docker Desktop does not share the system temp dir). Create
    # it once up front so parallel workers don't race on first creation.
    scratch_dir = run_dir / ".sandbox"
    scratch_dir.mkdir(parents=True, exist_ok=True)

    try:
        _eprint(
            f"\nModel: {args.model}  (provider: {args.provider})\n"
            f"Tasks: {len(tasks)} from {tasks_dir} (v{task_set_version})  "
            f"N={args.n}  k={args.k}  temperature={args.temperature}  "
            f"timeout={args.timeout}s  jobs={jobs}  style={'on' if args.style else 'off'}\n"
        )

        metric = f"pass@{args.k}"

        task_summaries: list[dict] = []
        total_input = 0
        total_output = 0

        for task in tasks:
            samples = generate_for_task(
                client,
                task,
                n=args.n,
                temperature=args.temperature,
                out_dir=samples_dir,
                max_tokens=args.max_tokens,
            )
            total_input += sum(s.input_tokens for s in samples)
            total_output += sum(s.output_tokens for s in samples)

            if offline_stub:
                pairs = _evaluate_stub_samples(task, samples)
            else:
                try:
                    pairs = _evaluate_samples(
                        task,
                        samples,
                        timeout=args.timeout,
                        memory=args.memory,
                        cpus=args.cpus,
                        scratch_dir=scratch_dir,
                        jobs=jobs,
                        rubocop_config=rubocop_config,
                    )
                except (subprocess.SubprocessError, OSError) as exc:
                    _report_docker_failure("process", exc)
                    return 2
            results = [result for result, _ in pairs]
            offenses = [offense for _, offense in pairs] if args.style else None
            # Keep individual outcomes and diagnostics, not only aggregate scores.
            (samples_dir / task.id / "evaluations.json").write_text(
                json.dumps(
                    [{**asdict(result), "style_offenses": offense} for result, offense in pairs],
                    indent=2,
                ),
                encoding="utf-8",
            )
            summary = summarize_task(
                task.id, results, args.n, args.k, style_offenses=offenses, category=task.category
            )
            task_summaries.append(summary)

            glyphs = " ".join(_GLYPH.get(r.status, "?") for r in results)
            line = f"  {task.id:<28} {metric} {summary['pass_at_k'] * 100:5.1f}%  [{glyphs}]"
            style = summary["style"]
            if style and style["clean_rate"] is not None:
                line += f"  clean {style['clean_rate'] * 100:4.0f}%"
            _eprint(line)

        report = build_report(
            model=args.model,
            provider=args.provider,
            n=args.n,
            k=args.k,
            temperature=args.temperature,
            timeout=args.timeout,
            task_set_version=task_set_version,
            task_summaries=task_summaries,
            input_tokens=total_input,
            output_tokens=total_output,
            pricing=pricing,
            timestamp=timestamp,
            style_enabled=args.style,
            evaluation_mode="offline_stub" if offline_stub else "sandbox",
            sandboxed=not offline_stub,
        )
        report["run_id"] = run_id
        report["artifacts_dir"] = run_dir.relative_to(out_root).as_posix()
        json_path, md_path = write_reports(report, out_root, run_id)
        manifest["state"] = "completed"
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)
        if manifest["state"] != "completed":
            manifest["state"] = "interrupted"
        manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    overall = report["overall_pass_at_k"]
    cost = report["cost"]
    cost_str = f"${cost['usd']:.4f}" if cost["priced"] else "n/a (add model to pricing.yaml)"
    summary_line = (
        f"\nOverall {metric}: {overall * 100:.1f}%   "
        f"tokens: {total_input} in / {total_output} out   cost: {cost_str}"
    )
    if args.style and report["overall_clean_rate"] is not None:
        summary_line += f"   clean: {report['overall_clean_rate'] * 100:.1f}%"
    _eprint(summary_line)

    categories = report["categories"]
    if len(categories) > 1:
        for name, data in categories.items():
            line = f"  [{name}] {metric} {data['pass_at_k'] * 100:.1f}% ({data['tasks']} tasks)"
            if args.style and data["clean_rate"] is not None:
                line += f"   clean {data['clean_rate'] * 100:.1f}%"
            _eprint(line)

    _eprint(f"Report: {json_path}")
    _eprint(f"Markdown: {md_path}\n")
    return 0


def cmd_list_tasks(args: argparse.Namespace) -> int:
    tasks_dir = find_tasks_dir(args.tasks)
    tasks = discover_tasks(tasks_dir, only=args.task or None)
    version = read_version(tasks_dir)
    print(f"{len(tasks)} task(s) in {tasks_dir} (v{version}):")
    for task in tasks:
        print(f"  {task.id:<30} {task.framework}")
    return 0


def cmd_validate_tasks(args: argparse.Namespace) -> int:
    """Run task reference solutions against their tests in the Docker sandbox."""
    if not _validate_sandbox_limits(args):
        return 2
    tasks_dir = find_tasks_dir(args.tasks)
    tasks = discover_tasks(tasks_dir, only=args.task or None)
    if not docker_available():
        _eprint(
            "Error: Docker is required to validate task reference solutions safely but was not "
            "found on PATH."
        )
        return 2

    try:
        ensure_image(find_sandbox_dir(args.sandbox, strict_explicit=True))
    except (subprocess.CalledProcessError, OSError) as exc:
        _report_docker_failure("setup", exc)
        return 2
    # Keep scratch under the current directory so Docker Desktop can bind-mount
    # it, but make it unique so cleanup can never remove a user's existing path.
    scratch_dir = Path(tempfile.mkdtemp(prefix=".ruby-llm-eval-validation-", dir=Path.cwd()))
    passed = 0
    try:
        for task in tasks:
            try:
                reference = task.reference()
            except (OSError, UnicodeError) as exc:
                print(f"[FAIL] {task.id}: cannot read solution_ref.rb: {exc}")
                continue
            sample = Sample(index=0, code=reference, input_tokens=0, output_tokens=0)
            try:
                result = run_sample(
                    task,
                    sample,
                    timeout=args.timeout,
                    memory=args.memory,
                    cpus=args.cpus,
                    scratch_dir=scratch_dir,
                )
            except (subprocess.SubprocessError, OSError) as exc:
                _report_docker_failure("process", exc)
                return 2
            if result.status == STATUS_PASSED:
                passed += 1
                print(f"[PASS] {task.id}")
            else:
                detail = result.stderr.strip().splitlines()
                suffix = f": {detail[0]}" if detail else f": {result.status}"
                print(f"[FAIL] {task.id}{suffix}")
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)

    failed = len(tasks) - passed
    print(f"Validated {len(tasks)} task reference solution(s): {passed} passed, {failed} failed.")
    return 0 if failed == 0 else 1


def _doctor_line(label: str, ok: bool, detail: str) -> None:
    status = "OK" if ok else "FAIL"
    print(f"[{status}] {label}: {detail}")


def _docker_readiness() -> tuple[bool, str]:
    docker_path = shutil.which("docker")
    if not docker_path:
        return False, "docker not found on PATH"

    try:
        proc = subprocess.run(
            [docker_path, "info"],
            capture_output=True,
            text=True,
            timeout=DOCKER_INFO_TIMEOUT_SECONDS,
        )
    except subprocess.TimeoutExpired:
        return False, f"docker info timed out after {DOCKER_INFO_TIMEOUT_SECONDS} seconds"
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout).strip().splitlines()
        message = detail[0] if detail else "docker daemon is not ready"
        return False, message

    return True, docker_path


def _validate_pricing(pricing: dict) -> tuple[bool, str]:
    for model, entry in pricing.items():
        if not isinstance(entry, dict):
            return False, f"model '{model}' must map to an object with input/output prices"

        missing = [key for key in ("input", "output") if key not in entry]
        if missing:
            return False, f"model '{model}' is missing {', '.join(missing)} price(s)"

        for key in ("input", "output"):
            value = entry[key]
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                return False, f"model '{model}' has non-numeric {key} price: {value!r}"

    return True, f"{len(pricing)} priced model entries"


def cmd_doctor(args: argparse.Namespace) -> int:
    overall_ok = True
    providers = {}

    try:
        config_dir = find_config_dir(args.config_dir, strict_explicit=True)
        _doctor_line("config", True, str(config_dir))
    except (FileNotFoundError, ValueError) as exc:
        config_dir = None
        overall_ok = False
        _doctor_line("config", False, str(exc))

    if config_dir is not None:
        try:
            providers = load_providers(config_dir)
            provider_names = ", ".join(sorted(providers)) or "none"
            _doctor_line("providers", True, f"{len(providers)} configured ({provider_names})")
        except Exception as exc:
            overall_ok = False
            _doctor_line("providers", False, str(exc))

        try:
            pricing = load_pricing(config_dir)
            pricing_ok, pricing_detail = _validate_pricing(pricing)
            overall_ok = overall_ok and pricing_ok
            _doctor_line("pricing", pricing_ok, pricing_detail)
        except Exception as exc:
            overall_ok = False
            _doctor_line("pricing", False, str(exc))

    try:
        tasks_dir = find_tasks_dir(args.tasks, strict_explicit=True)
        tasks = discover_tasks(tasks_dir)
        version = read_version(tasks_dir)
        _doctor_line("tasks", True, f"{tasks_dir} ({len(tasks)} tasks, v{version})")
    except (FileNotFoundError, ValueError) as exc:
        overall_ok = False
        _doctor_line("tasks", False, str(exc))

    try:
        sandbox_dir = find_sandbox_dir(args.sandbox, strict_explicit=True)
        _doctor_line("sandbox", True, str(sandbox_dir))
    except (FileNotFoundError, ValueError) as exc:
        overall_ok = False
        _doctor_line("sandbox", False, str(exc))

    docker_ok, docker_detail = _docker_readiness()
    if docker_ok:
        _doctor_line("docker", True, docker_detail)
        image_ok = image_exists(IMAGE_TAG)
        image_detail = (
            f"{IMAGE_TAG} present" if image_ok else f"{IMAGE_TAG} missing (will build on first run)"
        )
        _doctor_line("sandbox image", True, image_detail)
    else:
        overall_ok = False
        _doctor_line("docker", False, docker_detail)

    if args.provider:
        if args.provider == "stub":
            _doctor_line("provider stub", True, "no API key required")
        elif args.provider not in providers:
            overall_ok = False
            known = ", ".join(sorted(providers)) or "none"
            _doctor_line("provider", False, f"unknown provider '{args.provider}' (known: {known})")
        else:
            spec = providers[args.provider]
            api_key_env = spec.get("api_key_env")
            if api_key_env:
                env_ok = bool(args.api_key or os.environ.get(api_key_env))
                detail = (
                    f"API key available via --api-key/{api_key_env}"
                    if env_ok
                    else f"set {api_key_env} or pass --api-key"
                )
                overall_ok = overall_ok and env_ok
                _doctor_line(f"provider {args.provider}", env_ok, detail)
            else:
                _doctor_line(f"provider {args.provider}", True, "configured")

    return 0 if overall_ok else 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ruby-llm-eval",
        description="Measure how well an LLM writes Ruby code (pass@k).",
    )
    parser.add_argument("--version", action="version", version=f"ruby-llm-eval {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate + evaluate + report for a model.")
    run.add_argument("--model", required=True, help="Model name, e.g. claude-sonnet-4-6.")
    run.add_argument(
        "--provider",
        default="stub",
        help=(
            "Provider from configs/providers.yaml (default: stub; evaluation still "
            "uses Docker unless --offline-stub is set)."
        ),
    )
    run.add_argument(
        "--tasks",
        help=(
            "Tasks directory (default: nearest usable ./tasks up the tree, "
            "otherwise bundled tasks)."
        ),
    )
    run.add_argument(
        "--task",
        action="append",
        help="Run only this task id (repeatable). Default: all tasks.",
    )
    run.add_argument(
        "-n",
        "--samples",
        dest="n",
        type=int,
        default=5,
        help="Completions per task (default: 5).",
    )
    run.add_argument(
        "-k",
        dest="k",
        type=int,
        default=1,
        help="The k in pass@k; must be <= n (default: 1).",
    )
    run.add_argument(
        "--temperature", type=float, default=0.2, help="Sampling temperature (default: 0.2)."
    )
    run.add_argument(
        "--max-tokens",
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help="Requested output token limit per completion (default: 1024).",
    )
    run.add_argument(
        "--timeout", type=int, default=10, help="Per-test timeout in seconds (default: 10)."
    )
    run.add_argument("--memory", default="256m", help="Container memory limit (default: 256m).")
    run.add_argument("--cpus", type=float, default=1.0, help="Container CPU limit (default: 1.0).")
    run.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="Evaluate this many samples in parallel containers (default: 1).",
    )
    run.add_argument(
        "--style",
        action="store_true",
        help="Also score idiomatic style with RuboCop (needs configs/rubocop.yml).",
    )
    run.add_argument(
        "--offline-stub",
        action="store_true",
        help=(
            "Explicitly bypass Docker only for --provider stub --model stub. "
            "Reports are marked evaluation_mode=offline_stub and sandboxed=false."
        ),
    )
    run.add_argument("--output", default="results", help="Output directory (default: ./results).")
    run.add_argument("--base-url", help="Override the provider base URL.")
    run.add_argument("--api-key", help="Override the API key (prefer env vars).")
    run.add_argument("--config-dir", help="Directory containing providers.yaml + pricing.yaml.")
    run.add_argument("--sandbox", help="Directory containing the sandbox Dockerfile.")
    run.set_defaults(func=cmd_run)

    ls = sub.add_parser("list-tasks", help="List available tasks and their test framework.")
    ls.add_argument(
        "--tasks",
        help=(
            "Tasks directory (default: nearest usable ./tasks up the tree, "
            "otherwise bundled tasks)."
        ),
    )
    ls.add_argument(
        "--task", action="append", help="Show only this task id (repeatable). Default: all."
    )
    ls.set_defaults(func=cmd_list_tasks)

    validate = sub.add_parser(
        "validate-tasks", help="Run task reference solutions against tests safely in Docker."
    )
    validate.add_argument("--tasks", help="Tasks directory to validate instead of auto-discovery.")
    validate.add_argument(
        "--task", action="append", help="Validate only this task id (repeatable). Default: all."
    )
    validate.add_argument(
        "--timeout", type=int, default=10, help="Per-test timeout in seconds (default: 10)."
    )
    validate.add_argument(
        "--memory", default="256m", help="Container memory limit (default: 256m)."
    )
    validate.add_argument(
        "--cpus", type=float, default=1.0, help="Container CPU limit (default: 1.0)."
    )
    validate.add_argument("--sandbox", help="Directory containing the sandbox Dockerfile.")
    validate.set_defaults(func=cmd_validate_tasks)

    doctor = sub.add_parser(
        "doctor", help="Check install/runtime prerequisites and asset discovery."
    )
    doctor.add_argument("--tasks", help="Tasks directory to inspect instead of auto-discovery.")
    doctor.add_argument("--config-dir", help="Directory containing providers.yaml + pricing.yaml.")
    doctor.add_argument("--sandbox", help="Directory containing the sandbox Dockerfile.")
    doctor.add_argument("--provider", help="Optional provider name to verify API-key readiness.")
    doctor.add_argument(
        "--api-key", help="Optional API key override for provider readiness checks."
    )
    doctor.set_defaults(func=cmd_doctor)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (FileNotFoundError, ValueError) as exc:
        _eprint(f"Error: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
