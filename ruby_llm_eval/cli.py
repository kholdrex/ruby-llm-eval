"""Command-line entrypoint: ``ruby-llm-eval run --model <name> ...``."""

from __future__ import annotations

import argparse
import shutil
import sys
from datetime import datetime
from pathlib import Path

from . import __version__
from .config import find_config_dir, find_sandbox_dir, load_pricing, load_providers
from .evaluate import IMAGE_TAG, docker_available, ensure_image, run_sample
from .generate import generate_for_task, safe_model_dir
from .model_client import build_client
from .report import build_report, summarize_task, write_reports
from .tasks import discover_tasks, read_version

# ANSI status glyphs (degrade gracefully — they are just decoration).
_GLYPH = {"passed": "✓", "failed": "✗", "timeout": "⏱", "error": "!"}


def _eprint(*args: object) -> None:
    print(*args, file=sys.stderr)


def cmd_run(args: argparse.Namespace) -> int:
    config_dir = find_config_dir(args.config_dir)
    providers = load_providers(config_dir)
    pricing = load_pricing(config_dir)

    tasks_dir = Path(args.tasks)
    tasks = discover_tasks(tasks_dir, only=args.task or None)
    task_set_version = read_version(tasks_dir)

    if not docker_available():
        _eprint(
            "Error: Docker is required to run evaluations safely but was not "
            "found on PATH. Install Docker Desktop or the Docker Engine and "
            "try again."
        )
        return 2

    _eprint(f"Building/locating sandbox image {IMAGE_TAG} ...")
    ensure_image(find_sandbox_dir(args.sandbox))

    client = build_client(
        args.provider,
        args.model,
        providers,
        base_url=args.base_url,
        api_key=args.api_key,
    )

    out_root = Path(args.output)
    samples_dir = out_root / safe_model_dir(args.model)
    # Sandbox scratch lives inside the output tree so container runtimes can
    # bind-mount it (Docker Desktop does not share the system temp dir).
    scratch_dir = out_root / ".sandbox"

    _eprint(
        f"\nModel: {args.model}  (provider: {args.provider})\n"
        f"Tasks: {len(tasks)} from {tasks_dir} (v{task_set_version})  "
        f"N={args.n}  temperature={args.temperature}  timeout={args.timeout}s\n"
    )

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

        results = [
            run_sample(
                task,
                sample,
                timeout=args.timeout,
                memory=args.memory,
                cpus=args.cpus,
                scratch_dir=scratch_dir,
            )
            for sample in samples
        ]
        summary = summarize_task(task.id, results, args.n)
        task_summaries.append(summary)

        glyphs = " ".join(_GLYPH.get(r.status, "?") for r in results)
        _eprint(f"  {task.id:<28} pass@1 {summary['pass@1'] * 100:5.1f}%  [{glyphs}]")

    timestamp = datetime.now().strftime("%Y%m%dT%H%M%S")
    report = build_report(
        model=args.model,
        provider=args.provider,
        n=args.n,
        temperature=args.temperature,
        timeout=args.timeout,
        task_set_version=task_set_version,
        task_summaries=task_summaries,
        input_tokens=total_input,
        output_tokens=total_output,
        pricing=pricing,
        timestamp=timestamp,
    )
    json_path, md_path = write_reports(report, out_root, timestamp)
    shutil.rmtree(scratch_dir, ignore_errors=True)

    overall = report["overall_pass@1"]
    cost = report["cost"]
    cost_str = f"${cost['usd']:.4f}" if cost["priced"] else "n/a (add model to pricing.yaml)"
    _eprint(
        f"\nOverall pass@1: {overall * 100:.1f}%   "
        f"tokens: {total_input} in / {total_output} out   cost: {cost_str}"
    )
    _eprint(f"Report: {json_path}")
    _eprint(f"Markdown: {md_path}\n")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ruby-llm-eval",
        description="Measure how well an LLM writes Ruby code (pass@1).",
    )
    parser.add_argument("--version", action="version", version=f"ruby-llm-eval {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="Generate + evaluate + report for a model.")
    run.add_argument("--model", required=True, help="Model name, e.g. claude-sonnet-4-6.")
    run.add_argument(
        "--provider",
        default="stub",
        help="Provider from configs/providers.yaml (default: stub, runs offline).",
    )
    run.add_argument("--tasks", default="tasks", help="Tasks directory (default: ./tasks).")
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
        "--temperature", type=float, default=0.2, help="Sampling temperature (default: 0.2)."
    )
    run.add_argument(
        "--timeout", type=int, default=10, help="Per-test timeout in seconds (default: 10)."
    )
    run.add_argument("--memory", default="256m", help="Container memory limit (default: 256m).")
    run.add_argument("--cpus", type=float, default=1.0, help="Container CPU limit (default: 1.0).")
    run.add_argument("--output", default="results", help="Output directory (default: ./results).")
    run.add_argument("--base-url", help="Override the provider base URL.")
    run.add_argument("--api-key", help="Override the API key (prefer env vars).")
    run.add_argument("--config-dir", help="Directory containing providers.yaml + pricing.yaml.")
    run.add_argument("--sandbox", help="Directory containing the sandbox Dockerfile.")
    run.set_defaults(func=cmd_run)
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
