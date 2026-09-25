# Member Role Report — Day 10: Data Pipeline & Data Observability

## 1. Thông tin cá nhân

| Thông tin | Nội dung |
| --- | --- |
| Họ và tên | Nguyễn Phúc Bảo |
| MSSV | 2A202602925 |
| Khóa/Lớp | K4 — H205 |
| Tên nhóm | DoMixi |
| Vai trò chính | Trưởng nhóm — Ingestion & Pipeline Integrator |
| Repository | https://github.com/PhucBao1/K4-L3-DAY10-DoMixi-DataPipeline |
| Ngày hoàn thành | 2026-09-25 |

## 2. Vai trò và phạm vi công việc

### Phần việc sở hữu

| Module/deliverable | File/hàm phụ trách | Input nhận vào | Output bàn giao | Trạng thái |
| --- | --- | --- | --- | --- |
| Lấy dữ liệu Crossref | `src/ingestion/crossref.py` | Crossref API hoặc file snapshot `crossref_response.json` | `data/raw/crossref_records.json` (24 bài) | Hoàn thành |
| Pipeline baseline | `src/pipelines/phase1.py` | Cấu hình + raw records | Dữ liệu sạch, collection `papers-baseline`, `baseline_metrics.json`, `phase1_report.md` | Hoàn thành |
| Pipeline corruption & repair | `src/pipelines/corruption_flow.py` | Dữ liệu sạch, test set, raw records | Metrics/báo cáo của 3 trạng thái | Hoàn thành |
| Dashboard demo | `script/dashboard.py` | Các file trong `data/` | Giao diện Streamlit | Hoàn thành |
| Môi trường & artifact cuối | `pyproject.toml`, `uv.lock`, `.gitattributes`, `data/` | Code của cả nhóm | Artifact sinh lại từ bản nộp | Hoàn thành |

Phần của em nằm ở hai đầu: đầu vào dữ liệu và phần nối các module lại với nhau. File em tạo ra (`crossref_records.json`) là đầu vào cho `cleaning.py` của Trường. Hai pipeline của em gọi tới code của cả Trường (`cleaning.py`, `corruption.py`, `index.py`) lẫn Ngọc Bảo (`quality.py`, `testset.py`, `reporting.py`).

### Việc hỗ trợ ngoài phạm vi chính

| Hoạt động | Thành viên/module được hỗ trợ | Kết quả |
| --- | --- | --- |
| Chia việc, sắp thứ tự push lên `main` | Cả nhóm | Mỗi người có commit riêng cho phần của mình |
| Ghép code và chạy lại toàn bộ sau khi mọi người push | Trường, Ngọc Bảo | Cả 2 script chạy thành công trên bản cuối |
| Sửa cách lưu ChromaDB để chạy được trên máy khác | `index.py`, `data/chroma` | Đường dẫn tương đối + `.gitattributes` |

## 3. Kết quả theo vai trò

| Nhiệm vụ đã thực hiện | File/hàm/artifact liên quan | Kết quả bàn giao | Cách xác minh |
| --- | --- | --- | --- |
| Parse dữ liệu Crossref: bỏ tag `<jats:p>`, ghép tên tác giả, đổi ngày về `YYYY-MM-DD` | `parse_crossref_payload` | 24/24 bài hợp lệ | Lệnh CP0 in `Đã tải 24 bài báo` |
| Mặc định đọc file offline, chỉ gọi API khi cần, có retry khi bị 429 | `fetch_source_records` | Chạy được cả khi mất mạng | Log `[crossref] Offline mode: ...` |
| Dữ liệu không qua Quality Gate thì dừng, không đưa vào ChromaDB | `phase1.py` | | Đọc code, `phase1_report.md` |
| Tách luồng lỗi thành 2 bước (tiêm lỗi / repair), repair tự chạy khi phát hiện lỗi | `corruption_flow.py` | `repair_summary.json` | Log `[repair] Triggered by: ...` |
| Làm dashboard để demo bằng nút bấm | `dashboard.py` | 6 tab | `streamlit run script/dashboard.py` |

