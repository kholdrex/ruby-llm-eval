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


def _report(summaries, *, k=1, input_tokens=0, output_tokens=0, style_enabled=False):
    return build_report(
        model="demo-model",
        provider="stub",
        n=summaries[0]["n"] if summaries else 1,
        k=k,
        temperature=0.2,
        timeout=10,
        task_set_version="0.2.0",
        task_summaries=summaries,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        pricing=PRICING,
        timestamp="20990101T000000",
        style_enabled=style_enabled,
    )


def test_summarize_task_counts_statuses():
    summary = summarize_task("001_x", _results(["passed", "failed", "passed"]), n=3)
    assert summary["passed"] == 2
    assert abs(summary["pass_at_k"] - 2 / 3) < 1e-9
    assert summary["status_counts"]["failed"] == 1
    assert summary["status_counts"]["timeout"] == 0


def test_summarize_task_pass_at_k_for_k_gt_1():
    # 1 of 5 passing, pass@2 = 1 - C(4,2)/C(5,2) = 0.4
    summary = summarize_task(
        "x", _results(["passed", "failed", "failed", "failed", "failed"]), n=5, k=2
    )
    assert abs(summary["pass_at_k"] - 0.4) < 1e-9


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
    report = _report(summaries)
    assert report["overall_pass_at_k"] == 0.75
    assert report["metric"] == "pass@1"
    assert report["k"] == 1
    assert report["task_set_version"] == "0.2.0"


def test_metric_label_tracks_k():
    summaries = [summarize_task("a", _results(["passed", "failed"]), n=2, k=2)]
    report = _report(summaries, k=2)
    assert report["metric"] == "pass@2"


def test_render_markdown_includes_summary_row():
    summaries = [summarize_task("a", _results(["passed"]), n=1)]
    report = _report(summaries, input_tokens=100, output_tokens=50)
    md = render_markdown(report)
    assert "| Model | pass@1 | Cost |" in md
    assert "`demo-model`" in md
    assert "100.0%" in md


def test_render_markdown_header_reflects_k():
    summaries = [summarize_task("a", _results(["passed", "failed"]), n=2, k=2)]
    md = render_markdown(_report(summaries, k=2))
    assert "| Model | pass@2 | Cost |" in md


def test_style_is_none_when_not_measured():
    summary = summarize_task("a", _results(["passed", "passed"]), n=2)
    assert summary["style"] is None


def test_style_aggregates_offenses():
    # 2 clean (0 offenses), 1 with 3 offenses, 1 unmeasured (None)
    summary = summarize_task("a", _results(["passed"] * 4), n=4, style_offenses=[0, 0, 3, None])
    style = summary["style"]
    assert style["measured"] == 3
    assert style["clean"] == 2
    assert style["clean_rate"] == 0.6667  # round(2/3, 4)
    assert style["avg_offenses"] == 1.0


def test_build_report_overall_clean_rate_and_flag():
    summaries = [
        summarize_task("a", _results(["passed", "passed"]), n=2, style_offenses=[0, 0]),
        summarize_task("b", _results(["passed", "passed"]), n=2, style_offenses=[0, 4]),
    ]
    report = _report(summaries, style_enabled=True)
    assert report["style_enabled"] is True
    # clean rates 1.0 and 0.5 -> mean 0.75
    assert report["overall_clean_rate"] == 0.75


def test_categories_breakdown():
    summaries = [
        summarize_task("a", _results(["passed", "passed"]), n=2, category="rails"),
        summarize_task("b", _results(["passed", "failed"]), n=2, category="rails"),
        summarize_task("c", _results(["passed", "passed"]), n=2, category="general"),
    ]
    report = _report(summaries)
    cats = report["categories"]
    assert cats["rails"]["tasks"] == 2
    assert cats["rails"]["pass_at_k"] == 0.75  # mean(1.0, 0.5)
    assert cats["general"]["pass_at_k"] == 1.0


def test_render_markdown_adds_clean_column_when_styled():
    summaries = [summarize_task("a", _results(["passed"]), n=1, style_offenses=[0])]
    md = render_markdown(_report(summaries, style_enabled=True))
    assert "| Model | pass@1 | clean | Cost |" in md
    assert "clean | passed/N" in md
