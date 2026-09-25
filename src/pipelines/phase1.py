from __future__ import annotations

from typing import Any

from core.config import Settings, load_settings
from core.utils import now_utc, read_json, write_csv, write_json
from evaluation.metrics import evaluate_pipeline
from evaluation.testset import build_test_set
from ingestion.cleaning import build_clean_dataframe
from ingestion.crossref import fetch_source_records
from observability.quality import build_freshness_report, run_data_quality_checks
from observability.reporting import generate_phase1_report
from retrieval.index import LocalEmbeddingIndex

DEMO_QUESTION_COUNT = 2


def _run_agent_demo(settings: Settings, index: LocalEmbeddingIndex, test_set: list[dict[str, Any]]) -> None:
    """Demo agent tren vai cau hoi; loi LLM (thieu key, provider offline) khong lam hong pipeline."""
    demo: list[dict[str, Any]] = []
    try:
        from retrieval.agent import build_agent, run_agent_question

        agent = build_agent(settings, index)
        for item in test_set[:DEMO_QUESTION_COUNT]:
            demo.append({"question": item["question"], "answer": run_agent_question(agent, item["question"])})
    except Exception as exc:
        demo.append({"skipped": f"Agent demo unavailable: {exc}"})
    write_json(settings.paths.demo_answers, demo)


def main() -> None:
    settings = load_settings()
    run_date = now_utc()
    print(f"[phase1] Run date: {run_date.isoformat()}")

    # 1-2. Ingestion: raw snapshot (offline) hoac Crossref API (REFRESH_SOURCE=1).
    records = fetch_source_records(settings)
    print(f"[phase1] Raw records: {len(records)}")

    # 3-4. Cleaning va luu artifacts sach.
    clean_df = build_clean_dataframe(records, run_date)
    write_csv(clean_df, settings.paths.clean_csv)
    write_json(settings.paths.clean_json, clean_df.to_dict(orient="records"))
    print(f"[phase1] Clean rows: {len(clean_df)} -> {settings.paths.clean_csv}")

    # 5. Quality Gate chan du lieu xau truoc khi vao vector store.
    quality = run_data_quality_checks(clean_df, settings, "baseline")
    freshness = build_freshness_report(clean_df, settings, settings.paths.freshness_report)
    print(f"[phase1] Quality gate success={quality['success']} | is_fresh={freshness['is_fresh']}")
    if not quality["success"]:
        raise RuntimeError(f"Quality gate failed, refusing to index baseline data: {quality['failed_expectations']}")
    if not freshness["is_fresh"]:
        print(f"[phase1] WARNING: Freshness SLA violated ({freshness['stale_ratio']:.0%} stale rows)")

    # 6. Build Chroma collection `papers-baseline`.
    index = LocalEmbeddingIndex.build(clean_df, settings, settings.paths.embeddings_json)
    print(f"[phase1] Indexed {index.collection.count()} docs into '{index.collection_name}'")

    # 7. Test set co dinh de so sanh cong bang giua cac lan chay (REFRESH_TEST_SET=1 de tao lai).
    if settings.refresh_test_set or not settings.paths.eval_testset.exists():
        test_set = build_test_set(clean_df, settings.paths.eval_testset)
    else:
        test_set = read_json(settings.paths.eval_testset)
    print(f"[phase1] Test set: {len(test_set)} questions")

    # 8. Evaluate baseline.
    bundle = evaluate_pipeline(
        settings,
        index,
        settings.paths.eval_testset,
        settings.paths.baseline_metrics,
        settings.paths.baseline_answers,
    )
    metrics = bundle.summary
    print(
        f"[phase1] Baseline hit_rate={metrics['retrieval_hit_rate']:.3f} "
        f"token_f1={metrics['mean_token_f1']:.3f} judge_acc={metrics['judge_accuracy']:.3f}"
    )

    # 9. Markdown report.
    source_summary = {
        "source_api": settings.source_api,
        "mode": "live API" if settings.refresh_source else "offline snapshot",
        "source_query": settings.source_query,
        "raw_response": settings.paths.raw_api_response.relative_to(settings.paths.project_dir).as_posix(),
        "raw_records": len(records),
        "clean_rows": len(clean_df),
        "dropped_rows": len(records) - len(clean_df),
        "run_date": run_date.date().isoformat(),
        "embedding_model": settings.embedding_model,
        "collection": index.collection_name,
        "llm_provider": settings.llm_provider,
    }
    generate_phase1_report(settings.paths.baseline_report, source_summary, metrics, quality, freshness)
    print(f"[phase1] Report: {settings.paths.baseline_report}")

    # 10. Agent demo (optional).
    _run_agent_demo(settings, index, test_set)
