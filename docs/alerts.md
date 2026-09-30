# Template Alert và Runbook

Mỗi alert phải dựa trên triệu chứng người dùng hoặc SLO, không dựa trực tiếp vào tên implementation nội bộ.

## Alert mẫu để tham khảo

Ví dụ dưới đây minh họa mức độ cụ thể cần có. Học viên không cần copy nguyên, nhưng ba alert trong bài nộp nên rõ ràng tương tự: điều kiện là gì, kéo dài bao lâu, ảnh hưởng tới user ra sao và người trực cần kiểm tra gì trước.

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: latency P95 của `response_sent.latency_ms`
- Điều kiện và thời gian duy trì: `p95(latency_ms) > 3000ms` trong 5 phút
- Ảnh hưởng tới người dùng: người dùng phải chờ lâu hơn trước khi nhận câu trả lời
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard latency để xác nhận P95/P99 và khoảng thời gian tăng.
  2. Lọc `data/logs.jsonl` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao.
  3. Mở trace cùng `correlation_id` trên Langfuse, so sánh các span chính để xác định bước nào bất thường.
- Mitigation tạm thời: dựa trên evidence thực tế để rollback prompt, khôi phục cấu hình liên quan, tắt practice scenario hoặc giảm tải khi demo.
- Owner: `student-<MSSV>`

## Alert 1

- Tên: `HighLatencyP95`
- Severity: `warning`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` (`latency_ms <= 3000`, 99.5% / 28 ngày); panel **Latency percentiles and TTFT**
- Điều kiện và thời gian duy trì: `p95(response_sent.latency_ms) > 3000ms` liên tục 5 phút. Baseline bình thường P95 ≈ 1125 ms, nên vượt 3000 ms là chậm gần gấp ba.
- Ảnh hưởng tới người dùng: phải chờ ≥ 3 giây mới có câu trả lời; mỗi request chậm tiêu error budget của SLO.
- Ba bước kiểm tra đầu tiên:
  1. Mở dashboard panel Latency: xác nhận P95/P99 tăng từ lúc nào, TTFT P95 có tăng theo không (TTFT không đổi mà latency tăng → chậm trước bước LLM).
  2. Lọc `data/logs.jsonl` event `response_sent` trong khoảng đó, lấy một `correlation_id` có `latency_ms` cao nhất.
  3. Mở trace cùng `correlation_id` trên Langfuse, so thời gian `retrieval` với `llm-generation` để biết bước nào chậm.
- Mitigation tạm thời: nếu `retrieval` chậm → khôi phục/tắt cấu hình vector store gây chậm (`scripts/inject_incident.py --scenario rag_slow --disable` khi luyện tập), giảm tải; nếu `llm-generation` chậm → rollback prompt `production` về version trước.
- Owner: `student-2A202602846`

## Alert 2

- Tên: `HighErrorRateOrRetrievalFailing`
- Severity: `critical`
- Duration: `5m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: SLO `fast_successful_requests` (request lỗi là bad event); guardrail `error_rate_pct_max: 2`, `retrieval_success_rate_pct_min: 90`; panel **Error rate and retrieval success**
- Điều kiện và thời gian duy trì: `error_rate_pct > 2%` **hoặc** `tool_success_rate_pct < 90%` liên tục 5 phút. Baseline: error rate 0%, retrieval success 100%.
- Ảnh hưởng tới người dùng: nhận HTTP 500 thay vì câu trả lời, hoặc câu trả lời thiếu context tài liệu. Tiêu error budget nhanh nhất nên để `critical`.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Errors: xem error rate, breakdown theo `error_type` và retrieval success giảm từ lúc nào.
  2. Lọc log event `request_failed` lấy `error_type`, `tool_name`, `payload.detail` và một `correlation_id`.
  3. Mở trace cùng `correlation_id`: observation nào có `level=ERROR` (`retrieval` ghi `status_message` là tên exception).
- Mitigation tạm thời: nếu lỗi ở `retrieval` → chuyển sang fallback answer không dùng tài liệu hoặc khôi phục vector store (`--scenario tool_fail --disable` khi luyện tập); nếu lỗi sau khi đổi prompt/deploy → rollback.
- Owner: `student-2A202602846`

## Alert 3

- Tên: `CostPerRequestSpike`
- Severity: `warning`
- Duration: `15m`
- Kênh thông báo: Slack `#k4-l3b-alerts`
- SLI/SLO liên quan: guardrail `daily_cost_usd_max: 2.5`; panel **Cost over time** và **Input and output tokens**
- Điều kiện và thời gian duy trì: `avg(cost_usd) > 0.004 USD/request` (≈ 2x baseline $0.002017) **hoặc** chi phí ngoại suy theo ngày > 2.5 USD, liên tục 15 phút. Duration dài hơn vì cost không làm hỏng trải nghiệm ngay lập tức.
- Ảnh hưởng tới người dùng: không thấy ngay, nhưng vượt ngân sách; output quá dài thường kèm câu trả lời dài dòng và latency cao hơn.
- Ba bước kiểm tra đầu tiên:
  1. Mở panel Cost và Tokens: cost tăng do `tokens_in` hay `tokens_out`? Traffic có tăng tương ứng không (cost tăng do nhiều request thì không phải lỗi).
  2. Lọc log `response_sent` lấy `correlation_id` có `tokens_out`/`cost_usd` cao nhất.
  3. Mở trace cùng `correlation_id`, xem `usage_details`/`cost_details` của `llm-generation` và `prompt_version` đang dùng.
- Mitigation tạm thời: rollback prompt `production` về version có output ngắn hơn, giới hạn max output tokens, hoặc tắt cấu hình gây tăng token (`--scenario cost_spike --disable` khi luyện tập).
- Owner: `student-2A202602846`
