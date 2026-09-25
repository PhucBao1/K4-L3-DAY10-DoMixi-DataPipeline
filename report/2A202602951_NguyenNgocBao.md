# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Ngọc Bảo |
| MSSV | 2A202602951 |
| Khóa/Lớp | K4 — H205 |
| Tên nhóm | DoMixi |
| Vai trò chính | Observability & Evaluation |
| Repository | https://github.com/PhucBao1/K4-L3-DAY10-DoMixi-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Quality Gate (Great Expectations 1.x) | `src/observability/quality.py` (`run_data_quality_checks`) | Bảng dữ liệu (sạch / lỗi / đã sửa) | `data/quality/<tên>_quality_report.json` | Hoàn thành |
| Kiểm tra độ tươi (Freshness SLA) | `src/observability/quality.py` (`build_freshness_report`) | Bảng dữ liệu có `published`, `age_days` | `freshness_report.json` và 2 bản corrupted/repaired | Hoàn thành |
| Bộ đề đánh giá | `src/evaluation/testset.py` (`build_test_set`) | Bảng dữ liệu sạch | `data/eval/test_set.json` (10 câu) | Hoàn thành |
| Báo cáo markdown | `src/observability/reporting.py` | Điểm, kết quả kiểm tra, log lỗi, câu trả lời | `phase1_report.md`, `corruption_report.md` | Hoàn thành |

Phần của em nhận dữ liệu từ Trường (làm sạch và tiêm lỗi). Kết quả Quality Gate của em được Phúc Bảo dùng ở hai chỗ: chặn không cho dữ liệu xấu vào ChromaDB, và làm tín hiệu để tự chạy repair.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Đề xuất thêm expectation để bắt đúng các lỗi mà Trường tiêm vào | `corruption.py` | Lỗi cắt tiêu đề và lùi ngày đều bị phát hiện |
| Kiểm tra LLM Judge có thật sự dùng LLM không | `metrics.py`, cấu hình `.env` | Phát hiện judge đang chấm bằng heuristic, sửa xong thì 0/40 câu dùng heuristic |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Quality Gate theo cú pháp GX 1.x: 4 expectation bắt buộc + 2 expectation em thêm | `quality.py` | Dữ liệu sạch 8/8 đạt, dữ liệu lỗi 4/8 | Lệnh CP1 in `Quality check status = True` |
| Freshness: cảnh báo khi hơn 25% bài cũ quá 180 ngày | `build_freshness_report` | Sạch 4.17% (Fresh), lỗi 26.09% (Stale) | Các file `*freshness_report.json` |
| Đề 10 câu, 4 loại, chọn bài trải đều từ mới đến cũ | `testset.py` | `test_set.json` | Lệnh CP2 in `Sinh được 10 câu hỏi test` |
| Báo cáo so sánh 3 trạng thái, có bảng từng câu | `reporting.py` | `corruption_report.md` | Đối chiếu với các file trong `data/results/` |

Kết quả cụ thể nhất của em là file `corrupted_quality_report.json`: nó chỉ rõ 4 expectation bị fail và số dòng vi phạm (trùng `paper_id` 8 dòng, tiêu đề ngắn 5 dòng, tóm tắt ngắn 3 dòng, quá hạn 6 dòng). Đây chính là tín hiệu làm repair tự chạy.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Khi dữ liệu hỏng, agent vẫn trả lời bình thường chứ không báo lỗi. Nhóm cần ba thứ: một "chốt kiểm dịch" phát hiện dữ liệu xấu **trước khi** nó vào vector store, một tín hiệu cho biết dữ liệu còn mới hay đã cũ, và một bộ đề cố định để đo điểm giảm bao nhiêu.

### Cách triển khai

**Quality Gate:** mỗi lần kiểm tra em tạo một context GX loại `ephemeral` (chạy trên RAM, không tạo file rác, lần chạy sau không bị trùng tên với lần trước). Trình tự là thêm data source pandas → tạo asset → tạo batch cho cả bảng. Em gom 8 expectation vào một suite rồi validate một lần, sau đó rút gọn kết quả (tên expectation, cột, đạt hay không, số dòng vi phạm) và ghi ra JSON.

**Hai expectation em thêm:**
- Tiêu đề phải dài ít nhất 8 ký tự.
- `age_days` phải từ 0 đến 180, với tham số `mostly=0.75`, tức là cho phép tối đa 25% bài vượt ngưỡng. Đây đúng là quy tắc Freshness SLA, nên độ tươi vừa có báo cáo riêng, vừa nằm trong Quality Gate.

**Bộ đề:** 10 câu theo thứ tự summary, authors, date, categories, lặp lại, rồi thêm 1 câu summary và 1 câu authors. Em chọn 10 bài ở các vị trí cách đều nhau trong danh sách đã sắp theo ngày, nên đề có cả bài mới nhất lẫn cũ nhất. Chọn như vậy thì lỗi "xóa bài mới nhất" chắc chắn đụng tới đề.

