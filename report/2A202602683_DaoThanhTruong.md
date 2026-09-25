# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Đào Thanh Trường |
| MSSV | 2A202602683 |
| Khóa/Lớp | K4 — H205 |
| Tên nhóm | DoMixi |
| Vai trò chính | Data Transformation, Corruption & RAG Index |
| Repository | https://github.com/PhucBao1/K4-L3-DAY10-DoMixi-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Làm sạch dữ liệu | `src/ingestion/cleaning.py` (`build_clean_dataframe`) | 24 bài từ `crossref.py`, ngày chạy | Bảng 24 dòng × 16 cột → `papers_clean.csv/json` | Hoàn thành |
| Tiêm lỗi dữ liệu | `src/ingestion/corruption.py` (`corrupt_clean_dataframe`) | Bảng dữ liệu sạch | Bảng bị lỗi (23 dòng) + `corruption_log.json` | Hoàn thành |
| Vector index | `src/retrieval/index.py` (sửa `build`/`load`) | Dữ liệu sạch / lỗi / đã sửa | 3 collection ChromaDB | Hoàn thành |

Em nhận dữ liệu từ phần của Phúc Bảo (`crossref.py`). Bảng dữ liệu sạch của em được Ngọc Bảo dùng để kiểm tra chất lượng và sinh đề thi, rồi được đưa vào ChromaDB. Bước repair của Phúc Bảo cũng gọi lại chính hàm làm sạch của em, nên hàm này phải chạy lần nào cũng ra y hệt.

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Thống nhất tên cột với phần retrieval | `index.py`, Phúc Bảo | Các cột `authors_joined`, `categories_joined`, `published` khớp với metadata ChromaDB |
| Dùng chung hàm tạo `text_for_embedding` cho phần tiêm lỗi | `corruption.py` | Dữ liệu lỗi được embed lại đúng với nội dung đã bị hỏng |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Bỏ tag HTML, chuẩn hóa khoảng trắng, bỏ tác giả trùng, loại bài thiếu thông tin, bỏ bài trùng `paper_id` | `cleaning.py` | 24 dòng sạch, không dòng nào bị loại | Lệnh CP1 in `Clean thành công 24 dòng` |
| Tính `age_days`, `summary_chars`, ghép `text_for_embedding` 5 phần | `cleaning.py` | `age_days` từ 65 đến 181 ngày | `papers_clean.json` |
| 6 kiểu lỗi dữ liệu, cố định seed, ghi log chi tiết | `corruption.py` | 24 → 23 dòng, log đủ 6 loại | `corruption_log.json` |
| Lưu đường dẫn ChromaDB dạng tương đối | `index.py` | File manifest ghi `data/chroma` thay vì `D:\...` | Mở `data/embeddings/*.json` |

File log lỗi của em là thứ giúp cả nhóm giải thích được từng câu sai. Ví dụ câu eval_002 sai vì bài 807 nằm trong danh sách bị xóa, còn câu eval_003 sai vì bài 824 bị lùi ngày từ `2026-06-12` về `2025-06-12`.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Dữ liệu raw chưa dùng được ngay: abstract còn tag HTML, ngày tháng nhiều dạng, tác giả là list object. Muốn embed thì mỗi bài phải là một dòng gọn gàng, có một đoạn văn đủ thông tin để trả lời cả 4 loại câu hỏi. Ngược lại, để chứng minh hệ thống bị ảnh hưởng thế nào khi dữ liệu hỏng, nhóm cần một bộ lỗi có kiểm soát và chạy lại được.

### Cách triển khai

**Làm sạch:**
- Mọi trường chữ đều qua một hàm chung: bỏ tag HTML → giải mã ký tự như `&amp;` → gộp khoảng trắng. Bước lấy dữ liệu của Phúc Bảo đã bỏ tag rồi, nhưng em vẫn làm lại để phần của mình không phụ thuộc vào bước trước.
- DOI viết thường hết. Ngày không đọc được thì bỏ dòng đó.
- `age_days` là số ngày từ ngày xuất bản tới ngày chạy.
- Nếu có 2 dòng cùng `paper_id` thì giữ bản cập nhật mới nhất.
- Cuối cùng sắp xếp bài mới lên đầu để thứ tự lần nào cũng như nhau.

**Tiêm lỗi:** em xếp bài mới nhất lên đầu rồi làm lần lượt:
1. Xóa 5 bài mới nhất (20%).
2. Dùng random với seed 42 để chia các dòng còn lại thành 4 nhóm **không trùng nhau**: 3 dòng bị xóa tóm tắt, 3 dòng bị chèn ký tự rác, 3 dòng bị cắt tiêu đề còn 7 ký tự, 5 dòng bị lùi ngày 365 ngày.
3. Tạo lại `text_for_embedding` từ dữ liệu đã hỏng.
4. Nhân đôi 4 dòng ngẫu nhiên.
5. Ghi hết vào log, kèm tiêu đề và ngày gốc trước khi bị sửa.

