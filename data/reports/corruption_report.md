# Corruption Report — Baseline vs Corrupted vs Repaired

_Generated at: 2026-09-25T10:10:05.052148+00:00_

## 1. Bảng đối chiếu 3 trạng thái

| Metric | Baseline | Corrupted | Repaired | Δ Corrupted | Δ Repaired |
| :--- | ---: | ---: | ---: | ---: | ---: |
| samples | 10 | 10 | 10 | 0 | 0 |
| retrieval_hit_rate | 1.0000 | 0.7000 | 1.0000 | -0.3000 | 0 |
| mean_token_f1 | 1.0000 | 0.7741 | 1.0000 | -0.2259 | 0 |
| judge_accuracy | 1.0000 | 0.7000 | 1.0000 | -0.3000 | 0 |
| mean_judge_score | 5 | 4.1000 | 5 | -0.9000 | 0 |
| GX quality gate | ✅ True | ❌ False | ✅ True | | |
| Expectations passed | 8/8 | 4/8 | 8/8 | | |
| Rows | 24 | 23 | 24 | | |
| Freshness is_fresh | ✅ True | ❌ False | ✅ True | | |
| Stale ratio (age_days > 180) | 0.0417 | 0.2609 | 0.0417 | | |

## 2. Các lỗi đã tiêm (corruption_log.json)

Rows: 24 → 23 (seed=42)

| # | Corruption | Rows | Description |
| ---: | :--- | ---: | :--- |
| 1 | `drop_latest_records` | 5 | Dropped the 20% most recent papers (simulates a failed incremental ingestion). |
| 2 | `blank_summary` | 3 | Replaced the abstract with an empty string. |
| 3 | `inject_noise` | 3 | Prepended garbage tokens to the abstract. |
| 4 | `truncate_title` | 3 | Truncated the title to 7 characters. |
| 5 | `stale_date` | 5 | Shifted the published date back by 365 days. |
| 6 | `duplicate_rows` | 4 | Appended exact copies of existing rows (non-idempotent re-ingestion). |

## 3. Observability Alert trên dữ liệu lỗi

- Quality gate: **❌ False** — failed expectations:
  - `expect_column_values_to_be_unique(paper_id)`
  - `expect_column_value_lengths_to_be_between(title)`
  - `expect_column_value_lengths_to_be_between(summary)`
  - `expect_column_values_to_be_between(age_days)`
- Freshness SLA: **❌ False** (6/23 stale rows, latest_published=2026-06-11)

| Expectation | Column | Result | Observed / Unexpected |
| :--- | :--- | :---: | :--- |
| `expect_table_row_count_to_be_between` | (table) | ✅ True | observed=23 |
| `expect_column_values_to_not_be_null` | paper_id | ✅ True | unexpected=0 (0.0%) |
| `expect_column_values_to_be_unique` | paper_id | ❌ False | unexpected=8 (34.8%) |
| `expect_column_values_to_not_be_null` | title | ✅ True | unexpected=0 (0.0%) |
| `expect_column_value_lengths_to_be_between` | title | ❌ False | unexpected=5 (21.7%) |
| `expect_column_values_to_not_be_null` | text_for_embedding | ✅ True | unexpected=0 (0.0%) |
| `expect_column_value_lengths_to_be_between` | summary | ❌ False | unexpected=3 (13.0%) |
| `expect_column_values_to_be_between` | age_days | ❌ False | unexpected=6 (26.1%) |

## 4. Tác động theo từng câu hỏi (Token F1 / retrieval hit)

| ID | Type | Baseline | Corrupted | Repaired | Corrupted answer |
| :--- | :--- | :---: | :---: | :---: | :--- |
| eval_001 | summary | 1.00 / hit | 0.74 / miss | 1.00 / hit | An extended empirical study on tatic benchmarks fail to capture dom... |
| eval_002 | authors | 1.00 / hit | 0.00 / miss | 1.00 / hit | Anh Tran, Quoc Pham |
| eval_003 | date | 1.00 / hit | 0.00 / hit | 1.00 / hit | 2025-06-12 |
| eval_004 | categories | 1.00 / hit | 1.00 / hit | 1.00 / hit | Information Retrieval, Natural Language Processing |
| eval_005 | summary | 1.00 / hit | 1.00 / hit | 1.00 / hit | An extended empirical study on single LLM is susceptible to confirm... |
| eval_006 | authors | 1.00 / hit | 1.00 / hit | 1.00 / hit | Tuan Phan, Mai Bui |
| eval_007 | date | 1.00 / hit | 1.00 / hit | 1.00 / hit | 2026-06-03 |
| eval_008 | categories | 1.00 / hit | 1.00 / hit | 1.00 / hit | Artificial Intelligence, Information Retrieval |
| eval_009 | summary | 1.00 / hit | 1.00 / hit | 1.00 / hit | Connecting LLMs directly to raw warehouse tables often results in s... |
| eval_010 | authors | 1.00 / hit | 1.00 / miss | 1.00 / hit | Tuan Phan, Mai Bui |

## 5. Phân tích

- **Silent failure:** trên dữ liệu lỗi, pipeline RAG vẫn chạy bình thường và trả lời tự tin, không hề báo lỗi — nhưng Hit Rate giảm 0.30 và Token F1 giảm 0.23 so với baseline. Bài bị drop không còn trong index (retrieval miss); title bị cắt làm exact-lookup thất bại; summary rỗng/nhiễu và ngày bị lùi tạo ra câu trả lời sai nhưng trông hợp lệ.
- **Observability:** Great Expectations 1.x và Freshness SLA phát hiện ngay các vi phạm (trùng `paper_id`, summary quá ngắn, title bị cắt, tỷ lệ bài quá hạn vượt ngưỡng) trước khi dữ liệu tới serving layer.
- **Repair:** tái tạo dữ liệu từ raw snapshot `data/raw/crossref_records.json` → chỉ số khôi phục hoàn toàn về baseline.
- **Idempotent repair:** Repair rebuilds the clean dataset from the immutable raw snapshot; running it twice yields identical data.
  - trigger: quality gate failed, freshness SLA violated
  - idempotent_two_runs_identical: ✅ True
  - repaired_matches_baseline_content: ✅ True
  - repaired_rows: 24
