from __future__ import annotations

from typing import Any

from core.utils import now_utc, write_text


def _fmt(value: Any) -> str:
    if isinstance(value, bool):
        return "✅ True" if value else "❌ False"
    if isinstance(value, float):
        return f"{value:.4f}"
    if value is None:
        return "-"
    return str(value)


def _quality_table(quality: dict[str, Any]) -> list[str]:
    lines = [
        "| Expectation | Column | Result | Observed / Unexpected |",
        "| :--- | :--- | :---: | :--- |",
    ]
    for check in quality.get("checks", []):
        if "observed_value" in check:
            observed = f"observed={check['observed_value']}"
        elif "unexpected_count" in check:
            observed = f"unexpected={check['unexpected_count']} ({check.get('unexpected_percent', 0):.1f}%)"
        else:
            observed = check.get("exception", "-")
        lines.append(
            f"| `{check['expectation']}` | {check.get('column') or '(table)'} | {_fmt(check['success'])} | {observed} |"
        )
    return lines


def generate_phase1_report(
    report_path,
    source_summary: dict[str, Any],
    metrics: dict[str, Any],
    quality: dict[str, Any],
    freshness: dict[str, Any],
) -> None:
    """Viet markdown report cho baseline phase: nguon du lieu, metrics, quality gate va freshness."""
    lines = [
        "# Phase 1 Report — Baseline Data Pipeline",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Source & Lineage",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in source_summary.items()]

    lines += [
        "",
        "## 2. Baseline RAG Evaluation",
        "",
        "| Metric | Value |",
        "| :--- | ---: |",
    ]
    for key in ("samples", "retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score"):
        lines.append(f"| {key} | {_fmt(metrics.get(key))} |")
    ragas = metrics.get("ragas")
    if ragas:
        lines.append(f"| ragas | {ragas} |")

    lines += [
        "",
        "## 3. Data Quality Gate (Great Expectations 1.x)",
        "",
        f"- Overall success: **{_fmt(quality.get('success'))}**",
        f"- Expectations passed: {quality.get('successful_expectations')}/{quality.get('evaluated_expectations')}",
        f"- Rows validated: {quality.get('row_count')}",
        "",
        *_quality_table(quality),
        "",
        "## 4. Freshness SLA",
        "",
        f"Rule: `is_fresh = False` when more than {freshness.get('max_stale_ratio', 0.25):.0%} of papers have "
        f"`age_days > {freshness.get('threshold_days')}`.",
        "",
        "| Field | Value |",
        "| :--- | :--- |",
    ]
    lines += [f"| {key} | {_fmt(value)} |" for key, value in freshness.items() if key != "generated_at"]

    lines += [
        "",
        "## 5. Conclusion",
        "",
        (
            "Baseline data passed the quality gate and is fresh; this run is the reference point for the corruption experiment."
            if quality.get("success") and freshness.get("is_fresh")
            else "⚠️ Baseline data did not fully pass the quality gate / freshness SLA — investigate before serving."
        ),
        "",
    ]
    write_text(report_path, "\n".join(lines))


def generate_corruption_report(
    report_path,
    baseline_metrics: dict[str, Any],
    corrupted_metrics: dict[str, Any],
    repaired_metrics: dict[str, Any],
    corrupted_quality: dict[str, Any],
    repaired_quality: dict[str, Any],
    corrupted_freshness: dict[str, Any],
    repaired_freshness: dict[str, Any],
    baseline_quality: dict[str, Any] | None = None,
    baseline_freshness: dict[str, Any] | None = None,
    corruption_log: dict[str, Any] | None = None,
    answers: dict[str, list[dict[str, Any]]] | None = None,
    repair_summary: dict[str, Any] | None = None,
) -> None:
    """Viet markdown report so sanh 3 trang thai Baseline vs Corrupted vs Repaired."""
    baseline_quality = baseline_quality or {}
    baseline_freshness = baseline_freshness or {}

    def delta(new: Any, old: Any) -> str:
        if isinstance(new, (int, float)) and isinstance(old, (int, float)) and not isinstance(new, bool):
            diff = new - old
            return f"{diff:+.4f}" if diff else "0"
        return ""

    metric_keys = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")
    lines = [
        "# Corruption Report — Baseline vs Corrupted vs Repaired",
        "",
        f"_Generated at: {now_utc().isoformat()}_",
        "",
        "## 1. Bảng đối chiếu 3 trạng thái",
        "",
        "| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |",
        "| :--- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for key in ("samples", *metric_keys):
        b, c, r = baseline_metrics.get(key), corrupted_metrics.get(key), repaired_metrics.get(key)
        lines.append(f"| {key} | {_fmt(b)} | {_fmt(c)} | {_fmt(r)} | {delta(c, b)} | {delta(r, b)} |")

    def passed(quality: dict[str, Any]) -> str:
        if not quality:
            return "-"
        return f"{quality.get('successful_expectations')}/{quality.get('evaluated_expectations')}"

    lines += [
        f"| GX quality gate | {_fmt(baseline_quality.get('success'))} | {_fmt(corrupted_quality.get('success'))} "
        f"| {_fmt(repaired_quality.get('success'))} | | |",
        f"| Expectations passed | {passed(baseline_quality)} | {passed(corrupted_quality)} | {passed(repaired_quality)} | | |",
        f"| Rows | {_fmt(baseline_quality.get('row_count'))} | {_fmt(corrupted_quality.get('row_count'))} "
        f"| {_fmt(repaired_quality.get('row_count'))} | | |",
        f"| Freshness is_fresh | {_fmt(baseline_freshness.get('is_fresh'))} | {_fmt(corrupted_freshness.get('is_fresh'))} "
        f"| {_fmt(repaired_freshness.get('is_fresh'))} | | |",
        f"| Stale ratio (age_days > {repaired_freshness.get('threshold_days')}) | {_fmt(baseline_freshness.get('stale_ratio'))} "
        f"| {_fmt(corrupted_freshness.get('stale_ratio'))} | {_fmt(repaired_freshness.get('stale_ratio'))} | | |",
    ]

    if corruption_log:
        lines += [
            "",
            "## 2. Các lỗi đã tiêm (corruption_log.json)",
            "",
            f"Rows: {corruption_log.get('rows_before')} → {corruption_log.get('rows_after')} (seed={corruption_log.get('seed')})",
            "",
            "| # | Corruption | Rows | Description |",
            "| ---: | :--- | ---: | :--- |",
        ]
        for number, entry in enumerate(corruption_log.get("corruptions", []), start=1):
            lines.append(f"| {number} | `{entry['corruption']}` | {entry['affected_rows']} | {entry['description']} |")

    lines += [
        "",
        "## 3. Observability Alert trên dữ liệu lỗi",
        "",
        f"- Quality gate: **{_fmt(corrupted_quality.get('success'))}** — failed expectations:",
    ]
    lines += [f"  - `{name}`" for name in corrupted_quality.get("failed_expectations", [])] or ["  - (none)"]
    lines += [
        f"- Freshness SLA: **{_fmt(corrupted_freshness.get('is_fresh'))}** "
        f"({corrupted_freshness.get('stale_rows')}/{corrupted_freshness.get('total_rows')} stale rows, "
        f"latest_published={corrupted_freshness.get('latest_published')})",
        "",
        *_quality_table(corrupted_quality),
    ]

    if answers:
        baseline_answers = {item["id"]: item for item in answers.get("baseline", [])}
        corrupted_answers = {item["id"]: item for item in answers.get("corrupted", [])}
        repaired_answers = {item["id"]: item for item in answers.get("repaired", [])}
        lines += [
            "",
            "## 4. Tác động theo từng câu hỏi (Token F1 / retrieval hit)",
            "",
            "| ID | Type | Baseline | Corrupted | Repaired | Corrupted answer |",
            "| :--- | :--- | :---: | :---: | :---: | :--- |",
        ]

        def cell(item: dict[str, Any] | None) -> str:
            if not item:
                return "-"
            return f"{item['token_f1']:.2f} / {'hit' if item['retrieval_hit'] else 'miss'}"

        for item_id, base in baseline_answers.items():
            corrupted_item = corrupted_answers.get(item_id)
            answer = (corrupted_item or {}).get("answer", "") or "(empty)"
            answer = answer.replace("|", "\\|")
            answer = answer if len(answer) <= 70 else answer[:67] + "..."
            lines.append(
                f"| {item_id} | {base['question_type']} | {cell(base)} | {cell(corrupted_item)} "
                f"| {cell(repaired_answers.get(item_id))} | {answer} |"
            )

    hit_drop = (baseline_metrics.get("retrieval_hit_rate") or 0) - (corrupted_metrics.get("retrieval_hit_rate") or 0)
    f1_drop = (baseline_metrics.get("mean_token_f1") or 0) - (corrupted_metrics.get("mean_token_f1") or 0)
    recovered = all(
        abs((repaired_metrics.get(key) or 0) - (baseline_metrics.get(key) or 0)) < 1e-9 for key in metric_keys
    )
    lines += [
        "",
        "## 5. Phân tích",
        "",
        f"- **Silent failure:** trên dữ liệu lỗi, pipeline RAG vẫn chạy bình thường và trả lời tự tin, không hề báo lỗi — "
        f"nhưng Hit Rate giảm {hit_drop:.2f} và Token F1 giảm {f1_drop:.2f} so với baseline. "
        "Bài bị drop không còn trong index (retrieval miss); title bị cắt làm exact-lookup thất bại; "
        "summary rỗng/nhiễu và ngày bị lùi tạo ra câu trả lời sai nhưng trông hợp lệ.",
        "- **Observability:** Great Expectations 1.x và Freshness SLA phát hiện ngay các vi phạm "
        "(trùng `paper_id`, summary quá ngắn, title bị cắt, tỷ lệ bài quá hạn vượt ngưỡng) trước khi dữ liệu tới serving layer.",
        f"- **Repair:** tái tạo dữ liệu từ raw snapshot `data/raw/crossref_records.json` "
        f"→ {'chỉ số khôi phục hoàn toàn về baseline' if recovered else 'chỉ số chưa khôi phục hoàn toàn, cần kiểm tra'}.",
    ]
    if repair_summary:
        lines += [f"- **Idempotent repair:** {repair_summary.get('note', '')}"]
        lines += [f"  - {key}: {_fmt(value)}" for key, value in repair_summary.items() if key != "note"]
    lines.append("")
    write_text(report_path, "\n".join(lines))
