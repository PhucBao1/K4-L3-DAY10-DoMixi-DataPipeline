from __future__ import annotations

from typing import Any

import pandas as pd

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from ingestion.cleaning import build_clean_dataframe
from ingestion.corruption import corrupt_clean_dataframe
from ingestion.crossref import load_raw_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_corruption_report
from retrieval.index import LocalEmbeddingIndex


def _save_frame(df: pd.DataFrame, csv_path, json_path) -> None:
    write_csv(df, csv_path)
    write_json(json_path, df.to_dict(orient="records"))


def _evaluate(settings: Settings, df: pd.DataFrame, embeddings_path, metrics_path, answers_path, label: str):
    index = LocalEmbeddingIndex.build(df, settings, embeddings_path)
    print(f"[{label}] Indexed {index.collection.count()} docs into '{index.collection_name}'")
    bundle = evaluate_pipeline(settings, index, settings.paths.eval_testset, metrics_path, answers_path)
    summary = bundle.summary
    print(
        f"[{label}] hit_rate={summary['retrieval_hit_rate']:.3f} token_f1={summary['mean_token_f1']:.3f} "
        f"judge_acc={summary['judge_accuracy']:.3f}"
    )
    return bundle


def _repair_from_raw(settings: Settings, run_date) -> pd.DataFrame:
    """Idempotent repair: tai tao du lieu sach tu raw snapshot (nguon su that), khong sua tay."""
    return build_clean_dataframe(load_raw_records(settings.paths.raw_records_json), run_date)


def _print_comparison(baseline: dict[str, Any], corrupted: dict[str, Any], repaired: dict[str, Any]) -> None:
    keys = ("retrieval_hit_rate", "mean_token_f1", "judge_accuracy", "mean_judge_score")
    print("\n" + "=" * 72)
    print(f"{'Metric':<22}{'Baseline':>12}{'Corrupted':>12}{'Repaired':>12}{'Δ Corrupt':>12}")
    print("-" * 72)
    for key in keys:
        b, c, r = (float(m.get(key, 0)) for m in (baseline, corrupted, repaired))
        print(f"{key:<22}{b:>12.3f}{c:>12.3f}{r:>12.3f}{c - b:>+12.3f}")
    print("=" * 72 + "\n")


CORRUPTED_FRESHNESS = "corrupted_freshness_report.json"
REPAIRED_FRESHNESS = "repaired_freshness_report.json"


def _require_baseline(settings: Settings) -> None:
    paths = settings.paths
    for required in (paths.baseline_metrics, paths.clean_json, paths.eval_testset):
        if not required.exists():
            raise FileNotFoundError(f"Missing {required}. Run `python script/run_phase1.py` first.")


def run_corruption_stage(settings: Settings | None = None) -> dict[str, Any]:
    """Buoc 1-5: tiem loi -> quality gate/freshness bao dong -> index + evaluate du lieu loi."""
    settings = settings or load_settings()
    paths = settings.paths
    _require_baseline(settings)
    clean_df = pd.DataFrame(read_json(paths.clean_json))

    # Xoa ket qua repair cu de trang thai "Repaired" khong bi lan voi lan tiem loi moi.
    for stale in (paths.repaired_metrics, paths.repaired_answers, paths.comparison_report):
        stale.unlink(missing_ok=True)

    corrupted_df = corrupt_clean_dataframe(clean_df, paths.corruption_log)
    _save_frame(corrupted_df, paths.corrupted_clean_csv, paths.corrupted_clean_json)
    print(f"[corrupted] Rows {len(clean_df)} -> {len(corrupted_df)} | log: {paths.corruption_log}")

    corrupted_quality = run_data_quality_checks(corrupted_df, settings, "corrupted")
    corrupted_freshness = build_freshness_report(corrupted_df, settings, paths.quality_dir / CORRUPTED_FRESHNESS)
    print(
        f"[corrupted] ALERT quality_success={corrupted_quality['success']} "
        f"failed={corrupted_quality['failed_expectations']} | is_fresh={corrupted_freshness['is_fresh']}"
    )

    # Co tinh index + evaluate du lieu loi de do "silent failure" neu khong co quality gate.
    bundle = _evaluate(
        settings, corrupted_df, paths.corrupted_embeddings_json, paths.corrupted_metrics, paths.corrupted_answers, "corrupted"
    )
    return {"quality": corrupted_quality, "freshness": corrupted_freshness, "metrics": bundle.summary}


