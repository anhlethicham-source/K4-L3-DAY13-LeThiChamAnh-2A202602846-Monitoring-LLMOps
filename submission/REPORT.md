# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Thị Châm Anh
- **MSSV:** 2A202602846
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/anhlethicham-source/K4-L3-DAY13-LeThiChamAnh-2A202602846-Monitoring-LLMOps
- **Commit SHA cuối:** _(điền sau commit cuối)_
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602846`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | _(chưa có — chạy ở CP4)_ |
| Log validator | `evidence/02-log-validator.txt` |
| Dashboard validator | `evidence/03-dashboard-validator.txt` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | _(chưa có)_ |
| Prompt rollback | _(chưa có)_ |
| Dashboard runtime | _(chưa có)_ |
| Incident metric | `evidence/12-incident-metric.txt` |
| Incident log | `evidence/13-incident-log.txt` |
| Incident trace | `evidence/14-incident-trace.txt` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 ([evidence](evidence/00-baseline.txt)) | 100/100 ([evidence](evidence/02-log-validator.txt)) | 0 correlation ID (`MISSING`), 20/21 record thiếu required field và enrichment |
| `validate_dashboard.py` | 6/6 panel (contract) | 6/6 panel ([evidence](evidence/03-dashboard-validator.txt)) + dashboard runtime `dashboard/app.py` | Validator chỉ kiểm tra contract YAML, chưa chứng minh dashboard runtime |
| `pytest` | Lỗi collection (`test_validate_logs.py`) | | Package `scripts` trong site-packages che thư mục `scripts/` của repo |
| Số traces hợp lệ | 0 child observation (chỉ root `lab-agent-run`) | 15 trace đủ cây retrieval + generation (38 root trace tổng cộng) — [evidence](evidence/06-trace-list.png) | 23 trace đầu tạo trước khi thêm child observation |
| Số PII leak | 0 | 0 | Starter đã scrub `message_preview` qua `summarize_text` |
| Latency P95 / TTFT P95 | _(chưa đo — log baseline chưa có latency hợp lệ)_ | Bình thường: P95 ≈ 1125 ms / TTFT P95 50 ms (21 request); khi bật `rag_slow`: 2900–3699 ms | Latency tăng do retrieval, TTFT không đổi |
| Retrieval success rate | _(chưa đo)_ | 100% | Chưa có request lỗi trong cửa sổ đo |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** `CorrelationIdMiddleware` (`app/middleware.py`) gọi `clear_contextvars()` đầu mỗi request để không rò context từ request trước; lấy `x-request-id` từ header nếu client gửi, nếu không thì sinh `req-<8-hex>` từ `uuid4`. ID được `bind_contextvars` để mọi log trong request đều mang `correlation_id`, lưu vào `request.state` để truyền sang `LabAgent.run` (trace metadata), và trả lại qua header `x-request-id` cùng `x-response-time-ms`.
- **Các metadata được ghi vào structured log:** `ts`, `level`, `service`, `event`, `correlation_id`; enrichment bind trong `/chat` (`app/main.py`): `user_id_hash` (SHA-256, 12 ký tự — không log `user_id` thô), `session_id`, `feature`, `model`, `env`; event `response_sent` có thêm `latency_ms`, `ttft_ms`, `tokens_in/out`, `cost_usd`, `quality_score`, `tool_name`, `tool_success`.
- **Cách bảo đảm PII được scrub trước khi ghi:** processor `scrub_event` (`app/logging_config.py`) được đăng ký sau `format_exc_info` và trước `JsonlFileProcessor`/`JSONRenderer`, nên dữ liệu bị che trước khi serialize hoặc ghi file. Processor duyệt đệ quy mọi chuỗi trong record (kể cả `payload` lồng nhau, list và traceback), không chỉ `payload`. `app/pii.py` có pattern cho email, thẻ, CCCD, điện thoại VN, hộ chiếu và địa chỉ (theo từ khóa hành chính); pattern cụ thể chạy trước để số dài không bị che một phần.
- **Cách kiểm chứng kết quả:** `validate_logs.py` tăng từ 30/100 lên 100/100 (0 record thiếu field, 10 correlation ID, 0 PII leak — [evidence](evidence/02-log-validator.txt)); unit test trong `tests/test_pii.py` cho từng loại PII và cho text không phải PII; gửi request chứa PII giả và kiểm tra log (`evidence/05-pii-redaction.png`); header `x-request-id` được giữ nguyên khi client gửi `req-abcdef12`.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** trace được gửi bằng key của project `day13-k4-l3b-2A202602846` trong `.env` (không commit); tên project hiện trên thanh tiêu đề của [ảnh trace list](evidence/06-trace-list.png). Workload do tôi tự chạy bằng `scripts/load_test.py` ngày 2026-09-30; trace nằm trong khoảng 11:46–11:49 (giờ VN).
- **Cấu trúc root/retrieval/generation observations:** `day13-agent-request` → `lab-agent-run` (agent, root) → `retrieval` (retriever) và `llm-generation` (generation). Hai child observation được tạo bằng `start_as_current_observation` của Langfuse SDK v4 trong `app/agent.py`. `retrieval` ghi `query_preview` đã scrub, `doc_count`, `tool_success` và `level=ERROR` khi retrieval lỗi. `llm-generation` ghi model, managed prompt, `usage_details` (input/output/total), `cost_details` (input/output/total) và `completion_start_time` để Langfuse tính TTFT. Trace chỉ chứa preview đã scrub, không chứa raw prompt/answer. Ví dụ trace `ae4fb863eba8721c30760353cb48b5b2`: tổng 2.99s, `retrieval` 2.50s, `llm-generation` 0.15s (TTFT 0.05s), 142 tokens, $0.00171 — [waterfall](evidence/07-trace-waterfall.png), [metadata](evidence/08-trace-metadata.png).
- **Cách nối trace với log:** `correlation_id` từ middleware được truyền vào `LabAgent.run` và gắn qua `propagate_attributes(metadata=...)`, nên xuất hiện trong metadata của cả ba observation. Ví dụ trace `ae4fb863eba8721c30760353cb48b5b2` có `correlation_id=req-240ad977`; trong `data/logs.jsonl`, `req-240ad977` có hai dòng `request_received` và `response_sent` (`latency_ms=2993`, `cost_usd=0.00171`, `tokens_in=35`, `tokens_out=107`) khớp với latency, cost và token (35 + 107 = 142) của trace.
- **Prompt name:**
- **Version/label baseline:**
- **Version/label candidate:**
- **Trace ID của mỗi version:**
- **Cách promote và rollback `production`:**

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** dashboard Streamlit tại `dashboard/app.py` (chạy `streamlit run dashboard/app.py`), đọc trực tiếp `data/logs.jsonl`. Tên panel, đơn vị và threshold được đọc từ `config/dashboard.yaml` nên luôn khớp contract; time range mặc định 60 phút, tự refresh 30 giây, threshold vẽ bằng đường nét đứt và có nhãn Đạt/Không đạt. Sáu panel: (1) Latency P50/P95/P99 + TTFT P95, (2) Traffic request/phút, (3) Error rate + breakdown `error_type` + retrieval success, (4) Cost theo phút + tổng, (5) tổng `tokens_in`/`tokens_out`, (6) mean `quality_score`. Ảnh: `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** giữ SLO `fast_successful_requests`: 99.5% request có `response_sent` với `latency_ms <= 3000` trong 28 ngày (`config/slo.yaml`). Baseline 21 request bình thường: 383–1438 ms, P95 ≈ 1125 ms, nên 3000 ms cho khoảng 2.7x headroom, tránh báo động giả nhưng vẫn bắt được retrieval chậm (request khi bật `rag_slow` mất 2900–3699 ms). Hạn chế: một số request `rag_slow` ở 2900–2993 ms vẫn dưới ngưỡng; tôi chưa hạ ngưỡng vì mới có 21 mẫu baseline.
- **Cách tính error budget:** error budget = 100% − 99.5% = 0.5%. Với 10,000 request trong 28 ngày, tối đa 10,000 × 0.005 = 50 request được phép lỗi hoặc chậm hơn 3000 ms. Burn rate = (tỉ lệ bad trong cửa sổ ngắn) / 0.005; burn rate 1 tiêu hết budget đúng 28 ngày, burn rate 14.4 hết budget trong khoảng 2 ngày.
- **Ba alert và runbook tương ứng:** (`config/alert_rules.yaml`, runbook trong `docs/alerts.md`, Slack `#k4-l3b-alerts`)
  1. `HighLatencyP95` — warning, `p95(latency_ms) > 3000ms` trong 5 phút → [runbook](../docs/alerts.md#alert-1).
  2. `HighErrorRateOrRetrievalFailing` — critical, error rate > 2% hoặc retrieval success < 90% trong 5 phút → [runbook](../docs/alerts.md#alert-2).
  3. `CostPerRequestSpike` — warning, cost trung bình > $0.004/request (≈ 2x baseline $0.002017) hoặc chi phí ngoại suy > $2.5/ngày trong 15 phút → [runbook](../docs/alerts.md#alert-3).
  Mỗi alert dựa trên triệu chứng người dùng thấy (chậm, lỗi, vượt ngân sách) và tương ứng một loại sự cố: retrieval chậm, retrieval lỗi, token/cost tăng.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (file riêng do Lab Coach gửi, `config/challenge.json` không commit). Chạy đúng lệnh `python scripts/inject_incident.py` rồi `python scripts/load_test.py --challenge --concurrency 5`.
- **Khoảng thời gian điều tra:** 2026-10-01 00:13:40 → 00:13:55 (giờ VN; UTC 2026-09-30 17:13:40–17:13:55). Log `incident_enabled` lúc 00:13:39.99, `incident_disabled` (fix) lúc 00:15:13.45. Đối chứng: baseline 00:13:33–00:13:39 và chạy lại challenge sau fix 00:15:13–00:15:16 — [metric](evidence/12-incident-metric.txt).
- **Triệu chứng từ metrics:** chỉ latency xấu đi. `latency_ms` của 5/5 request `feature=monitoring` là 2886–2900 ms, P50 tăng từ ~390 ms lên 2888 ms (x7.4), vượt `latency_threshold_ms=2000` của challenge. Các tín hiệu khác không đổi: TTFT P95 = 50 ms, error rate 0%, retrieval success 100%, cost ~$0.0022/request, `tokens_out` ~140, quality 0.84. Latency tăng mà TTFT không đổi nghĩa là phần chậm nằm trước bước LLM, và hệ thống chậm chứ không lỗi. Phía client còn tệ hơn: 8.7–14.5 s vì 5 request đồng thời phải xếp hàng. Alert `HighLatencyP95` (> 3000 ms) **không** kích hoạt vì P95 = 2900 ms nằm ngay dưới ngưỡng.
- **Log line và correlation ID liên quan:** lọc `event=response_sent`, `feature=monitoring`, `latency_ms > 2000` trong cửa sổ trên thì được 5 request (`req-cf45e3d5`, `req-bbe99f0a`, `req-f77dd35d`, `req-63f8c938`, `req-7b9cd4df`). Tôi chọn request chậm nhất: `{"event": "response_sent", "correlation_id": "req-cf45e3d5", "feature": "monitoring", "latency_ms": 2900, "ttft_ms": 50, "tokens_in": 35, "tokens_out": 128, "cost_usd": 0.002025, "tool_name": "retrieval", "tool_success": true, "ts": "2026-09-30T17:13:43.256276Z"}` — [log](evidence/13-incident-log.txt).
- **Trace ID và span gây ảnh hưởng:** trace `69a323929dfb82873da6fbf71e4d1027` (metadata `correlation_id=req-cf45e3d5`): `lab-agent-run` 2901 ms → **`retrieval` 2501 ms (86%)**, `llm-generation` 152 ms (TTFT 50 ms, 163 tokens, $0.002025); không observation nào `level=ERROR`. Cả 5 trace incident đều có `retrieval` ≈ 2501 ms, trong khi baseline và sau fix chỉ 0–2 ms. `llm-generation`, TTFT và token giữ nguyên ở mọi pha — [trace](evidence/14-incident-trace.txt).
- **Root cause:** bước retrieval (RAG/vector store) bị chậm thêm cố định khoảng 2.5 s cho mỗi request trong khi incident `rag_slow` bật (`app/mock_rag.py`: `time.sleep(2.5)` khi `STATE["rag_slow"]`). Không phải do LLM, prompt hay token, vì generation/TTFT/cost không đổi và prompt vẫn là `local-v1`. Mức ảnh hưởng tới người dùng bị khuếch đại vì `LabAgent.run()` là hàm đồng bộ, chạy trong handler `async def chat`, nên mỗi lần retrieval chặn event loop 2.5 s. 5 request đồng thời vì thế bị xử lý tuần tự: `latency_ms` phía server chỉ ~2.9 s nhưng client phải chờ tới 14.5 s.
- **Fix action:** khôi phục retrieval bằng cách tắt cấu hình gây chậm (`python scripts/inject_incident.py --disable`, lúc 00:15:13). Kiểm chứng bằng cách chạy lại đúng 5 query challenge: `retrieval` về 0–2 ms, `latency_ms` 382–396 ms (riêng request đầu 925 ms do fetch lại prompt khi cache hết TTL), ví dụ `req-07b38321` / trace `082b72f67bd9e700e7e4723f1f091365`. Ngoài lab, bước tương ứng là rollback thay đổi của vector store/index, hoặc chuyển sang replica/cache khỏe.
- **Preventive measure:**
  1. **Sửa lỗ hổng alert:** hạ `HighLatencyP95` xuống `p95(latency_ms) > 2000ms` trong 5 phút (≈ 5x baseline P50, khớp ngưỡng challenge). Thêm alert theo triệu chứng tăng tương đối, `p50(latency_ms) > 3 × baseline` trong 5 phút, để bắt được sự cố "chậm vừa phải" như lần này (2.9 s).
  2. **Đo retrieval riêng:** ghi `retrieval_ms` vào log `response_sent` và thêm panel/alert `p95(retrieval_ms) > 500ms`, để dashboard chỉ ra ngay bước chậm mà không cần mở trace.
  3. **Guardrail cho retrieval:** đặt timeout (ví dụ 800 ms) quanh `retrieve()`. Khi quá hạn thì trả fallback context và ghi `tool_success=false`, nên alert retrieval success sẽ kích hoạt thay vì người dùng phải chờ.
  4. **Không chặn event loop:** đổi `chat` sang `def` (FastAPI chạy trong threadpool) hoặc gọi `run_in_threadpool(agent.run, ...)`. Thêm load test với concurrency 5 và so sánh latency client với `latency_ms` server, để phát hiện hàng đợi ẩn.
  5. **Runbook:** bổ sung vào `docs/alerts.md#alert-1` quy tắc "latency tăng + TTFT không đổi thì mở span `retrieval` trước", kèm lệnh lọc log theo `feature` và `latency_ms`.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:**
- **Một lỗi/blocker đã gặp:**
- **Cách tìm nguyên nhân và xử lý:**
- **Cách hiểu luồng Metrics → Logs → Traces:**
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:**
- **Điều quan trọng nhất đã học:**
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** _(cập nhật ở CP4)_ Hiện chưa hoàn thành: prompt v1/v2 và rollback (trace hiện dùng `prompt_source=local-fallback` vì chưa tạo prompt `day13-chat` trên Langfuse). Evidence incident (12–14) ở dạng text trích trực tiếp từ `data/logs.jsonl` và Langfuse API (`/api/public/v2/observations`), không có ảnh chụp. `tests/test_validate_logs.py` không chạy được trong môi trường conda `base` vì package `scripts` trong site-packages che thư mục `scripts/` của repo.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [ ] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [ ] Incident evidence nối đúng metric → log → trace.
- [ ] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ key/secret.
- [ ] Repository chạy lại được theo README.
- [ ] Không có secret, API key, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
