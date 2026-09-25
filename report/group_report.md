# Group Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin bài nộp

| Thông tin | Nội dung |
| --- | --- |
| Khóa/Lớp | K4 — H205 |
| Tên nhóm | DoMixi |
| Repository | https://github.com/PhucBao1/K4-L3-DAY10-DoMixi-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

### Thành viên và phân công

| STT | Họ và tên | MSSV | Vai trò chính | Module/deliverable sở hữu |
| --: | --- | --- | --- | --- |
| 1 | Nguyễn Phúc Bảo | 2A202602925 | Trưởng nhóm, Ingestion & Pipeline Integrator | `src/ingestion/crossref.py`, `src/pipelines/phase1.py`, `src/pipelines/corruption_flow.py`, `script/dashboard.py`, cấu hình môi trường, artifacts trong `data/` |
| 2 | Đào Thanh Trường | 2A202602683 | Data Transformation, Corruption & RAG Index | `src/ingestion/cleaning.py`, `src/ingestion/corruption.py`, `src/retrieval/index.py`, 3 collection ChromaDB |
| 3 |  Nguyễn Ngọc Bảo | 2A202602951 | Observability & Evaluation | `src/observability/quality.py`, `src/observability/reporting.py`, `src/evaluation/testset.py` |

## 2. Tóm tắt kết quả

Nhóm hoàn thành toàn bộ 7 tầng của pipeline: ingestion Crossref có fallback offline, cleaning, Quality Gate Great Expectations 1.x kèm Freshness SLA, index ChromaDB bằng `all-MiniLM-L6-v2`, đánh giá RAG, bộ 6 kịch bản corruption và repair tự động, idempotent từ raw snapshot. Cả hai lệnh `run_phase1.py` và `run_corruption_flow.py` chạy end-to-end với exit code 0 trên commit nộp bài.

Pha baseline sinh ra 24 bản ghi sạch (`papers_clean.csv/json`), bộ 10 câu hỏi cố định (`test_set.json`), collection `papers-baseline`, `baseline_metrics.json` và `phase1_report.md`. Baseline đạt Hit Rate 1.00, Token F1 1.00, Quality Gate 8/8.

Sau khi tiêm lỗi, Quality Gate giảm còn 4/8 và Freshness SLA chuyển sang STALE (26% bài quá hạn). Hit Rate giảm từ 1.00 xuống 0.70, Token F1 xuống 0.774, Judge Accuracy xuống 0.70. Lỗi ảnh hưởng rõ nhất đến agent là `drop_latest_records`: 2 câu hỏi mất tài liệu đích nên agent trả lời bằng bài khác mà không báo lỗi. Kế đến là `stale_date`, khiến câu hỏi ngày xuất bản bị trả lời lệch đúng 1 năm.

Repair tự kích hoạt vì Quality Gate và Freshness đều fail. Dữ liệu được dựng lại từ `data/raw/crossref_records.json`, chạy 2 lần cho kết quả giống hệt, và toàn bộ chỉ số phục hồi về mức baseline.

Giới hạn lớn nhất: QA dạng trích xuất kèm exact-title lookup khiến baseline đạt điểm tuyệt đối, và test set 10 câu chưa phủ các bài bị `blank_summary` hay `inject_noise`, nên hai lỗi này chỉ được Quality Gate phát hiện chứ chưa làm giảm metric.

## 3. Kiến trúc và luồng dữ liệu

### Luồng end-to-end

```text
Crossref REST API (REFRESH_SOURCE=1)  ──┐
data/raw/crossref_response.json (mặc định, offline) ─┴─> parse_crossref_payload
    -> data/raw/crossref_records.json                      (raw preservation)
    -> build_clean_dataframe -> data/clean/papers_clean.*  (cleaning + age_days + text_for_embedding)
    -> run_data_quality_checks (GX 1.x) + build_freshness_report
         └─ FAIL -> dừng Phase 1, không index
    -> LocalEmbeddingIndex.build -> ChromaDB `papers-baseline`
    -> build_test_set (cố định) -> evaluate_pipeline -> baseline_metrics.json
    -> corrupt_clean_dataframe (6 lỗi, seed=42) -> quality/freshness ALERT
    -> index `papers-corrupted` -> evaluate -> corrupted_metrics.json
    -> auto-repair: rebuild từ raw records (chạy 2 lần, so sánh) -> `papers-repaired`
    -> evaluate -> repaired_metrics.json -> corruption_report.md
```

