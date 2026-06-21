"""Command-line entrypoint: ``ruby-llm-eval run --model <name> ...``."""

from __future__ import annotations

import argparse
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
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
    run_rubocop,
    run_sample,
)
from .generate import generate_for_task, safe_model_dir
from .model_client import StubClient, build_client
from .report import build_report, summarize_task, write_reports
from .tasks import discover_tasks, read_version

# ANSI status glyphs (degrade gracefully — they are just decoration).
_GLYPH = {"passed": "✓", "failed": "✗", "timeout": "⏱", "error": "!"}


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


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
    if args.k < 1 or args.k > args.n:
        _eprint(f"Error: -k must be between 1 and -n/--samples ({args.n}); got {args.k}.")
        return 2
    jobs = max(1, args.jobs)

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
    if args.offline_stub and not isinstance(client, StubClient):
        _eprint("Error: --offline-stub requires --provider stub --model stub.")
        return 2
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
        ensure_image(find_sandbox_dir(args.sandbox))

    out_root = Path(args.output)
    samples_dir = out_root / safe_model_dir(args.model)
    # Sandbox scratch lives inside the output tree so container runtimes can
    # bind-mount it (Docker Desktop does not share the system temp dir). Create
    # it once up front so parallel workers don't race on first creation.
    scratch_dir = out_root / ".sandbox"
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
            )
            total_input += sum(s.input_tokens for s in samples)
            total_output += sum(s.output_tokens for s in samples)

            if offline_stub:
                pairs = _evaluate_stub_samples(task, samples)
            else:
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
            results = [result for result, _ in pairs]
            offenses = [offense for _, offense in pairs] if args.style else None
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

        timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
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
        json_path, md_path = write_reports(report, out_root, timestamp)
    finally:
        shutil.rmtree(scratch_dir, ignore_errors=True)

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
