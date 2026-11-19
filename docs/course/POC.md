# PoC — sinh bộ câu theo ma trận và kiểm kết quả

**Cập nhật 19/11/2026 trên nhánh `codex/ban-thu-13` (`47c40f8` & `8d37a0f`):**
- **`[Fixture / Mock]` & `[Hiện có / Đã chạy bằng Python]`:** Tại `8d37a0f`, toàn bộ `uv run pytest -q` đạt **`710 passed, 5 skipped, 1 warning, 3 subtests passed`** (`110.66s`), lượt tắt Node/npm khỏi `PATH` đạt **`167 passed`** (`51.99s`), hồi quy `npm test` đạt **`139 passed`**, `npm run check:team` đạt **`14 passed`**, và `IT-01`..`IT-11` chạy qua hai lượt `10/11` + rerun ca đơn (`--case 11`, `--case 05`) đều đạt trên phản hồi mẫu. Chi tiết tại [Đối chiếu Python](../testing/DOI_CHIEU_PYTHON.md) và [Kiểm thử tích hợp](../testing/KIEM_THU_TICH_HOP.md).
- **Đối chiếu model thật `qwen3:4b` Vulkan cục bộ (tách riêng hoàn toàn khỏi fixture, mẫu Toán lớp 5 gồm 5 câu, 4 dạng, 10 điểm, nguồn tự viết, ngưỡng `900s`, tắt chế độ suy nghĩ):**
  - **Lượt v1 (`outputs/qa-antigravity-qwen3`):** `900.707s`, `status="failed"`, `errorCode="timeout"`, `checkedAttempts=8`, `traceVerified=true`, `evidenceIssues=[]`, giữ nguyên kho (`beforeRevision == afterRevision == 2`, `0` câu lưu).
  - **Lượt v2 sau tinh chỉnh Pha 2 `47c40f8` (`outputs/qa-antigravity-qwen3-v2`):** `901.081s`, `status="failed"`, `errorCode="timeout"`, `checkedAttempts=7` (`19` lượt gọi model / `894.01s`), `traceVerified=true`, `evidenceIssues=[]`, giữ nguyên `beforeRevision == afterRevision == 2`. Toàn bộ `7/7` lượt `structure_check` đạt; **4/5 câu (`ordinal` `0, 2, 3, 4`) pass `blind_content_check` và cache ổn định (`24.0s`–`45.4s`/lượt)**; duy nhất `ordinal 1` vượt khả năng model `4B` trên câu suy diễn Thông hiểu từ nguồn 1 câu 2 số.
- **Kết luận PoC hiện tại:** cơ chế kiểm soát Python (giữ an toàn cấu trúc, phát hiện sai mức/sai đáp án, chặn ghi dở khi timeout) đã chứng minh hoạt động đúng như thiết kế (`[Hiện có / Đã chạy bằng Python]`), còn giả thuyết model `4B` cục bộ tự hoàn thành 100% bộ câu hỗn hợp trong `900s` trên câu suy diễn từ nguồn 1 câu **chưa đạt ở `ordinal 1`**. Phần thử model lớn hơn, thẩm định sư phạm độc lập, review chéo hợp đồng [AI](../contracts/ai.md) · [Job & SSE](../contracts/job-va-sse.md) · [Thiết kế trợ lý](../design/tro-ly-va-job.md) và diễn tập GreenNode vẫn `[Chờ review nhóm / Thành viên xác nhận]` (riêng GreenNode do `ngocthuan1505` tự vận hành theo [ops/greennode/README.md](../../ops/greennode/README.md)).

**Cập nhật 13/11/2026:** bản thử đã có vòng model gọi công cụ, nhận lỗi và nộp kiểm lại bằng Python, chạy qua CLI và bàn soạn local. Hai lượt đối chiếu Qwen2.5 3B/1.5B cùng đầu vào đều chưa đạt; chưa kết luận sinh đề thành công. Xem [nội dung, data model và cách chạy hiện tại](../testing/POC_AGENT_CMD.md). Test giả lập kiểm cơ chế khác với phép đo model thật. Các phần thử sửa vùng bên dưới là hồ sơ cũ, không thay phần sinh bộ câu theo ma trận.

**Cập nhật 12/11/2026 theo hai ảnh góp ý của giảng viên do Thuận cung cấp:** trọng tâm hiện tại là sinh cả bộ câu theo ma trận, có hậu xử lý và gọi lại khi lỗi, kiểm mức nhận thức thực tế. Phép sửa vùng bên dưới giữ làm thí nghiệm trước đây, không còn được dùng một mình để chứng minh phần rủi ro nhất. Bằng chứng và trạng thái lát tích hợp app thật ở [PoC ma trận](../testing/POC_MA_TRAN_APP_THAT.md). Chưa có kết luận thành công cho tới khi kiểm được model thật qua bàn soạn, xem trước/rà/xác nhận và các ca lỗi; fixture chỉ kiểm code.

## Phiếu rà độc lập cho một lượt PoC