**Index:** em sửa để file manifest lưu đường dẫn tương đối, khi đọc lại thì ghép với thư mục project.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | List 24 `PaperRecord`, ngày chạy (nếu không có múi giờ thì coi là UTC) |
| Output | Bảng 16 cột; `published` và `updated` là chuỗi `YYYY-MM-DD` |
| Module phụ thuộc | `crossref.py`, `core/utils.py` |
| Module sử dụng output | `quality.py`, `testset.py`, `index.py`, 2 pipeline |
| Điều kiện lỗi cần xử lý | Danh sách rỗng, bài thiếu title/tóm tắt/DOI, ngày sai định dạng, DOI trùng, tên tác giả rỗng hoặc trùng |

### Cách xác minh

```bash
python -c "from datetime import datetime, timezone; from core.config import load_settings; from ingestion.crossref import load_raw_records; from ingestion.cleaning import build_clean_dataframe; s=load_settings(); df=build_clean_dataframe(load_raw_records(s.paths.raw_records_json), datetime.now(timezone.utc)); print(f'Tín hiệu hoàn thành: Clean thành công {len(df)} dòng')"
python -c "from core.config import load_settings; from ingestion.corruption import corrupt_clean_dataframe; import pandas as pd; s=load_settings(); df=pd.read_json(s.paths.clean_json); c=corrupt_clean_dataframe(df, s.paths.corruption_log); print(f'Tín hiệu hoàn thành: Corrupted {len(c)} dòng')"
```

- **Kết quả mong đợi:** 24 dòng sạch; log ghi đủ 6 loại lỗi.
- **Kết quả thực tế:** `Clean thành công 24 dòng` và `Corrupted 23 dòng`. Chạy lại nhiều lần vẫn ra cùng danh sách bài bị lỗi nhờ cố định seed.
- **Artifact/log:** `data/clean/papers_clean.json`, `data/clean/papers_clean_corrupted.json`, `data/results/corruption_log.json`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** sau khi làm hỏng tóm tắt, tiêu đề hay ngày, có cần tạo lại đoạn văn `text_for_embedding` không?
- **Các phương án đã cân nhắc:** (1) chỉ sửa các cột gốc, giữ nguyên đoạn văn cũ; (2) tạo lại đoạn văn từ dữ liệu đã hỏng.
- **Phương án đã chọn:** (2).
- **Lý do:** nếu giữ đoạn văn cũ thì vector trong ChromaDB vẫn tính từ nội dung sạch, tìm kiếm gần như không bị ảnh hưởng, và thí nghiệm sẽ cho thấy lỗi ít nguy hiểm hơn thực tế. Ngoài đời, dữ liệu hỏng ở đầu nguồn sẽ kéo theo mọi thứ phía sau. Em cũng chia 4 nhóm dòng không trùng nhau để mỗi câu sai truy được về đúng một loại lỗi.
- **Bằng chứng quyết định phù hợp:** Great Expectations fail đúng 4 expectation tương ứng 4 loại lỗi, và từng câu sai trong bảng đều khớp với một dòng trong log.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** file `data/embeddings/papers_embeddings.json` lưu `"persist_path": "D:\\AIthucchien\\K4-L3-DAY10-DoMixi-DataPipeline\\data\\chroma"`.
- **Lệnh hoặc bước tái hiện:** chạy `python script/run_phase1.py` rồi mở file manifest. Trên máy khác, đường dẫn này không tồn tại nên dashboard không đọc được ChromaDB.
- **Nguyên nhân gốc:** hàm `build` trong `index.py` lưu đường dẫn tuyệt đối, và hàm `load` dùng luôn đường dẫn đó. Rubric cũng trừ điểm nếu hardcode đường dẫn kiểu `D:\...`.
- **Cách xử lý:** lưu đường dẫn tương đối so với thư mục project (`data/chroma`). Khi `load`, nếu gặp đường dẫn tương đối thì ghép với thư mục project, nên file manifest cũ vẫn đọc được.
- **Cách xác minh sau khi sửa:** chạy lại pipeline, file manifest ghi `"persist_path": "data/chroma"`, và tab "Hỏi thử RAG" trên dashboard đọc được cả 3 collection.
- **Điều học được:** file kết quả được commit lên repo cũng là "code" mà người khác sẽ dùng, nên không được chứa đường dẫn riêng của máy mình.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Dữ liệu raw từ Crossref được parse thành từng bài, em làm sạch rồi ghép mỗi bài thành một đoạn văn 5 dòng. Model MiniLM biến đoạn văn thành vector 384 chiều. Vector được lưu vào ChromaDB kèm thông tin phụ (tiêu đề, tác giả, ngày, lĩnh vực, tóm tắt) để lúc trả lời lấy ra dùng.
2. Mỗi câu hỏi đã biết trước DOI đúng. Nếu DOI đó có trong 4 kết quả tìm được thì tính là hit. Câu trả lời thì so với đáp án bằng Token F1 và LLM Judge.
3. Great Expectations kiểm tra từng dòng có hợp lệ không, ví dụ trùng `paper_id`, tiêu đề quá ngắn, tóm tắt rỗng. Freshness kiểm tra cả bộ có còn mới không. Trong các lỗi em tạo, nhân đôi dòng và cắt tiêu đề bị Great Expectations bắt, còn lùi ngày thì làm freshness báo đỏ.
4. Để khi điểm thay đổi thì biết chắc là do dữ liệu, không phải do đề khác đi.
5. Khi Quality Gate đạt lại 8/8, freshness báo Fresh, điểm sau repair bằng baseline, và file `repair_summary.json` xác nhận chạy 2 lần ra y hệt.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.70 | 1.00 | 2 câu sai do bài bị xóa (807, 812), 1 câu do tiêu đề bị cắt (805) |
| `mean_token_f1` | 1.000 | 0.774 | 1.000 | |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | |
| `mean_judge_score` | 5.0 | 4.1 | 5.0 | |
| Quality checks | 8/8 | 4/8 | 8/8 | Trùng `paper_id`: 8 dòng (4 cặp). Tiêu đề ngắn: 5 dòng (3 bài bị cắt + 2 bản nhân đôi của chúng) |
| Freshness status | Fresh | Stale | Fresh | 6/23 bài quá hạn = 5 bài bị lùi ngày + 1 bài vốn đã 181 ngày |