Một điểm quan trọng: câu hỏi phải dùng đúng từ khóa mà `qa.py` nhận diện ("who authored", "when was", "what categories") và để tên bài trong dấu `'...'`. Nếu viết khác đi, QA sẽ luôn trả về phần tóm tắt và điểm sẽ sai lệch.

**Báo cáo:** các con số và phần phân tích đều sinh tự động từ file kết quả, không viết tay số nào.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Bảng có `paper_id`, `title`, `summary`, `text_for_embedding`, `published`, `age_days`, `authors_joined`, `categories_joined` |
| Output | Kết quả kiểm tra (`success`, số expectation đạt, danh sách fail, chi tiết); báo cáo freshness (`is_fresh`, `stale_ratio`, `latest_published`...); 10 câu hỏi |
| Module phụ thuộc | Great Expectations 1.18, `cleaning.py`, `core/utils.py` |
| Module sử dụng output | `phase1.py` (chặn index), `corruption_flow.py` (kích hoạt repair), `metrics.py` (đề thi), `dashboard.py` |
| Điều kiện lỗi cần xử lý | Thiếu cột (GX ghi lỗi và trả `success = False`), bảng rỗng (`is_fresh = False`), không đủ 10 bài hợp lệ để ra đề (báo lỗi) |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from observability.quality import run_data_quality_checks; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); res=run_data_quality_checks(df, s, 'test'); print(f'Tín hiệu hoàn thành: Quality check status = {res[\"success\"]}')"
python -c "from core.config import load_settings; from evaluation.testset import build_test_set; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); ts=build_test_set(df, s.paths.eval_testset); print(f'Tín hiệu hoàn thành: Sinh được {len(ts)} câu hỏi test')"
```

- **Kết quả mong đợi:** `Quality check status = True`, `Sinh được 10 câu hỏi test`, và Quality Gate phải fail trên dữ liệu lỗi.
- **Kết quả thực tế:** đúng như vậy. Trên dữ liệu lỗi, GX trả về `success = False` với 4 expectation fail.
- **Artifact/log:** `data/quality/baseline_quality_report.json`, `data/quality/corrupted_quality_report.json`, `data/eval/test_set.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** chỉ dùng 4 expectation theo Guide, hay thêm expectation cho những lỗi mà Trường sẽ tiêm vào?
- **Các phương án đã cân nhắc:** (1) chỉ dùng 4 expectation bắt buộc; (2) thêm kiểm tra độ dài tiêu đề và kiểm tra `age_days` với `mostly=0.75`.
- **Phương án đã chọn:** (2).
- **Lý do:** với 4 expectation gốc, lỗi cắt tiêu đề (tiêu đề còn 7 ký tự nhưng không rỗng) và lỗi lùi ngày (ngày vẫn hợp lệ, chỉ là cũ) đều lọt qua. Nếu freshness chỉ nằm ở báo cáo riêng, pipeline không dùng nó để quyết định chặn hay repair. Gộp vào gate thì chỉ cần một tín hiệu `success` cho cả chất lượng lẫn độ tươi. Cái giá là gate chặt hơn: dữ liệu sạch hiện đã có 1/24 bài quá hạn, nên khoảng sau tháng 11/2026 gate sẽ fail nếu không lấy dữ liệu mới.
- **Bằng chứng quyết định phù hợp:** trên dữ liệu lỗi, 2 expectation em thêm chiếm một nửa số lần fail (tiêu đề 5 dòng, quá hạn 6 dòng). Trên dữ liệu sạch và dữ liệu đã sửa, cả 8 đều đạt, không có báo động nhầm.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** mọi dòng `reasoning` của judge trong `baseline_answers.json` đều là `"Fallback heuristic judge used because the LLM evaluator was unavailable."`, còn `agent_demo_answers.json` ghi `"Agent demo unavailable: GOOGLE_API_KEY is required when LLM_PROVIDER=gemini."`. Pipeline vẫn chạy xong, không báo lỗi gì.
- **Lệnh hoặc bước tái hiện:** chạy `python script/run_phase1.py` khi `.env` để `LLM_PROVIDER=gemini` nhưng chỉ có `OPENAI_API_KEY`, rồi đếm số lần chữ "Fallback" xuất hiện trong `baseline_answers.json`.
- **Nguyên nhân gốc:** khi không tạo được LLM, hàm chấm điểm tự chuyển sang chấm theo Token F1 mà không báo gì. Provider trong `.env` không khớp với key đang có, nên lỗi thiếu key bị "nuốt" mất. Lúc đó `judge_accuracy` thực chất chỉ là Token F1 đổi tên, chứ không phải LLM chấm.
- **Cách xử lý:** đổi cấu hình sang `LLM_PROVIDER=openai`, `LLM_MODEL=gpt-4o-mini` (không commit file `.env`), gọi thử một câu để chắc key dùng được, rồi chạy lại cả 2 pipeline để 3 trạng thái được chấm bởi cùng một judge.
- **Cách xác minh sau khi sửa:** chữ "Fallback" xuất hiện 0 lần trong cả 4 file answers. Judge đưa ra lý do thật, ví dụ câu eval_003: *"states the publication date as 2025-06-12, which is one year earlier…"*.
- **Điều học được:** cơ chế dự phòng giúp pipeline không sập, nhưng chính nó cũng là một kiểu "lỗi thầm lặng". Nhìn thấy con số thôi chưa đủ, phải kiểm tra con số đó được tính bằng cách nào.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu từ Crossref được lưu nguyên vào `data/raw/`, parse thành các bài báo, rồi làm sạch thành 24 dòng có `text_for_embedding`. Phải qua được gate của em thì dữ liệu mới được embed bằng MiniLM và nạp vào ChromaDB.
2. Mỗi câu trong đề có sẵn DOI đúng. Hit Rate đo xem hệ thống có *tìm đúng bài* không (DOI có trong top-4). Token F1 và LLM Judge đo xem có *trả lời đúng* không. Cần cả hai, vì câu eval_010 cho thấy trả lời đúng mà vẫn có thể là tìm sai bài.
3. Quality check hỏi "từng dòng có hợp lệ không": có rỗng không, có trùng không, có quá ngắn không. Freshness hỏi "cả bộ còn mới không". Ví dụ xóa 20% bài mới nhất không làm dòng nào sai, nhưng làm ngày mới nhất lùi gần 6 tuần.
4. Để điểm thay đổi chỉ có thể là do dữ liệu. Em sinh đề từ dữ liệu sạch và giữ cố định, nên các câu về bài đã bị xóa vẫn còn trong đề và mức giảm điểm đo được.
5. Repair thành công khi Quality Gate đạt 8/8, freshness báo Fresh, và điểm sau repair bằng baseline (1.00 / 1.00 / 1.00 / 5.0) trên cùng bộ đề.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.70 | 1.00 | Nhạy nhất với lỗi làm mất hoặc che bài |
| `mean_token_f1` | 1.000 | 0.774 | 1.000 | Không phạt câu eval_010 dù tìm sai bài |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | Judge phạt đúng câu eval_003 (sai 1 năm) |
| `mean_judge_score` | 5.0 | 4.1 | 5.0 | Câu eval_001 được 3/5: đúng ý chính nhưng lẫn nội dung bài khác |
| Quality checks | 8/8 | 4/8 | 8/8 | Bắt được 4/6 loại lỗi; lỗi xóa bài mới và chèn rác lọt qua |
| Freshness status | Fresh (4.17%) | Stale (26.09%) | Fresh (4.17%) | Chỉ vượt ngưỡng 25% khoảng 1 điểm %, ngưỡng hợp lý nhưng sát |