Dùng [phiếu tự giải](poc-ra-doc-lap/1_TU_GIAI_VA_NHAN_DINH.md) trước khi mở [phiếu đối chiếu](poc-ra-doc-lap/2_DOI_CHIEU_SAU_KHI_TU_GIAI.md). Hai phiếu và [manifest](poc-ra-doc-lap/DOI_CHIEU_NGUON.json) giữ nguyên từ [PR #43 của nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/43).

Bốn câu trong phiếu trích từ phản hồi ở lượt thử thứ hai của Qwen2.5 3B. Manifest ghi tác vụ kết thúc vì hết lượt thử và đề chưa được lưu vào bàn soạn. Các ô nhận xét còn trống. Hồ sơ này hỗ trợ chấm độc lập từng câu trong CT-04 và CT-06 khi có người rà thực hiện.

## Thí nghiệm sửa vùng đã lập trước phản hồi mới

Trạng thái: **kế hoạch, chưa có kết quả thí nghiệm này**. Nguồn: Topic 4 trang 31, 36–40; Topic 6 trang 7–8, 14, 17. BE-1 điều phối, UI-3 và BE-5 hỗ trợ; mọi thao tác GreenNode do Thuận thực hiện sau khi có server.

Proposal cũ đã có kế hoạch/phạm vi PoC gồm đọc nguồn, truy xuất, sinh câu có căn cứ, kiểm và rút trích. Câu hỏi sửa vùng dưới đây là **ứng viên nhóm cần chốt**, không tự thay toàn bộ kế hoạch đã làm. Trong [hồ sơ đã đối chiếu](HO_SO_DA_CO.md) chưa thấy bộ kết quả thực nghiệm đủ để kết luận CT-04 hoàn thành; demo kỹ thuật cũ cần chọn input/output/metrics phù hợp mới dùng làm bằng chứng PoC này.

## Câu hỏi rủi ro

“Từ một đề có công thức và yêu cầu sửa đúng một câu, hệ thống có tạo đề xuất được kiểm phạm vi/revision, cho giáo viên xem trước, và bảo toàn các câu khác không?” Tách hai giả thuyết: bộ kiểm Python chặn thay đổi sai; model thật tạo đề xuất đủ chất lượng. Fixture chỉ kiểm giả thuyết đầu, không chứng minh model giải toán đúng.

## Thí nghiệm dự kiến

1. UI-2/BE-4 tạo bộ 12 đề tự viết, gồm ít nhất Toán/Lý/Hóa và Văn/Anh, có công thức/bảng ở một số mẫu. BE-1/UI-3 viết yêu cầu sửa có đích xác định, gồm cả yêu cầu mơ hồ cần hỏi lại. Đây là đề xuất bộ mẫu của nhóm, không phải số lượng thầy bắt buộc.
2. BE-3 lưu snapshot chuẩn và revision; BE-2 chốt contract. BE-5 xây các phản hồi fixture: hợp lệ, sai schema, sửa ngoài vùng, sai job, stale, duplicate và sau cancel.
3. Chạy validator Python và UI preview/undo; so sánh hash hoặc cấu trúc mọi khối ngoài vùng, lưu kết quả trên dữ liệu mẫu. Ghi commit và lệnh chạy.
4. Khi có backend/model thật, Thuận chạy cùng bộ mẫu với model/params/provenance được ghi nhận, không bật fallback trả phí. Giáo viên/người đánh giá kiểm câu trả lời và lời giải; tách tiêu chí hình thức với đúng kiến thức.
5. Tổng hợp lỗi, phương án khác và quyết định tiếp tục/chỉnh thiết kế. Thất bại cũng là bằng chứng PoC; không bỏ ca lỗi khỏi báo cáo.

## Ngưỡng đề xuất cần chốt trước chạy

- An toàn: **0** lần ghi ngoài vùng, mất công thức hoặc ghi kết quả stale/cancel; mọi phản hồi sai cấu trúc phải bị chặn. Một lỗi loại này là fail, không lấy trung bình che đi.
- Chất lượng model: nhóm và người duyệt chốt số ca cần đạt trên 12 mẫu trước khi chạy; chưa có ngưỡng được phê duyệt, không tự ghi “80% chính xác”.
- Ghi thời gian chờ, số retry và giới hạn tài nguyên thực đo; timeout cần có giá trị cụ thể trong contract, chưa suy ra từ GPU cũ.

| ID mẫu | Commit/môi trường/model hoặc fixture | Kỳ vọng | Ngoài vùng giữ nguyên? | Kiến thức đúng? ai duyệt? | Kết quả + thời gian + bằng chứng |
|---|---|---|---|---|---|
| Chưa chạy | — | — | — | — | — |

## Điều kiện xong

Có script/notebook/test chạy lại được, bộ mẫu hợp lệ, ngưỡng đã chốt, kết quả gồm cả lỗi, kết luận yes/no/chưa đủ bằng chứng và kế hoạch sửa. Có thể nộp script/ảnh/video ngắn minh chứng; màn hình login hay danh sách model không chứng minh được giả thuyết này.

Nếu chưa có model/server: hoàn thành bộ thử và báo kết quả fixture riêng, để **phần model thật đang chờ**; tìm model local phù hợp bằng quyết định của Thuận, không nhận tài khoản server của người khác.
