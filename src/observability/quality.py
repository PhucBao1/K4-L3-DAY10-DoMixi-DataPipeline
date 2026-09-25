from __future__ import annotations

from typing import Any

import great_expectations as gx
import great_expectations.expectations as gxe
import pandas as pd

from core.config import Settings
from core.utils import now_utc, write_json

MIN_ROWS = 5
MAX_ROWS = 5000
MIN_SUMMARY_CHARS = 30
MIN_TITLE_CHARS = 8
MAX_STALE_RATIO = 0.25
REQUIRED_NOT_NULL_COLUMNS = ("paper_id", "title", "text_for_embedding")


def _build_expectations(settings: Settings) -> list[gxe.Expectation]:
    expectations: list[gxe.Expectation] = [
        gxe.ExpectTableRowCountToBeBetween(min_value=MIN_ROWS, max_value=MAX_ROWS),
        *[gxe.ExpectColumnValuesToNotBeNull(column=column) for column in REQUIRED_NOT_NULL_COLUMNS],
        gxe.ExpectColumnValuesToBeUnique(column="paper_id"),
        gxe.ExpectColumnValueLengthsToBeBetween(column="summary", min_value=MIN_SUMMARY_CHARS),
        # Bo sung: bat loi title bi cat ngan va vi pham Freshness SLA (> 25% bai qua han).
        gxe.ExpectColumnValueLengthsToBeBetween(column="title", min_value=MIN_TITLE_CHARS),
        gxe.ExpectColumnValuesToBeBetween(
            column="age_days",
            min_value=0,
            max_value=settings.freshness_threshold_days,
            mostly=1 - MAX_STALE_RATIO,
        ),
    ]
    return expectations


def _summarize_result(result) -> dict[str, Any]:
    config = result.expectation_config
    details = result.result or {}
    summary: dict[str, Any] = {
        "expectation": config.type,
        "column": config.kwargs.get("column"),
        "success": bool(result.success),
    }
    for key in ("observed_value", "unexpected_count", "unexpected_percent", "partial_unexpected_list"):
        if key in details:
            summary[key] = details[key]
    if result.exception_info and result.exception_info.get("raised_exception"):
        summary["exception"] = result.exception_info.get("exception_message")
    return summary


def run_data_quality_checks(df: pd.DataFrame, settings: Settings, report_name: str) -> dict[str, Any]:
    """Chay Quality Gate bang Great Expectations 1.x (ephemeral context) va ghi report JSON.

    Report duoc ghi vao `data/quality/<report_name>_quality_report.json`.
    """
    context = gx.get_context(mode="ephemeral")
    data_source = context.data_sources.add_pandas(name="papers_source")
    data_asset = data_source.add_dataframe_asset(name="papers_asset")
    batch_def = data_asset.add_batch_definition_whole_dataframe("papers_batch")
    batch = batch_def.get_batch(batch_parameters={"dataframe": df})

    suite = context.suites.add(gx.ExpectationSuite(name=f"papers_quality_{report_name}"))
    for expectation in _build_expectations(settings):
        suite.add_expectation(expectation)

    validation = batch.validate(suite)
    checks = [_summarize_result(result) for result in validation.results]
    failed = [check for check in checks if not check["success"]]
    report = {
        "report_name": report_name,
        "generated_at": now_utc().isoformat(),
        "gx_version": gx.__version__,
        "success": bool(validation.success),
        "row_count": int(len(df)),
        "evaluated_expectations": len(checks),
        "successful_expectations": len(checks) - len(failed),
        "failed_expectations": [f"{check['expectation']}({check['column'] or 'table'})" for check in failed],
        "checks": checks,
    }
    report_path = settings.paths.quality_dir / f"{report_name}_quality_report.json"
    write_json(report_path, report)
    report["report_path"] = str(report_path)
    return report


def build_freshness_report(df: pd.DataFrame, settings: Settings, report_path) -> dict[str, Any]:
    """Tong hop Freshness SLA: `is_fresh = False` neu > 25% bai co `age_days > threshold`."""
    threshold = settings.freshness_threshold_days
    total_rows = int(len(df))
    published = pd.to_datetime(df["published"], errors="coerce") if total_rows else pd.Series(dtype="datetime64[ns]")
    age_days = pd.to_numeric(df["age_days"], errors="coerce") if total_rows else pd.Series(dtype=float)

    stale_rows = int((age_days > threshold).sum())
    stale_ratio = stale_rows / total_rows if total_rows else 1.0
    payload = {
        "generated_at": now_utc().isoformat(),
        "threshold_days": threshold,
        "max_stale_ratio": MAX_STALE_RATIO,
        "latest_published": published.max().strftime("%Y-%m-%d") if published.notna().any() else None,
        "oldest_published": published.min().strftime("%Y-%m-%d") if published.notna().any() else None,
        "median_age_days": float(age_days.median()) if age_days.notna().any() else None,
        "stale_rows": stale_rows,
        "total_rows": total_rows,
        "stale_ratio": round(stale_ratio, 4),
        "is_fresh": bool(total_rows > 0 and stale_ratio <= MAX_STALE_RATIO),
    }
    write_json(report_path, payload)
    return payload