### Kết luận từ số liệu

1. Lỗi lùi ngày ở 5 bài làm tỷ lệ bài quá hạn tăng từ 4.17% lên 26.09%, nên freshness báo Stale và expectation `age_days` fail 6 dòng. Câu eval_003 vì thế trả lời `2025-06-12` thay vì `2026-06-12` (Token F1 = 0, judge 2/5).
2. Repair làm sạch lại từ file raw, tỷ lệ quá hạn về 4.17%, gate về 8/8, và `judge_accuracy` từ 0.70 lên lại 1.00.

Nếu nhìn vào điểm của agent thì lỗi nặng nhất là **xóa bài mới nhất** (2 câu mất bài). Nhưng nhìn từ góc kiểm tra dữ liệu thì nó còn đáng sợ hơn: không có expectation nào fail vì lỗi này, freshness cũng chỉ phản ánh gián tiếp qua ngày mới nhất.

Kết quả khác với em nghĩ: câu eval_010 tìm sai bài nhưng Token F1 vẫn 1.00 và judge cho 5/5. Xem `corrupted_answers.json` thì thấy hệ thống tìm ra bài 817 thay cho bài 805, mà hai bài này có cùng tác giả "Tuan Phan, Mai Bui". Điểm câu trả lời có thể che lỗi tìm kiếm, nên em để báo cáo luôn hiện cả hit/miss lẫn F1 cho từng câu.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Bộ đề phải thiết kế cùng với cách hệ thống trả lời. Câu hỏi không khớp từ khóa của QA thì điểm đo ra sẽ sai.
2. Quality Gate chỉ đáng tin khi đã thử nó trên dữ liệu lỗi. Pass trên dữ liệu sạch chưa chứng minh được gì cho tới khi nó fail đúng chỗ trên dữ liệu hỏng.
3. Phải kiểm tra cả cách con số được tạo ra: judge âm thầm chuyển sang heuristic mà con số vẫn trông rất hợp lý.

### Nếu có thêm thời gian

Em sẽ thêm một expectation bắt ký tự rác trong tóm tắt (regex tìm chuỗi như `#@!%`, `~~~`), và một expectation so ngày mới nhất với lần chạy trước để bắt lỗi xóa bài mới. Mục tiêu: Quality Gate bắt được 6/6 loại lỗi thay vì 4/6, trong khi dữ liệu sạch vẫn đạt hết.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Ngọc Bảo
**Ngày xác nhận:** 2026-09-25