def run_repair_stage(settings: Settings | None = None) -> dict[str, Any]:
    """Buoc 6-8: auto-repair tu raw snapshot (idempotent) -> evaluate -> comparison report."""
    settings = settings or load_settings()
    paths = settings.paths
    _require_baseline(settings)
    if not paths.corrupted_metrics.exists():
        raise FileNotFoundError("Missing corrupted artifacts. Run the corruption stage first.")
    run_date = now_utc()

    baseline_metrics = read_json(paths.baseline_metrics)
    baseline_answers = read_json(paths.baseline_answers) if paths.baseline_answers.exists() else []
    clean_df = pd.DataFrame(read_json(paths.clean_json))
    baseline_quality = run_data_quality_checks(clean_df, settings, "baseline")
    baseline_freshness = build_freshness_report(clean_df, settings, paths.freshness_report)
    corrupted_quality = read_json(paths.corrupted_quality_report)
    corrupted_freshness = read_json(paths.quality_dir / CORRUPTED_FRESHNESS)
    corrupted_metrics = read_json(paths.corrupted_metrics)
    corrupted_answers = read_json(paths.corrupted_answers)

    # Auto-repair khi quality gate / freshness SLA bi vi pham.
    trigger = []
    if not corrupted_quality["success"]:
        trigger.append("quality gate failed")
    if not corrupted_freshness["is_fresh"]:
        trigger.append("freshness SLA violated")
    print(f"[repair] Triggered by: {', '.join(trigger) or 'manual run'} -> rebuilding from {paths.raw_records_json}")

    repaired_df = _repair_from_raw(settings, run_date)
    second_pass = _repair_from_raw(settings, run_date)
    idempotent = repaired_df.equals(second_pass)
    matches_baseline = set(repaired_df["paper_id"]) == set(clean_df["paper_id"]) and (
        repaired_df.set_index("paper_id")["text_for_embedding"].sort_index().tolist()
        == clean_df.set_index("paper_id")["text_for_embedding"].sort_index().tolist()
    )
    _save_frame(repaired_df, paths.repaired_clean_csv, paths.repaired_clean_json)

    repaired_quality = run_data_quality_checks(repaired_df, settings, "repaired")
    repaired_freshness = build_freshness_report(repaired_df, settings, paths.quality_dir / REPAIRED_FRESHNESS)
    print(f"[repair] quality_success={repaired_quality['success']} is_fresh={repaired_freshness['is_fresh']} idempotent={idempotent}")
    if not repaired_quality["success"]:
        raise RuntimeError(f"Repaired data still fails the quality gate: {repaired_quality['failed_expectations']}")

    repaired_bundle = _evaluate(
        settings, repaired_df, paths.repaired_embeddings_json, paths.repaired_metrics, paths.repaired_answers, "repaired"
    )

    repair_summary = {
        "note": "Repair rebuilds the clean dataset from the immutable raw snapshot; running it twice yields identical data.",
        "trigger": ", ".join(trigger) or "manual run",
        "idempotent_two_runs_identical": idempotent,
        "repaired_matches_baseline_content": matches_baseline,
        "repaired_rows": len(repaired_df),
    }
    write_json(paths.quality_dir / "repair_summary.json", repair_summary)
    generate_corruption_report(
        paths.comparison_report,
        baseline_metrics,
        corrupted_metrics,
        repaired_bundle.summary,
        corrupted_quality,
        repaired_quality,
        corrupted_freshness,
        repaired_freshness,
        baseline_quality=baseline_quality,
        baseline_freshness=baseline_freshness,
        corruption_log=read_json(paths.corruption_log),
        answers={"baseline": baseline_answers, "corrupted": corrupted_answers, "repaired": repaired_bundle.answers},
        repair_summary=repair_summary,
    )
    _print_comparison(baseline_metrics, corrupted_metrics, repaired_bundle.summary)
    print(f"[report] {paths.comparison_report}")
    return {"quality": repaired_quality, "freshness": repaired_freshness, "metrics": repaired_bundle.summary, **repair_summary}


def main() -> None:
    settings = load_settings()
    run_corruption_stage(settings)
    run_repair_stage(settings)