### Kết luận từ số liệu

1. Nhân đôi 4 dòng làm Great Expectations báo trùng `paper_id` ở 8 dòng. Ở câu eval_002, bài 819 (bị nhân đôi) chiếm luôn 2 trong 4 chỗ của kết quả tìm kiếm, đẩy các bài khác ra ngoài. Dữ liệu trùng không làm hệ thống sập, nhưng làm ngữ cảnh gửi cho agent nghèo đi.
2. Repair gọi lại hàm làm sạch của em trên file raw, bỏ trùng xong thì `paper_id` lại duy nhất, Quality Gate về 8/8 và Hit Rate về 1.00.

Lỗi ảnh hưởng nhiều nhất là **xóa bài mới nhất** (gây ra 2 trong 3 câu tìm sai), vì bài không còn trong kho. Đứng thứ hai là **cắt tiêu đề**, vì nó làm hỏng bước tra cứu chính xác theo tên bài.

Kết quả khác với em nghĩ: bài 821 cũng bị cắt tiêu đề nhưng câu eval_004 vẫn đúng. Xem `corrupted_answers.json` thì thấy tìm kiếm theo nghĩa vẫn ra đúng bài nhờ phần tóm tắt trong đoạn văn còn nguyên. Còn với bài 805 (câu eval_010), kết quả tìm được lại là bài 817 có cùng tác giả. Vậy cắt tiêu đề nguy hiểm tới đâu còn tùy nội dung còn lại của bài có đủ khác biệt không.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Hàm làm sạch phải cho ra cùng một kết quả mỗi lần chạy, vì repair dựa hoàn toàn vào việc chạy lại nó.
2. Tiêm lỗi phải có seed và log rõ ràng, không thì không cách nào truy từ một câu trả lời sai về đúng dòng dữ liệu gây ra nó.
3. Dữ liệu trùng không gây lỗi đỏ mà lặng lẽ chiếm chỗ trong kết quả tìm kiếm.

### Nếu có thêm thời gian

Em muốn bỏ trùng theo cả nội dung (so tiêu đề + tóm tắt) chứ không chỉ theo `paper_id`. Bộ dữ liệu có nhiều bài kiểu "Advanced Perspectives on …" gần giống bài gốc, và đó chính là lý do câu eval_001 tìm nhầm bài. Cách đo: đếm số cặp bài gần trùng tìm được, và xem tỷ lệ tìm đúng bài ở vị trí số 1 của các câu hỏi tóm tắt có tăng không.

## 10. Cam kết của thành viên

- [ ] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ ] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ ] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [ ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ ] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [ ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Đào Thanh Trường
**Ngày xác nhận:** 2026-09-25