### Trách nhiệm của từng khối

| Khối | Input | Xử lý chính | Output/artifact | Owner |
| --- | --- | --- | --- | --- |
| Ingestion | Crossref API / `crossref_response.json` | Retry 429/5xx tối đa 4 lần (backoff 2^n hoặc `Retry-After`), fallback snapshot, parse DOI/title/abstract/authors/subject/dates, bỏ tag JATS | `data/raw/crossref_records.json` | Thành viên 1 |
| Cleaning | `PaperRecord` list, `run_date` | Chuẩn hóa text, bỏ record thiếu khóa, dedupe `paper_id`, tính `age_days`, sinh cột helper | `data/clean/papers_clean.csv/json` | Thành viên 2 |
| Embedding/index | Clean dataframe | `all-MiniLM-L6-v2` (normalized), Chroma cosine, persist path tương đối | `data/chroma/`, `data/embeddings/*.json` | Thành viên 2 |
| Evaluation | Clean dataframe | 10 câu hỏi / 4 loại, Hit Rate, Token F1, LLM Judge | `data/eval/test_set.json`, `data/results/*_metrics.json` | Thành viên 3 |
| Observability | Dataframe bất kỳ | GX 1.x ephemeral context (8 expectations), Freshness SLA | `data/quality/*.json` | Thành viên 3 |
| Corruption/repair | Clean dataframe, raw records | 6 corruption có seed; repair rebuild từ raw | `corruption_log.json`, `papers_clean_*` | Thành viên 2 (corruption), Thành viên 1 (repair) |
| Orchestration | Settings | Thứ tự chạy, quality gate chặn index, auto-repair trigger, báo cáo | `phase1_report.md`, `corruption_report.md` | Thành viên 1 (pipelines), Thành viên 3 (reporting) |

## 4. Cách tái hiện kết quả

### Cấu hình không chứa secret

| Biến/cấu hình | Giá trị sử dụng |
| --- | --- |
| `LLM_PROVIDER` | `openai` (có hỗ trợ `mock`, `gemini`, `anthropic`, `ollama`...) |
| `LLM_MODEL` | `gpt-4o-mini` |
| Embedding model | `sentence-transformers/all-MiniLM-L6-v2` |
| Số lượng Crossref records | 24 |
| Retrieval `top_k` | 4 |
| Freshness threshold | `age_days > 180`, cảnh báo khi tỷ lệ bài quá hạn > 25% |
| Random seed | 42 (`corruption.py`) |

Không có API key thì pipeline vẫn chạy hết. LLM Judge tự chuyển sang heuristic theo Token F1, còn phần demo agent được ghi là "skipped".

### Lệnh cài đặt

```bash
uv sync
```

### Lệnh chạy

```bash
uv run python script/run_phase1.py
uv run python script/run_corruption_flow.py
uv run streamlit run script/dashboard.py   # dashboard (bonus)
```

### Kết quả tái hiện

| Lệnh | Trạng thái | Thời điểm chạy gần nhất | Bằng chứng |
| --- | --- | --- | --- |
| Baseline pipeline | Thành công (exit 0) | 2026-09-25 17:09 (GMT+7) | `data/results/baseline_metrics.json`, `data/reports/phase1_report.md` |
| Corruption flow | Thành công (exit 0) | 2026-09-25 17:09 (GMT+7) | `data/results/corrupted_metrics.json`, `repaired_metrics.json`, `data/reports/corruption_report.md` |

## 5. Ingestion, cleaning và data contract

### Nguồn dữ liệu

| Thuộc tính | Giá trị |
| --- | --- |
| Source | Crossref REST API `https://api.crossref.org/works`, chế độ mặc định đọc snapshot `data/raw/crossref_response.json` |
| Query/filter | `query="agentic retrieval augmented generation large language model"`, `filter=from-pub-date:<hôm nay − 180 ngày>,has-abstract:true`, `rows=24`, sort theo `published` giảm dần |
| Thời điểm lấy dữ liệu | Snapshot offline có sẵn trong starter repo; parse lại lúc 2026-09-25 17:09 |
| Số record nhận được | 24 (24 hợp lệ, 0 trùng DOI) |
| Cơ chế retry/backoff | Retry tối đa 4 lần với status 429/500/502/503/504, chờ theo `Retry-After` hoặc 2^n giây. Nếu API vẫn lỗi thì fallback snapshot và không ghi đè raw gốc |

