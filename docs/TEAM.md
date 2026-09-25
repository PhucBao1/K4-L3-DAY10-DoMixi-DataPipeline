# Danh Sách Thành Viên & Báo Cáo Phân Công Nhóm

- **Tên Nhóm:** `DoMixi`
- **Mã Nhóm / Lớp:** `K4-L3-DAY10`
- **Tên Repository Nộp Bài:** `K4-L3-DAY10-DoMixi-DataPipeline`

---

## # Thành viên

| STT | Họ và tên | MSSV | Email | Vai trò & Phân công công việc | Báo cáo cá nhân |
|---:|---|---|---|---|---|
| 1 | | | | Trưởng nhóm / Ingestion & Pipeline Integrator (`core/`, `crossref.py`, `phase1.py`, `corruption_flow.py`) | `report/<MSSV1>_HoTen.md` |
| 2 | | | | Data Transformation, Corruption & RAG Index (`cleaning.py`, `corruption.py`, `retrieval/`, ChromaDB) | `report/<MSSV2>_HoTen.md` |
| 3 | | | | Observability & Evaluation (`quality.py` GX 1.x, `testset.py`, `reporting.py`) | `report/<MSSV3>_HoTen.md` |

---

## # Kế hoạch phân công theo Checkpoint

| Checkpoint | Thành viên 1 (Lead) | Thành viên 2 (Data & RAG) | Thành viên 3 (Observability & Eval) |
| :--- | :--- | :--- | :--- |
| **CP0** (0–30') | Fork repo, add collaborators, setup `.env`; viết `parse_crossref_payload`, `fetch_source_records` (fallback snapshot / 429), `load_raw_records` | Setup venv, chạy smoke test; đọc `core/config.py` + schema `PaperRecord`, phác thảo `cleaning.py` | Setup venv, chạy smoke test; đọc tài liệu GX 1.x, dựng khung ephemeral context trong `quality.py` |
| **CP1** (30–65') | Review & hỗ trợ ghép `crossref.py` ↔ `cleaning.py` | `build_clean_dataframe`: dedupe `paper_id`, tính `age_days`, ghép `text_for_embedding` → 24 dòng | `run_data_quality_checks` (4 expectations GX 1.x) + `build_freshness_report` (cảnh báo khi >25% bài có `age_days > 180`) |
| **CP2** (65–95') | Nối các bước vào `phase1.py` | Kiểm tra `retrieval/` (MiniLM + Chroma), index collection `papers-baseline` 24 docs | `build_test_set`: 10 câu hỏi, đủ 4 nhóm `summary`/`authors`/`date`/`categories` → `data/eval/test_set.json` |
| **CP3** (95–120') | Chạy `script/run_phase1.py` end-to-end, fix lỗi tích hợp | Kiểm tra Hit Rate / Token F1 hợp lý, tinh chỉnh retrieval nếu cần | `generate_phase1_report` → `data/reports/phase1_report.md` |
| **CP4** (120–165') | Khung `corruption_flow.py`: corrupt → quality gate → index `papers-corrupted` → evaluate | `corrupt_clean_dataframe`: 6 lỗi (drop latest 20%, blank summary, noise, truncate title, stale date, duplicate) + `corruption_log.json` | Xác nhận Quality Gate & Freshness báo `False` trên data lỗi, ghi `corrupted_metrics.json` |
| **CP5** (165–210') | Repair idempotent từ raw → `papers-repaired`, chạy `script/run_corruption_flow.py` 2 lần để chứng minh idempotent | Hỗ trợ repair, kiểm tra 3 collection độc lập | `generate_corruption_report`: bảng 3 cột Baseline vs Corrupted vs Repaired |
| **CP6** (210–240') | Trình bày demo trực tiếp | Trả lời Q&A về cleaning, corruption, vector store | Trình bày bảng 3 trạng thái, trả lời Q&A về GX 1.x & Freshness SLA |

> ⚠️ Mỗi thành viên tự commit phần mình phụ trách lên nhánh `main` (kiểm tra ở Insights > Contributors) và tự viết báo cáo cá nhân trong `report/`.

---

## # Cá nhân

### ## HoVaTen1-MSSV1
- **Vai trò:** Trưởng nhóm, Ingestion & Điều phối Pipeline.
- **Công việc chi tiết đã hoàn thành:**
  - Khởi tạo repo nhóm, quản lý cấu hình `core/config.py`, `core/utils.py` và `.env`.
  - Xây dựng module thu thập Crossref API với cơ chế Fallback offline trong `src/ingestion/crossref.py`, lưu 2 raw artifacts.
  - Kết nối luồng thực thi trong `src/pipelines/phase1.py` và `src/pipelines/corruption_flow.py`, thực thi Idempotent Repair từ raw snapshot.
- **Điều học được / Đóng góp chính:**
  - Thiết kế Idempotent Pipeline, bảo toàn raw snapshot (Data Lineage) và quản lý trạng thái luồng dữ liệu đa tầng.

### ## HoVaTen2-MSSV2
- **Vai trò:** Phụ trách Làm sạch dữ liệu, Tiêm lỗi & RAG Vector Index.
- **Công việc chi tiết đã hoàn thành:**
  - Chuẩn hóa schema, khử trùng lặp, tính `age_days` và `text_for_embedding` trong `src/ingestion/cleaning.py`.
  - Triển khai 6 kịch bản làm bẩn dữ liệu trong `src/ingestion/corruption.py` và ghi `corruption_log.json`.
  - Quản lý embedding `all-MiniLM-L6-v2` và 3 collection ChromaDB (`papers-baseline`, `papers-corrupted`, `papers-repaired`).
- **Điều học được / Đóng góp chính:**
  - Ảnh hưởng của từng dạng lỗi dữ liệu lên chất lượng retrieval và cách cô lập không gian vector để so sánh khách quan.

### ## HoVaTen3-MSSV3
- **Vai trò:** Phụ trách Data Observability & Benchmark Evaluation.
- **Công việc chi tiết đã hoàn thành:**
  - Thiết lập Quality Gate theo chuẩn **Great Expectations 1.x** và giám sát Freshness SLA trong `src/observability/quality.py`.
  - Xây dựng bộ câu hỏi đánh giá chuẩn trong `src/evaluation/testset.py`.
  - Sinh báo cáo `phase1_report.md` và bảng đối chiếu 3 trạng thái `corruption_report.md` trong `src/observability/reporting.py`.
- **Điều học được / Đóng góp chính:**
  - Thiết lập hệ thống cảnh báo sớm chặn đứng Silent Failure trước khi dữ liệu vào serving layer.
