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


def _summarize_style(style_offenses: list[int | None] | None) -> dict | None:
    """Aggregate per-sample RuboCop offense counts into a style summary.

    Returns None when style was not measured. ``clean`` counts offence-free
    samples; ``clean_rate`` and ``avg_offenses`` are None if nothing linted.
    """
    if style_offenses is None:
        return None
    counted = [o for o in style_offenses if o is not None]
    if not counted:
        return {"measured": 0, "clean": 0, "clean_rate": None, "avg_offenses": None}
    clean = sum(1 for o in counted if o == 0)
    return {
        "measured": len(counted),
        "clean": clean,
        "clean_rate": round(clean / len(counted), 4),
        "avg_offenses": round(sum(counted) / len(counted), 2),
    }


def summarize_task(
    task_id: str,
    results: list[SampleResult],
    n: int,
    k: int = 1,
    style_offenses: list[int | None] | None = None,
    category: str = "general",
) -> dict:
    """Per-task pass@k, a breakdown of sample statuses, and optional style."""
    statuses = [r.status for r in results]
    passed = statuses.count(STATUS_PASSED)
    return {
        "task_id": task_id,
        "category": category,
        "n": n,
        "passed": passed,
        "pass_at_k": pass_at_k(n, passed, k),
        "status_counts": {s: statuses.count(s) for s in STATUSES},
        "style": _summarize_style(style_offenses),
    }


def _summarize_categories(task_summaries: list[dict]) -> dict:
    """Aggregate per-task results into per-category pass@k and clean rates."""
    groups: dict[str, list[dict]] = {}
    for task in task_summaries:
        groups.setdefault(task.get("category", "general"), []).append(task)

    summary = {}
    for category, items in sorted(groups.items()):
        pass_rates = [t["pass_at_k"] for t in items]
        clean_rates = [
            t["style"]["clean_rate"]
            for t in items
            if t.get("style") and t["style"]["clean_rate"] is not None
        ]
        summary[category] = {
            "tasks": len(items),
            "pass_at_k": round(sum(pass_rates) / len(pass_rates), 4),
            "clean_rate": round(sum(clean_rates) / len(clean_rates), 4) if clean_rates else None,
        }
    return summary


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
    style_enabled: bool = False,
    evaluation_mode: str = "sandbox",
    sandboxed: bool = True,
) -> dict:
    overall = (
        sum(t["pass_at_k"] for t in task_summaries) / len(task_summaries) if task_summaries else 0.0
    )
    clean_rates = [
        t["style"]["clean_rate"]
        for t in task_summaries
        if t.get("style") and t["style"]["clean_rate"] is not None
    ]
    overall_clean = round(sum(clean_rates) / len(clean_rates), 4) if clean_rates else None
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
        "style_enabled": style_enabled,
        "evaluation_mode": evaluation_mode,
        "sandboxed": sandboxed,
        "overall_clean_rate": overall_clean,
        "categories": _summarize_categories(task_summaries),
        "tasks": task_summaries,
        "cost": compute_cost(input_tokens, output_tokens, model, pricing),
    }


def _fmt_cost(cost: dict) -> str:
    if not cost["priced"]:
        return "n/a (no pricing)"
    return f"${cost['usd']:.4f}"


def _clean_pct(rate: float | None) -> str:
    return f"{rate * 100:.0f}%" if rate is not None else "n/a"


def render_markdown(report: dict) -> str:
    """A copy-pasteable summary plus a per-task breakdown.

    When style scoring is enabled, a ``clean`` column (RuboCop offence-free
    rate) is added to both tables.
    """
    metric = report["metric"]  # e.g. "pass@1" or "pass@3"
    cost = _fmt_cost(report["cost"])
    overall_pct = f"{report['overall_pass_at_k'] * 100:.1f}%"
    style_on = report.get("style_enabled")
    warning = []
    if report.get("evaluation_mode") == "offline_stub" or report.get("sandboxed") is False:
        warning = [
            "⚠️ **OFFLINE STUB REPORT — NOT A REAL SANDBOXED EVALUATION.**",
            "",
            "Docker was bypassed, `sandboxed` is false, and reported pass rates only "
            "reflect deterministic stub/reference-sample plumbing.",
            "Do not compare this output with real model or Docker sandbox correctness results.",
            "",
        ]

    if style_on:
        clean = _clean_pct(report.get("overall_clean_rate"))
        summary = [
            f"| Model | {metric} | clean | Cost |",
            "| --- | --- | --- | --- |",
            f"| `{report['model']}` | {overall_pct} | {clean} | {cost} |",
        ]
        per_task_head = [
            f"| Task | {metric} | clean | passed/N | failed | timeout | error |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    else:
        summary = [
            f"| Model | {metric} | Cost |",
            "| --- | --- | --- |",
            f"| `{report['model']}` | {overall_pct} | {cost} |",
        ]
        per_task_head = [
            f"| Task | {metric} | passed/N | failed | timeout | error |",
            "| --- | --- | --- | --- | --- | --- |",
        ]

    categories = report.get("categories", {})
    category_block: list[str] = []
    if len(categories) > 1:
        category_block.append("**By category**")
        category_block.append("")
        if style_on:
            category_block.append(f"| Category | tasks | {metric} | clean |")
            category_block.append("| --- | --- | --- | --- |")
            for name, data in categories.items():
                category_block.append(
                    f"| {name} | {data['tasks']} | {data['pass_at_k'] * 100:.0f}% "
                    f"| {_clean_pct(data['clean_rate'])} |"
                )
        else:
            category_block.append(f"| Category | tasks | {metric} |")
            category_block.append("| --- | --- | --- |")
            for name, data in categories.items():
                category_block.append(
                    f"| {name} | {data['tasks']} | {data['pass_at_k'] * 100:.0f}% |"
                )
        category_block.append("")

    lines = [
        f"### ruby-llm-eval results — `{report['model']}`",
        "",
        f"Task set `v{report['task_set_version']}` · "
        f"N={report['n']} · k={report['k']} · temperature={report['temperature']}",
        "",
        *warning,
        *summary,
        "",
        *category_block,
        "<details><summary>Per-task breakdown</summary>",
        "",
        *per_task_head,
    ]
    for task in report["tasks"]:
        counts = task["status_counts"]
        cells = [f"`{task['task_id']}`", f"{task['pass_at_k'] * 100:.0f}%"]
        if style_on:
            style = task.get("style") or {}
            cells.append(_clean_pct(style.get("clean_rate")))
        cells += [
            f"{task['passed']}/{task['n']}",
            str(counts[STATUS_FAILED]),
            str(counts[STATUS_TIMEOUT]),
            str(counts[STATUS_ERROR]),
        ]
        lines.append("| " + " | ".join(cells) + " |")
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