### Raw và clean schema

| Trường | Kiểu dữ liệu | Bắt buộc? | Ý nghĩa | Xử lý khi thiếu/sai |
| --- | --- | --- | --- | --- |
| `paper_id` | str (DOI lowercase) | Có | Khóa duy nhất | Thiếu thì bỏ record; trùng thì giữ bản `updated` mới nhất |
| `title` | str | Có | Tiêu đề | Thiếu thì bỏ record |
| `summary` | str | Có | Abstract đã bỏ tag JATS | Thiếu hoặc rỗng thì bỏ record |
| `authors` / `authors_joined` | list[str] / str | Không | Tác giả (given + family) | Rỗng thì để chuỗi rỗng |
| `categories` / `categories_joined` | list[str] / str | Không | Subject Crossref | Rỗng thì để chuỗi rỗng |
| `published` | str `YYYY-MM-DD` | Có | Ngày xuất bản (`published` → `published-online` → `published-print` → `issued`) | Không parse được thì bỏ record |
| `updated` | str `YYYY-MM-DD` | Không | Ngày tạo/deposit | Thiếu thì dùng `published` |
| `age_days` | int | Có | Tuổi bài báo tại `run_date` | Tính từ `published` |
| `summary_chars` | int | Có | Độ dài abstract | Tính lại sau mỗi biến đổi |
| `text_for_embedding` | str | Có | Văn bản đưa vào embedding | Sinh từ 5 trường |

### Quy tắc cleaning

| Quy tắc | Quality dimension liên quan | Số record bị tác động | Cách xác minh |
| --- | --- | --: | --- |
| Bỏ tag JATS/HTML (`<jats:p>`), decode HTML entity | Validity | 24 | `crossref_response.json` so với `crossref_records.json` |
| Chuẩn hóa khoảng trắng, bỏ author/category trùng | Consistency | 24 (chuẩn hóa), 0 trùng | `papers_clean.json` |
| Bỏ record thiếu `paper_id`/`title`/`summary`/`published` | Completeness | 0 | `phase1_report.md`: `dropped_rows = 0` |
| Dedupe theo `paper_id`, giữ bản mới nhất | Uniqueness | 0 | GX `expect_column_values_to_be_unique(paper_id)` pass |
| Tính `age_days` theo ngày chạy | Timeliness | 24 | `freshness_report.json` |

`text_for_embedding` ghép 5 dòng: `Title / Authors / Published / Categories / Summary`, nên embedding mang đủ ngữ cảnh cho cả 4 loại câu hỏi. Document ID trong Chroma là `<paper_id>::<vị trí dòng>`, để các dòng trùng lặp khi bị corruption vẫn được index riêng (và chiếm chỗ trong top-k, đúng như sự cố thực tế). `age_days = (run_date − published).days`, tính theo ngày UTC.

## 6. Evaluation setup

| Thành phần | Cấu hình thực tế |
| --- | --- |
| Số câu hỏi | 10 |
| Các `question_type` | `summary` (3), `authors` (3), `date` (2), `categories` (2) |
| Ground-truth document ID | DOI của bài được chọn. 10 bài được chọn trải đều theo `published` từ mới đến cũ nên có cả bài mới nhất |
| Embedding model | `all-MiniLM-L6-v2` |
| Vector store/collection | ChromaDB persistent `data/chroma`, cosine: `papers-baseline`, `papers-corrupted`, `papers-repaired` |
| Retrieval `top_k` | 4 |
| LLM provider/model | OpenAI `gpt-4o-mini` (LLM Judge + agent demo) |
| Test set dùng chung cho ba trạng thái | `data/eval/test_set.json` (sha256 `3541bfb96efb…`) |

Test set được sinh một lần từ dữ liệu sạch và giữ cố định (chỉ sinh lại khi `REFRESH_TEST_SET=1`). Nhờ vậy, mọi chênh lệch giữa Baseline, Corrupted và Repaired đều do dữ liệu trong index thay đổi, không do đề thi thay đổi. Nếu sinh test set từ dữ liệu lỗi thì các bài bị drop sẽ biến mất khỏi đề và sự suy giảm bị che mất.

## 7. Kết quả baseline

### Artifact checklist