Kết quả em thấy rõ nhất là bảng so sánh in ra cuối `run_corruption_flow.py`: Hit Rate đi từ 1.00 xuống 0.70 rồi lên lại 1.00, kèm dòng log cho biết repair tự chạy vì *"quality gate failed, freshness SLA violated"*.

## 4. Giải thích phần kỹ thuật đã thực hiện

### Vấn đề cần giải quyết

Em cần hai thứ. Thứ nhất, một nguồn dữ liệu đầu vào ổn định: chạy lúc nào, trên máy nào cũng ra đúng 24 bài như nhau, không phụ thuộc mạng. Thứ hai, một "đường ống" nối 7 bước theo đúng thứ tự, trong đó dữ liệu xấu phải bị chặn trước khi vào vector store.

### Cách triển khai

Về phần lấy dữ liệu: Crossref trả về abstract bọc trong tag `<jats:p>`, tác giả là list object `{given, family}`, còn ngày ở dạng `date-parts` như `[[2026, 5, 20]]`. Em viết hàm parse để:
- bỏ tag,
- ghép tên tác giả,
- lấy ngày theo thứ tự ưu tiên `published` → `published-online` → `published-print` → `issued`,
- bỏ những bài thiếu DOI, title, abstract hoặc ngày.

Mặc định pipeline đọc file snapshot có sẵn. Chỉ khi đặt `REFRESH_SOURCE=1` mới gọi API thật, và nếu API lỗi 429/5xx thì thử lại tối đa 4 lần. Em chỉ ghi đè file snapshot khi API trả về dữ liệu hợp lệ, để lỡ API trả về rỗng thì không mất dữ liệu gốc.

Về phần pipeline: `phase1.py` chạy theo thứ tự lấy dữ liệu → làm sạch → kiểm tra chất lượng → (không đạt thì dừng) → đưa vào ChromaDB → chấm điểm → viết báo cáo. Với luồng lỗi, em tách làm 2 bước:
- **Tiêm lỗi:** làm hỏng dữ liệu, chạy kiểm tra (sẽ báo đỏ), rồi vẫn cố tình đưa vào ChromaDB để đo xem agent bị ảnh hưởng thế nào.
- **Repair:** đọc lại file raw gốc, làm sạch lại từ đầu. Em chạy bước này 2 lần và so sánh hai kết quả để chắc là chạy bao nhiêu lần cũng ra y hệt.

### Input, output và contract

| Thành phần | Mô tả |
| --- | --- |
| Input | Cấu hình (query, filter, 24 bài, đường dẫn), file `crossref_response.json` |
| Output | List `PaperRecord` 11 trường + `crossref_records.json`; metrics và báo cáo 3 trạng thái |
| Module phụ thuộc | `core/`, `cleaning.py`, `quality.py`, `testset.py`, `reporting.py`, `index.py` |
| Module sử dụng output | `cleaning.py`, `dashboard.py` |
| Điều kiện lỗi cần xử lý | API lỗi/timeout, bài thiếu thông tin, chưa chạy baseline mà đã chạy corruption, repair xong vẫn không đạt Quality Gate |

### Cách xác minh

```bash
python -c "from core.config import load_settings; from ingestion.crossref import fetch_source_records; s=load_settings(); r=fetch_source_records(s); print(f'Tín hiệu hoàn thành: Đã tải {len(r)} bài báo')"
python script/run_phase1.py
python script/run_corruption_flow.py
```

- **Kết quả mong đợi:** tải đủ 24 bài, 2 script chạy xong không lỗi, điểm sau repair bằng baseline.
- **Kết quả thực tế:** đúng như vậy. `repair_summary.json` xác nhận chạy 2 lần ra giống nhau và khớp với dữ liệu baseline.
- **Artifact/log:** `data/raw/crossref_records.json`, `data/quality/repair_summary.json`, `data/reports/corruption_report.md`.

## 5. Một quyết định kỹ thuật quan trọng

