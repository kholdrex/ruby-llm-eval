"""Assemble a reproducible JSON report and a shareable markdown table."""

from __future__ import annotations

import json
from pathlib import Path

from .evaluate import (
    STATUS_ERROR,
    STATUS_FAILED,
    STATUS_PASSED,
    STATUS_TIMEOUT,
    SampleResult,
)
from .pass_k import pass_at_k

STATUSES = (STATUS_PASSED, STATUS_FAILED, STATUS_TIMEOUT, STATUS_ERROR)


def summarize_task(task_id: str, results: list[SampleResult], n: int, k: int = 1) -> dict:
    """Per-task pass@k plus a breakdown of sample statuses."""
    statuses = [r.status for r in results]
    passed = statuses.count(STATUS_PASSED)
    return {
        "task_id": task_id,
        "n": n,
        "passed": passed,
        "pass_at_k": pass_at_k(n, passed, k),
        "status_counts": {s: statuses.count(s) for s in STATUSES},
    }


def compute_cost(input_tokens: int, output_tokens: int, model: str, pricing: dict) -> dict:
    """Estimate USD cost from token counts and configs/pricing.yaml."""
    entry = pricing.get(model)
    base = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    if not entry:
        return {**base, "usd": None, "priced": False}
    usd = input_tokens / 1_000_000 * entry["input"] + output_tokens / 1_000_000 * entry["output"]
    return {**base, "usd": round(usd, 6), "priced": True}


def build_report(
    *,
    model: str,
    provider: str,
    n: int,
    k: int,
    temperature: float,
    timeout: int,
    task_set_version: str,
    task_summaries: list[dict],
    input_tokens: int,
    output_tokens: int,
    pricing: dict,
    timestamp: str,
) -> dict:
    overall = (
        sum(t["pass_at_k"] for t in task_summaries) / len(task_summaries) if task_summaries else 0.0
    )
    return {
        "schema_version": 2,
        "timestamp": timestamp,
        "model": model,
        "provider": provider,
        "n": n,
        "k": k,
        "temperature": temperature,
        "timeout_seconds": timeout,
        "task_set_version": task_set_version,
        "metric": f"pass@{k}",
        "overall_pass_at_k": round(overall, 4),
        "tasks": task_summaries,
        "cost": compute_cost(input_tokens, output_tokens, model, pricing),
    }


def _fmt_cost(cost: dict) -> str:
    if not cost["priced"]:
        return "n/a (no pricing)"
    return f"${cost['usd']:.4f}"


def render_markdown(report: dict) -> str:
    """A copy-pasteable summary plus a per-task breakdown."""
    metric = report["metric"]  # e.g. "pass@1" or "pass@3"
    cost = _fmt_cost(report["cost"])
    overall_pct = f"{report['overall_pass_at_k'] * 100:.1f}%"

    lines = [
        f"### ruby-llm-eval results — `{report['model']}`",
        "",
        f"Task set `v{report['task_set_version']}` · "
        f"N={report['n']} · k={report['k']} · temperature={report['temperature']}",
        "",
        f"| Model | {metric} | Cost |",
        "| --- | --- | --- |",
        f"| `{report['model']}` | {overall_pct} | {cost} |",
        "",
        "<details><summary>Per-task breakdown</summary>",
        "",
        f"| Task | {metric} | passed/N | failed | timeout | error |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for task in report["tasks"]:
        counts = task["status_counts"]
        lines.append(
            f"| `{task['task_id']}` "
            f"| {task['pass_at_k'] * 100:.0f}% "
            f"| {task['passed']}/{task['n']} "
            f"| {counts[STATUS_FAILED]} "
            f"| {counts[STATUS_TIMEOUT]} "
            f"| {counts[STATUS_ERROR]} |"
        )
    lines += ["", "</details>", ""]
    return "\n".join(lines)


def write_reports(report: dict, out_dir: Path, timestamp: str) -> tuple[Path, Path]:
    """Write run_<timestamp>.json and run_<timestamp>.md; return both paths."""
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"run_{timestamp}.json"
    md_path = out_dir / f"run_{timestamp}.md"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    return json_path, md_path