| Artifact | Đường dẫn thực tế | Trạng thái | Ghi chú |
| --- | --- | --- | --- |
| Raw response/records | `data/raw/` | Có | 24 items / 24 records |
| Cleaned dataset | `data/clean/` | Có | 24 dòng, 16 cột |
| Embedding manifest/index | `data/embeddings/`, `data/chroma/` | Có | 3 collection, persist path tương đối |
| Evaluation set | `data/eval/test_set.json` | Có | 10 câu |
| Baseline metrics | `data/results/baseline_metrics.json` | Có | Kèm `baseline_answers.json` |
| Quality/freshness | `data/quality/` | Có | baseline / corrupted / repaired |
| Baseline report | `data/reports/phase1_report.md` | Có | Sinh tự động |

### Baseline metrics

| Metric | Giá trị | Diễn giải |
| --- | --: | --- |
| `retrieval_hit_rate` | 1.00 | Cả 10 câu đều có tài liệu đích trong top-4 |
| `mean_token_f1` | 1.00 | QA trích xuất trực tiếp từ metadata của tài liệu top-1, nên trên dữ liệu sạch câu trả lời trùng khớp ground truth |
| `judge_accuracy` | 1.00 | LLM Judge (`gpt-4o-mini`) chấm đúng cả 10 câu |
| `mean_judge_score` | 5.0 / 5 | |
| Ragas | N/A | Tắt mặc định (`RUN_RAGAS=1` để bật) vì chậm và tốn thêm lượt gọi LLM |

## 8. Data quality và freshness

### Quality checks

| Check | Quality dimension | Ngưỡng/kỳ vọng | Kết quả baseline | Bằng chứng |
| --- | --- | --- | --- | --- |
| `ExpectTableRowCountToBeBetween` | Completeness | 5 – 5000 dòng | Pass (24) | `baseline_quality_report.json` |
| `ExpectColumnValuesToNotBeNull(paper_id)` | Completeness | 0 null | Pass (0) | 〃 |
| `ExpectColumnValuesToNotBeNull(title)` | Completeness | 0 null | Pass (0) | 〃 |
| `ExpectColumnValuesToNotBeNull(text_for_embedding)` | Completeness | 0 null | Pass (0) | 〃 |
| `ExpectColumnValuesToBeUnique(paper_id)` | Uniqueness | 0 trùng | Pass (0) | 〃 |
| `ExpectColumnValueLengthsToBeBetween(summary)` | Validity | ≥ 30 ký tự | Pass (min 193) | 〃 |
| `ExpectColumnValueLengthsToBeBetween(title)` *(bổ sung)* | Validity | ≥ 8 ký tự | Pass (min 55) | 〃 |
| `ExpectColumnValuesToBeBetween(age_days)` *(bổ sung)* | Timeliness | 0 – 180, `mostly=0.75` | Pass (1 bài vượt, 4%) | 〃 |

Quality Gate dùng cú pháp GX 1.x: `gx.get_context(mode="ephemeral")` → `data_sources.add_pandas` → `add_dataframe_asset` → `add_batch_definition_whole_dataframe` → `batch.validate(suite)`.

### Freshness

| Thuộc tính | Giá trị |
| --- | --- |
| Freshness được đo tại | Clean dataset (`age_days`), trước khi index |
| Timestamp mới nhất | `latest_published = 2026-07-22` (cũ nhất 2026-03-28) |
| Ngưỡng freshness | `age_days > 180` là quá hạn; `is_fresh = False` khi > 25% bài quá hạn |
| Trạng thái baseline | Fresh |
| Lý do | 1/24 bài quá hạn (4.17%), median `age_days` 110.5 |

## 9. Corruption scenarios và repair

