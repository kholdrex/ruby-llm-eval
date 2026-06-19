from ruby_llm_eval.evaluate import SampleResult
from ruby_llm_eval.report import (
    build_report,
    compute_cost,
    render_markdown,
    summarize_task,
)

PRICING = {"demo-model": {"input": 1.0, "output": 2.0}}


def _results(statuses):
    return [SampleResult("t", i, s) for i, s in enumerate(statuses)]


def test_summarize_task_counts_statuses():
    summary = summarize_task("001_x", _results(["passed", "failed", "passed"]), n=3)
    assert summary["passed"] == 2
    assert abs(summary["pass@1"] - 2 / 3) < 1e-9
    assert summary["status_counts"]["failed"] == 1
    assert summary["status_counts"]["timeout"] == 0


def test_compute_cost_known_model():
    cost = compute_cost(1_000_000, 500_000, "demo-model", PRICING)
    assert cost["priced"] is True
    assert cost["usd"] == 1.0 * 1.0 + 0.5 * 2.0


def test_compute_cost_unknown_model_is_unpriced():
    cost = compute_cost(10, 10, "mystery", PRICING)
    assert cost["priced"] is False
    assert cost["usd"] is None


def test_build_report_overall_is_mean_of_tasks():
    summaries = [
        summarize_task("a", _results(["passed", "passed"]), n=2),
        summarize_task("b", _results(["passed", "failed"]), n=2),
    ]
    report = build_report(
        model="demo-model",
        provider="stub",
        n=2,
        temperature=0.2,
        timeout=10,
        task_set_version="0.1.0",
        task_summaries=summaries,
        input_tokens=0,
        output_tokens=0,
        pricing=PRICING,
        timestamp="20990101T000000",
    )
    assert report["overall_pass@1"] == 0.75
    assert report["metric"] == "pass@1"
    assert report["task_set_version"] == "0.1.0"


def test_render_markdown_includes_summary_row():
    summaries = [summarize_task("a", _results(["passed"]), n=1)]
    report = build_report(
        model="demo-model",
        provider="stub",
        n=1,
        temperature=0.2,
        timeout=10,
        task_set_version="0.1.0",
        task_summaries=summaries,
        input_tokens=100,
        output_tokens=50,
        pricing=PRICING,
        timestamp="20990101T000000",
    )
    md = render_markdown(report)
    assert "| Model | pass@1 | Cost |" in md
    assert "`demo-model`" in md
    assert "100.0%" in md