- **Bối cảnh:** mỗi lần chạy nên gọi API Crossref lấy dữ liệu mới, hay dùng file snapshot?
- **Các phương án đã cân nhắc:** (1) luôn gọi API, file snapshot chỉ dùng khi lỗi; (2) mặc định dùng snapshot, chỉ gọi API khi bật `REFRESH_SOURCE=1`.
- **Phương án đã chọn:** (2).
- **Lý do:** filter của Crossref tính theo ngày chạy (`from-pub-date` = hôm nay trừ 180 ngày), nên mỗi lần gọi có thể ra một bộ 24 bài khác. Khi đó test set, điểm baseline và báo cáo sẽ không so sánh được giữa các lần chạy hay giữa máy các bạn. Mạng hôm làm lab cũng khá chập chờn. Ngoài ra file raw cố định còn là "nguồn sự thật" để repair đọc lại.
- **Bằng chứng quyết định phù hợp:** trong ngày nhóm chạy lại toàn bộ pipeline nhiều lần, lần nào cũng ra đúng 24 bài và cùng bộ điểm 1.00 / 0.70 / 1.00.

## 6. Một lỗi hoặc blocker đã xử lý

- **Triệu chứng/lỗi nguyên văn:** lúc chạy lại `run_phase1.py` trên bản code cuối, script dừng với lỗi `RuntimeError: Cannot send a request, as the client has been closed.` (trong `huggingface_hub`).
- **Lệnh hoặc bước tái hiện:** xóa `data/chroma` rồi chạy `python script/run_phase1.py` khi mạng yếu.
- **Nguyên nhân gốc:** model MiniLM đã có sẵn trên máy, nhưng thư viện vẫn kết nối HuggingFace để kiểm tra phiên bản, và mạng lỗi làm Phase 1 dừng giữa chừng. Điều em thấy nguy hiểm hơn: file `baseline_metrics.json` của lần chạy trước vẫn còn, nên khi chạy `run_corruption_flow.py` ngay sau đó nó vẫn báo thành công nhưng lại so với baseline cũ. Nếu không để ý exit code của Phase 1 thì em đã commit một bộ số liệu lệch nhau.
- **Cách xử lý:** chạy với `HF_HUB_OFFLINE=1` để dùng model có sẵn trên máy, rồi chạy lại **cả hai** script để mọi file kết quả ra từ cùng một lần chạy.
- **Cách xác minh sau khi sửa:** cả hai script đều kết thúc với exit code 0, ChromaDB có đúng 3 collection.
- **Điều học được:** bước sau chạy được không có nghĩa là bước trước đúng. Phải kiểm tra từng bước và không để file cũ "đứng thay" file mới.

## 7. Hiểu biết về luồng end-to-end

**Câu trả lời:**

1. Crossref trả về JSON. Em lưu nguyên bản vào `data/raw/`, rồi parse ra 24 bài. Trường làm sạch và ghép mỗi bài thành một đoạn văn 5 dòng (Title, Authors, Published, Categories, Summary). Qua được Quality Gate thì đoạn văn đó được model MiniLM chuyển thành vector và lưu vào ChromaDB.
2. Mỗi câu hỏi trong test set có sẵn DOI của bài đúng. Nếu bài đó nằm trong 4 kết quả tìm được thì tính là "hit". Còn câu trả lời thì so với đáp án bằng Token F1 (trùng từ) và LLM Judge (đúng về nghĩa).
3. Quality check xem từng dòng có hợp lệ không (trùng, rỗng, quá ngắn). Freshness xem cả bộ dữ liệu có còn mới không. Dữ liệu có thể sạch hết mà vẫn cũ.
4. Nếu đề thi thay đổi theo dữ liệu thì không biết điểm giảm là do dữ liệu hỏng hay do đề khác. Giữ nguyên đề thì mọi chênh lệch chỉ có thể do dữ liệu.
5. Repair thành công khi Quality Gate đạt lại 8/8, freshness báo Fresh, và điểm trong `repaired_metrics.json` bằng `baseline_metrics.json`.

## 8. Phân tích kết quả

### Metrics chính