| Corruption | Cách tạo | Record bị tác động | Quality signal kỳ vọng | Tác động thực tế | Cách repair |
| --- | --- | --: | --- | --- | --- |
| `drop_latest_records` | Bỏ 20% bài mới nhất | 5 | Freshness: `latest_published` lùi | `latest_published` 2026-07-22 → 2026-06-11. eval_001, eval_002 retrieval miss, agent trả lời bằng bài khác | Rebuild từ raw records |
| `blank_summary` | Abstract thành chuỗi rỗng | 3 | Summary length fail | GX `summary` fail 3 dòng. Không có câu hỏi nào trỏ tới 3 bài này nên metric không đổi | Rebuild từ raw |
| `inject_noise` | Chèn token rác trước/sau abstract | 3 | (không có check riêng) | Bài 815 chỉ được hỏi `date` nên không đổi. Không phát hiện được bằng GX hiện tại | Rebuild từ raw |
| `truncate_title` | Cắt title còn 7 ký tự | 3 | Title length fail | GX `title` fail 5 dòng (3 bài + 2 bản sao). eval_010 retrieval miss vì exact-title lookup thất bại | Rebuild từ raw |
| `stale_date` | Lùi `published` 365 ngày | 5 | Freshness STALE, `age_days` fail | 6/23 bài quá hạn (26%): STALE. eval_003 trả lời `2025-06-12` thay vì `2026-06-12` | Rebuild từ raw |
| `duplicate_rows` | Nhân bản 4 dòng | 4 | Uniqueness fail | GX unique fail 8 dòng. Ở eval_002, bài 819 chiếm 2/4 slot top-k | Rebuild từ raw (dedupe) |

Corruption log:

- Đường dẫn: `data/results/corruption_log.json`
- Trạng thái: Có
- Nhận xét: log ghi đủ 6 loại, số dòng và `paper_id` bị tác động của từng loại, seed (42), số dòng trước/sau (24 → 23), kèm title và ngày gốc cho `truncate_title` và `stale_date`.

Repair **không vá dữ liệu lỗi** mà dựng lại toàn bộ clean dataset từ `data/raw/crossref_records.json`, bản raw bất biến được lưu ở bước ingestion (nguồn sự thật). Repair tự kích hoạt khi Quality Gate hoặc Freshness SLA fail (`repair_summary.json`: *"quality gate failed, freshness SLA violated"*). Pipeline chạy repair 2 lần và so sánh 2 dataframe (`idempotent_two_runs_identical = True`), đối chiếu nội dung với baseline (`repaired_matches_baseline_content = True`), rồi phải qua lại Quality Gate (8/8) mới được index vào `papers-repaired`.

## 10. So sánh baseline, corrupted và repaired

| Metric/signal | Baseline | Corrupted | Repaired | Thay đổi do corruption | Mức phục hồi | Nhận xét |
| --- | --: | --: | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.70 | 1.00 | −0.30 | 100% | 3 câu miss: 2 do drop, 1 do title bị cắt |
| `mean_token_f1` | 1.000 | 0.774 | 1.000 | −0.226 | 100% | eval_002 và eval_003 về 0, eval_001 còn 0.74 |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | −0.30 | 100% | Judge đánh sai eval_001, eval_002, eval_003 |
| `mean_judge_score` | 5.0 | 4.1 | 5.0 | −0.9 | 100% | |
| Quality checks pass/fail | 8/8 Pass | 4/8 Fail | 8/8 Pass | −4 checks | 100% | Fail: unique, title, summary, age_days |
| Freshness status | Fresh (4%) | Stale (26%) | Fresh (4%) | +22 điểm % | 100% | Vượt ngưỡng 25% |

Kết luận nhân quả (dựa trên `corruption_log.json`, `corrupted_answers.json`, `corrupted_quality_report.json`):

1. `drop_latest_records` bỏ bài 812 và 807 (đích của eval_001 và eval_002), Freshness báo `latest_published` lùi về 2026-06-11. Retrieval miss nên agent trả lời bằng bài khác: tác giả sai hoàn toàn ở eval_002 (F1 = 0), tóm tắt của một bài gần giống ở eval_001. Pipeline không báo lỗi nào. Đây là silent failure điển hình.
2. `stale_date` lùi ngày của 5 bài làm tỷ lệ bài quá hạn lên 26% (> 25%), nên `is_fresh = False` và `age_days` expectation fail. eval_003 vẫn retrieve đúng bài nhưng trả lời ngày sai đúng 1 năm (`2025-06-12`, F1 = 0): retrieval đúng vẫn không đảm bảo câu trả lời đúng khi dữ liệu bị mốc.
3. Repair dựng lại từ raw nên Quality Gate về 8/8 và Freshness về Fresh, toàn bộ 4 metric phục hồi về 1.00 / 5.0 trên cùng test set.

