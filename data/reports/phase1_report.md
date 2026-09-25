# Phase 1 Report — Baseline Data Pipeline

_Generated at: 2026-09-25T10:08:54.529011+00:00_

## 1. Source & Lineage

| Field | Value |
| :--- | :--- |
| source_api | Crossref REST API |
| mode | offline snapshot |
| source_query | agentic retrieval augmented generation large language model |
| raw_response | data/raw/crossref_response.json |
| raw_records | 24 |
| clean_rows | 24 |
| dropped_rows | 0 |
| run_date | 2026-09-25 |
| embedding_model | sentence-transformers/all-MiniLM-L6-v2 |
| collection | papers-baseline |
| llm_provider | openai |

## 2. Baseline RAG Evaluation

| Metric | Value |
| :--- | ---: |
| samples | 10 |
| retrieval_hit_rate | 1.0000 |
| mean_token_f1 | 1.0000 |
| judge_accuracy | 1.0000 |
| mean_judge_score | 5 |
| ragas | {'skipped': 'Set RUN_RAGAS=1 to enable the slower Ragas pass.'} |

## 3. Data Quality Gate (Great Expectations 1.x)

- Overall success: **✅ True**
- Expectations passed: 8/8
- Rows validated: 24

| Expectation | Column | Result | Observed / Unexpected |
| :--- | :--- | :---: | :--- |
| `expect_table_row_count_to_be_between` | (table) | ✅ True | observed=24 |
| `expect_column_values_to_not_be_null` | paper_id | ✅ True | unexpected=0 (0.0%) |
| `expect_column_values_to_be_unique` | paper_id | ✅ True | unexpected=0 (0.0%) |
| `expect_column_values_to_not_be_null` | title | ✅ True | unexpected=0 (0.0%) |
| `expect_column_value_lengths_to_be_between` | title | ✅ True | unexpected=0 (0.0%) |
| `expect_column_values_to_not_be_null` | text_for_embedding | ✅ True | unexpected=0 (0.0%) |
| `expect_column_value_lengths_to_be_between` | summary | ✅ True | unexpected=0 (0.0%) |
| `expect_column_values_to_be_between` | age_days | ✅ True | unexpected=1 (4.2%) |

## 4. Freshness SLA

Rule: `is_fresh = False` when more than 25% of papers have `age_days > 180`.

| Field | Value |
| :--- | :--- |
| threshold_days | 180 |
| max_stale_ratio | 0.2500 |
| latest_published | 2026-07-22 |
| oldest_published | 2026-03-28 |
| median_age_days | 110.5000 |
| stale_rows | 1 |
| total_rows | 24 |
| stale_ratio | 0.0417 |
| is_fresh | ✅ True |

## 5. Conclusion

Baseline data passed the quality gate and is fresh; this run is the reference point for the corruption experiment.