| Metric/signal | Baseline | Corrupted | Repaired | Nhận xét của cá nhân |
| --- | --: | --: | --: | --- |
| `retrieval_hit_rate` | 1.00 | 0.70 | 1.00 | 3 câu không tìm được đúng bài |
| `mean_token_f1` | 1.000 | 0.774 | 1.000 | Giảm ít hơn Hit Rate vì có câu tìm sai bài mà vẫn trả lời trùng |
| `judge_accuracy` | 1.00 | 0.70 | 1.00 | Judge đánh sai đúng 3 câu thật sự sai |
| `mean_judge_score` | 5.0 | 4.1 | 5.0 | |
| Quality checks | 8/8 | 4/8 | 8/8 | Bắt được 4 trong 6 loại lỗi |
| Freshness status | Fresh (4%) | Stale (26%) | Fresh (4%) | Vượt ngưỡng 25% |

### Kết luận từ số liệu

1. Lỗi bỏ 20% bài mới nhất xóa mất bài của câu eval_001 và eval_002, freshness ghi nhận ngày mới nhất lùi từ 2026-07-22 về 2026-06-11. Hai câu này tìm sai bài, chiếm 0.20 trong mức giảm 0.30 của Hit Rate.
2. Repair làm sạch lại từ file raw nên Quality Gate về 8/8 và freshness về Fresh. Cả 4 chỉ số quay lại đúng như baseline trên cùng bộ đề.

Theo em, lỗi ảnh hưởng nặng nhất là **bỏ bài mới nhất**, vì bài đã bị xóa khỏi kho thì tìm kiếm giỏi đến mấy cũng không lấy lại được. Điều đáng lo là không có expectation nào của Great Expectations báo lỗi vì chuyện này: 23 dòng vẫn nằm trong khoảng cho phép. Chỉ có ngày mới nhất trong báo cáo freshness là để lộ dấu vết.

Kết quả khác với em dự đoán: em nghĩ lỗi chèn ký tự rác sẽ làm giảm Token F1, nhưng thực tế không. Xem lại `corruption_log.json` thì trong 3 bài bị chèn rác, chỉ có bài 815 nằm trong đề, và câu hỏi về bài đó là hỏi ngày xuất bản, không đụng tới phần tóm tắt bị chèn rác.

## 9. Điều học được và hướng cải thiện

### Ba điều quan trọng nhất

1. Luôn giữ bản raw gốc không bị sửa. Nhờ có nó, repair chỉ đơn giản là chạy lại bước làm sạch, không phải đi vá từng lỗi bằng tay.
2. Chỉ kiểm tra từng dòng là không đủ, phải kiểm tra cả độ mới của dữ liệu. Mất dữ liệu mới nhất vẫn qua được mọi check dạng từng dòng.
3. Agent không báo lỗi khi dữ liệu hỏng. Ở câu eval_002, nó trả lời sai hẳn tên tác giả nhưng vẫn tự tin như câu đúng.

### Nếu có thêm thời gian

Em sẽ thêm một kiểm tra so với lần chạy trước: số dòng giảm quá 10% hoặc ngày mới nhất bị lùi thì báo lỗi, để Quality Gate tự bắt được lỗi mất dữ liệu mới. Cách đo: chạy lại `run_corruption_flow.py` và xem `corrupted_quality_report.json` có thêm 1 expectation fail hay không.

## 10. Cam kết của thành viên

- [ x] Nội dung báo cáo phản ánh đúng phần việc và mức hiểu của tôi.
- [ x] Tôi có thể giải thích luồng end-to-end, không chỉ module mình phụ trách.
- [ x] Mọi kết luận về kết quả đều có artifact hoặc metric để đối chiếu.
- [x ] Tôi không ghi “đã chạy thành công” cho phần chưa được kiểm chứng.
- [ x] Báo cáo không chứa `.env`, API key, token hoặc secret.
- [x ] Báo cáo này không phải bản sao nguyên văn của báo cáo nhóm hoặc báo cáo thành viên khác.

**Họ và tên:** Nguyễn Phúc Bảo
**Ngày xác nhận:** 2026-09-25