Kết quả khác kỳ vọng:
- **eval_010:** bài 805 bị cắt title nên exact lookup thất bại và retrieval miss. Tuy vậy Token F1 và Judge vẫn đạt tối đa, vì bài 817 được retrieve thay thế có cùng tác giả ("Tuan Phan, Mai Bui"). Metric câu trả lời có thể che lỗi retrieval, nên cần xem cả Hit Rate lẫn F1.
- **eval_004:** bài 821 cũng bị cắt title nhưng vẫn hit nhờ semantic search trên `text_for_embedding` vẫn còn abstract.
- **`blank_summary` và `inject_noise`:** không làm giảm metric vì không câu hỏi `summary` nào trỏ tới các bài bị tác động. Nhóm không kết luận hai lỗi này "có tác động" lên agent, chỉ ghi nhận chúng bị Quality Gate phát hiện (`blank_summary`) hoặc chưa được phát hiện (`inject_noise`).

## 11. Vấn đề tích hợp quan trọng

- **Triệu chứng:** artifact index sinh ra trên máy trưởng nhóm không dùng được trên máy khác. `data/embeddings/*.json` chứa `persist_path` tuyệt đối (`D:\...`), và các file segment nhị phân của Chroma (`length.bin`) bị git cảnh báo *"LF will be replaced by CRLF"*.
- **Nguyên nhân:** (1) `LocalEmbeddingIndex.build` lưu `str(persist_path)` tuyệt đối, đồng thời rubric trừ điểm hardcode đường dẫn; (2) `core.autocrlf` trên Windows coi file `.bin` không có byte NUL là text, nên khi checkout sẽ đổi byte xuống dòng và hỏng HNSW index.
- **Cách xử lý:** lưu `persist_path` tương đối (`data/chroma`) và resolve theo `project_dir` khi `load()`; thêm `.gitattributes` với `data/chroma/** binary`; xóa các thư mục segment mồ côi của những collection đã bị xóa trước khi commit.
- **Cách xác minh:** `grep persist_path data/embeddings/papers_embeddings.json` ra `"data/chroma"`; `git check-attr binary` ra `set`; `chroma.sqlite3` chỉ tham chiếu 3 segment tương ứng 3 collection.

Ngoài ra, khi ghép module nhóm phải thống nhất `published` là chuỗi `YYYY-MM-DD` chứ không phải `Timestamp`, vì metadata của ChromaDB chỉ nhận kiểu scalar và câu trả lời `date` cần khớp đúng định dạng ground truth.

## 12. Giới hạn và hướng cải thiện

| Giới hạn hiện tại | Ảnh hưởng | Hướng cải thiện có thể kiểm chứng |
| --- | --- | --- |
| QA trích xuất + exact-title lookup khiến baseline đạt 1.00 | Khó phân biệt chất lượng retrieval trên dữ liệu sạch | Thêm câu hỏi paraphrase không chứa title; đo Hit Rate@1 và MRR |
| Test set 10 câu chưa phủ bài bị `blank_summary` / `inject_noise` | Không đo được tác động của 2 lỗi này lên agent | Sinh test set có stratify theo loại lỗi hoặc tăng lên ≥ 30 câu; so sánh F1 theo `question_type` |
| Chưa có expectation phát hiện nhiễu ký tự | `inject_noise` lọt qua Quality Gate | Thêm `ExpectColumnValuesToNotMatchRegex(summary, r"[#@!%~�]{2,}")`; kiểm chứng GX fail trên `papers_clean_corrupted.json` |
| `age_days` tính theo ngày chạy trên snapshot cố định | Sau khoảng 2026-11, baseline sẽ tự chuyển STALE | Đo freshness theo `ingested_at` của snapshot, hoặc refresh qua `REFRESH_SOURCE=1` |
| LLM Judge không tất định | Judge score có thể dao động nhẹ giữa các lần chạy | `temperature=0` (đã dùng), chạy 3 lần lấy trung bình, đối chiếu với Token F1 |

## 13. Checklist trước khi nộp

- [ ] Thông tin nhóm và repository chính xác (điền họ tên và MSSV ở mục 1).
- [x] Phân công khớp với module, artifact và commit thực tế trên `main`.
- [x] Lệnh tái hiện đã được chạy lại trên phiên bản dùng để nộp.
- [x] Baseline, corrupted và repaired dùng cùng evaluation set.
- [x] Bảng metrics khớp với các file trong `data/results/`.
- [x] Quality/freshness conclusions khớp với `data/quality/`.
- [x] Các đường dẫn báo cáo và artifact truy cập được.
- [ ] Mỗi thành viên đã hoàn thành báo cáo vai trò riêng.
- [x] Không có `.env`, API key, token hoặc secret trong source, report, log hay ảnh.
