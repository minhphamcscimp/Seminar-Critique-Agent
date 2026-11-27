# Vân — bàn giao D3 (kiểm tra ngày 27/11/2026)

## Đã triển khai trong workspace (chưa phải tag/release)

- Benchmark lookup có timeout 10 giây; Gemini client đã có timeout 120 giây, backoff tối đa 4 lần (429 và lỗi server tạm thời). Test mô phỏng timeout và 429 chạy offline.
- Mỗi agent chấp nhận văn bản tự do/Markdown; phản hồi rỗng hoặc JSON được trả về nhưng hỏng sẽ thử thêm đúng 1 lần, sau đó **báo lỗi**, không coi là thành công. Pipeline không yêu cầu mọi agent trả JSON.
- Trace mới: `traces/<config>/<run_id>.jsonl`, mỗi dòng có `run_id`, thời gian và loại sự kiện. Ghi input task, chunk truy xuất, tool call/result, agent input/output/model/usage, retry, quyết định reflection, kết quả hoặc lỗi. Trace `.json` cũ vẫn được lưu cho các công cụ hiện có.
- `eval/results/results.csv` mới có `run_id`, `error`, `retries`, `reflection_iters`, `reflection_changed`, `trace_path`. Run lỗi giữ trong CSV nhưng không được tính là kết quả thành công; `eval/summarize.py` loại lỗi khỏi điểm trung bình và nêu số run lỗi. Resume yêu cầu CSV cùng schema mới; nên dùng output CSV mới thay vì resume file D2.
- Kiểm thử offline: `python -m pytest -q` đã đạt 100 test (27/11/2026).

## R2 / R3 — chỉ báo cáo theo bằng chứng có sẵn

- CSV D2 lưu 9 task × 3 config × 3 lần (27 lượt C), nhưng trong `traces/C/` chỉ có **2 trace JSON**, không phải 27; do đó không thể kết luận tỉ lệ dừng sớm trong 27 lượt.
- `traces/C/huang-intrinsic-self-correction_run0.json`: reflection đầu trả `NO CHANGE`, dừng ở vòng đầu và giữ bản Synthesizer. Tool lookup trong trace này có `found: false` do lookup theo topic (trace cũ).
- `traces/C/example-01_run0.json`: có 2 bước reflection (FakeLLM). Không suy ra chất lượng thực tế từ FakeLLM.
- Theo ngưỡng R3 (>50% lượt C dừng vòng đầu), hiện **chưa có đủ bằng chứng để chọn (a)**. Giữ config B như ablation và **chưa sửa logic reflection**; cần Tâm xác nhận quyết định và chạy lại/thu thập đủ trace trước khi kết luận B=C hoặc lập kế hoạch sửa.

## Còn phụ thuộc hoặc chưa thực hiện

- Bảng góp ý D1/D2 và file PDF phản hồi: cần email/phản hồi thực tế của thầy; chưa có trong repo.
- Phân tích ba task B thua A: cần Tâm cung cấp trace B tương ứng (hiện thư mục traces không chứa đủ 27 lượt) và kết luận theo từng task.
- Chạy task thật với Gemini, chọn demo và công bố số đo: cần API key/quota cùng phiên bản đã freeze. Không dùng FakeLLM làm kết quả chất lượng.
- PR review/merge, tag `d3-freeze`, `final`, push remote, ghép report/PDF, video và email nộp: cần kết quả/PR của Minh–Tín–Tâm, mốc freeze thống nhất và xác nhận của nhóm. Chưa tạo tag hoặc push khi chưa đủ phụ thuộc.
- Trước freeze cần Tâm kiểm tra các cột CSV mới; Minh/Tín xác nhận retriever/tool trên bộ 24 task; không tuyên bố hệ thống đã đạt acceptance D3 khi bộ task hiện vẫn 9.

## Chạy thử offline

Tại thư mục gốc repo, chạy `python -m pytest -q` để kiểm tra, sau đó `python -m seminar_critique.run --task eval/tasks/example_task.json --config C --llm fake` để tạo trace JSON và JSONL. Để tránh ghi đè CSV D2, chỉ chạy `eval.runner` với `--out` trỏ tới file CSV mới và `--traces` trỏ tới thư mục mới.
