# Demo đã có: kế thừa gì, còn phải làm gì?

Kiểm kê ngày 05/11/2026 trên source `71868ebab35813fdc3a16cea737fb5aa2f33e4e9`. Đây là **MVP kế thừa**, không phải 24 task Python đã hoàn thành và không gán lại tác giả cũ cho người nhận task mới.

**Bắt đầu:** [cài và dùng demo](../team/CHAY_VA_TEST_DEMO.md) → [kết quả test và giới hạn](../testing/BASELINE_2026_11_05.md) → [nhận việc/báo cáo](../team/BAO_CAO.md).

## Chức năng và bằng chứng

Test ghi trong bảng là nơi kiểm hành vi; kết quả lượt chạy hiện tại xem báo cáo baseline. Test AI dùng fixture loopback, không chứng minh Gemini/Claude/GPT/Ollama/GreenNode thật đang hoạt động. Các chức năng nghiệp vụ dưới đây hiện nằm ở JS/Node, trừ nền Python ghi riêng.

| Mã | Phần demo đã có để dùng lại | Source chính | Test liên quan | Còn cần xác nhận/cải thiện |
|---|---|---|---|---|
| D01 | Tạo đề trống/mẫu, đổi môn, kho đề, cấu trúc câu, Đề/Đáp án, lưu | [app.js](../../app.js), [design.js](../../design.js), [core.js](../../core.js) | [workbench UI](../../tests/workbench-browser.mjs), [core](../../tests/core.test.mjs) | Luồng người dùng thật, trạng thái lỗi/rỗng; chuyển API kho đề sang Python |
| D02 | Editor rich text, định dạng, bảng, ảnh, công thức, A4, undo/redo | [editor-engine.js](../../editor-engine.js), [editor.js](../../editor.js), [rich-document.js](../../rich-document.js) | [studio UI](../../tests/studio-browser.mjs), [studio](../../tests/studio.test.mjs) | Văn bản rất dài, bảng qua trang, IME và đối chiếu in trên Word |
| D03 | Thư viện 485 mục/19 nhóm môn, lớp gợi ý 1–12, lọc/tìm không dấu; nhập trực quan/MathLive | [composer.js](../../composer.js), [authoring-catalog.js](../../authoring-catalog.js), [curriculum-catalog.js](../../curriculum-catalog.js) | [curriculum](../../tests/curriculum.test.mjs), [curriculum UI](../../tests/curriculum-browser.mjs), [authoring UI](../../tests/authoring-browser.mjs) | Rà chuyên môn/điều kiện/nguồn; không tuyên bố bao trọn mọi chương trình |
| D04 | Mẫu Lý/Hóa/Sinh/Văn/Anh và môn khác; ngữ liệu giữ dòng/nguồn nhập tay; Punnett, ma trận, hệ phương trình | [composer.js](../../composer.js), [authoring-catalog.js](../../authoring-catalog.js) | [authoring](../../tests/authoring.test.mjs), [authoring UI](../../tests/authoring-browser.mjs) | Mẫu soạn không phải bộ giải tổng quát; Hóa chỉ kiểm bảo toàn nguyên tố trong phạm vi hỗ trợ |
| D05 | Hình học có ràng buộc, kéo điểm và hình trong bản xuất | [geometry.js](../../geometry.js) | [studio](../../tests/studio.test.mjs), [studio UI](../../tests/studio-browser.mjs) | Rà tính đúng hình với giáo viên; thêm fixture hình khó trước khi mở rộng |
| D06 | Sinh đề: làm rõ một lượt, xác nhận cấu trúc/điểm, sinh từng bài bằng job/SSE, hủy và khôi phục | [workbench.js](../../workbench.js), [workbench-server.mjs](../../workbench-server.mjs), [blocks.js](../../blocks.js) | [workbench](../../tests/workbench.test.mjs), [workbench UI](../../tests/workbench-browser.mjs) | Chạy model thật, tải đồng thời, timeout/retry; triển khai job/core trong Python |
| D07 | Bôi đen đúng đề/lời giải/barem; UUID block, version, preview/diff, xác nhận áp dụng, undo cả lần sửa | [editor.js](../../editor.js), [blocks.js](../../blocks.js), [workbench.js](../../workbench.js) | [selection](../../tests/selection.test.mjs), [selection UI](../../tests/selection-browser.mjs) | Không chọn xuyên hai editor; vùng cắt ngang cấu trúc bảng bị chặn; cần E2E cùng Python |
| D08 | Chat phân biệt hỏi/sửa/kiểm, ngữ cảnh đề hiện tại và hội thoại gần; bỏ chip bỏ ngữ cảnh thật | [workbench.js](../../workbench.js), [workbench-server.mjs](../../workbench-server.mjs) | [selection UI](../../tests/selection-browser.mjs), [workbench](../../tests/workbench.test.mjs) | Đánh giá yêu cầu tiếng Việt mơ hồ; câu trả lời AI không tự là nội dung đề đã lưu |
| D09 | Kiểm/giải độc lập đáp án; rà phần bị ảnh hưởng; tự cập nhật đáp án có lựa chọn; ma trận đếm từ đề | [core.js](../../core.js), [ai.mjs](../../ai.mjs), [workbench-server.mjs](../../workbench-server.mjs) | [core](../../tests/core.test.mjs), [workbench](../../tests/workbench.test.mjs) | Bộ kiểm cục bộ hỗ trợ một số dạng; chất lượng suy luận AI đa môn cần benchmark, giáo viên duyệt |
| D10 | Nhập DOCX/PDF/PPTX/text/ảnh, giữ trang nguồn; OCR Việt/Anh và phần không chắc | [importers.mjs](../../importers.mjs), [word-import.mjs](../../word-import.mjs) | [backend MVP](../../tests/mvp-backend.test.mjs), [studio](../../tests/studio.test.mjs), [studio UI](../../tests/studio-browser.mjs) | Fixture OCR đơn giản; ảnh xấu/công thức viết tay, chart/shape DOCX cần test riêng; port document service |
| D11 | Xuất Word OMML, PDF, HTML; bản học sinh tách đáp án/ghi chú; lưu bản xuất | [exports.mjs](../../exports.mjs), [math-word.mjs](../../math-word.mjs) | [backend MVP](../../tests/mvp-backend.test.mjs), [studio](../../tests/studio.test.mjs), [curriculum UI](../../tests/curriculum-browser.mjs) | Word XML/PDF trích xuất không thay kiểm trực quan bằng Microsoft Word và in thật |
| D12 | SQLite, revision conflict, lưu/mở lại và bản lưu offline; kho riêng theo tài khoản | [backend-store.mjs](../../backend-store.mjs), [storage.js](../../storage.js), [accounts.mjs](../../accounts.mjs) | [deployment](../../tests/deployment.test.mjs), [backend MVP](../../tests/mvp-backend.test.mjs), [workbench UI](../../tests/workbench-browser.mjs) | Port repository/migration Python, diễn tập restore; không dùng DB cá nhân làm fixture |
| D13 | Đăng ký/đăng nhập/đăng xuất, session/ownership chế độ online; chia sẻ snapshot và thu hồi | [accounts.mjs](../../accounts.mjs), [deployment.mjs](../../deployment.mjs), [mvp-server.mjs](../../mvp-server.mjs) | [deployment](../../tests/deployment.test.mjs), [online UI](../../tests/online-browser.mjs) | TLS proxy fixture không phải nghiệm thu hosting; chưa có email/reset mật khẩu hoặc đồng biên tập |
| D14 | Cấu hình riêng Sinh/Sửa/Kiểm; Gemini/Claude/GPT, Ollama/API tương thích, GreenNode; che key, lỗi rõ, không fallback trả phí ngầm | [ai-providers.js](../../ai-providers.js), [cloud-ai.mjs](../../cloud-ai.mjs), [greennode.mjs](../../greennode.mjs), [connections.js](../../connections.js) | [cloud AI](../../tests/cloud-ai.test.mjs), [GreenNode](../../tests/greennode.test.mjs) | Chỉ test protocol fixture; cần owner cấp kết nối hợp lệ rồi mới thử model thật; không dùng key cũ trong chat |
| D15 | Chat gọn, cuộn giữ vị trí, mở rộng, mobile, phím gửi/IME; thư viện không che hội thoại | [assets/usability.js](../../assets/usability.js), [assets/usability.css](../../assets/usability.css), [design.css](../../design.css) | [usability UI](../../tests/usability-browser.mjs) | Chưa đánh giá giáo viên thật, screen reader hoặc chứng nhận WCAG |
| D16 | Nền FastAPI `/api/health`, `/api/readiness`, `/docs`; readiness chủ động 503 | [Python main](../../backend/src/mach_backend/main.py) | [foundation pytest](../../backend/tests/test_foundation.py) | **Chưa có nghiệp vụ Python đầy đủ.** 503 ở readiness hiện là đúng thiết kế, không phải demo Node bị tắt |

Tra hướng dẫn thao tác chi tiết trong [USER_GUIDE](../../USER_GUIDE.md). Tìm nguồn/web, bộ chạy model, Docker/ngrok và các công cụ triển khai có source tham khảo nhưng không được suy ra đã chạy live hoặc có SLA 24/7 từ lượt test này. Không có thanh toán thật; điểm trong demo không phải hóa đơn dịch vụ.

## Định hướng từng mảng để tự chọn

Bảng dưới là menu công việc, không gán sẵn username. [Cách nghiên cứu/đăng ký cá nhân hoặc làm chung](../team/CHON_VIEC.md); nhóm tự chọn người/consumer/reviewer.

Đầu ra `001` là baseline/thiết kế, `002` là triển khai/tích hợp, `003` là nghiệm thu. Tính năng Node đã có là đầu vào để đọc, chạy fixture và port; không tự tick task Python chỉ vì demo kế thừa chạy được. Không giao người mới viết lại toàn bộ tính năng.

| Vai trò | Dùng lại trước | Việc cần làm tiếp và bằng chứng cần nộp |
|---|---|---|
| UI-1 | D01/D12/D13/D15 | Ghi sơ đồ tạo→lưu→mở→xuất, trạng thái rỗng/lỗi và Tab/mobile; nối contracts FastAPI; ảnh + fixture tách kho hai tài khoản |
| UI-2 | D02/D03/D04/D05/D07/D11 | Lập baseline công thức/bảng/hình/undo/reload; giữ richDoc khi chuyển API; so sánh Word/PDF và các mẫu đa môn |
| UI-3 | D06/D07/D08/D09/D15 | Dùng mock hiện có cho preview/hủy/retry; kiểm quá vùng, stale version và trả lời muộn; cuối cùng E2E tới job Python |
| BE-1 (Thuận) | D06/D09/D14 | Đọc adapter/prompt/validator cũ, port orchestration/validation Python; log fixture trước, model thật sau khi Thuận cấu hình; chỉ Thuận vận hành GreenNode |
| BE-2 | D07/D12/D13/D16 | Chốt OpenAPI/auth/ownership/error contracts từ route cũ; implement FastAPI và pytest âm; không proxy nghiệp vụ về Node |
| BE-3 | D01/D07/D12 | Chốt ERD/ADT/repository; giữ UUID, richDoc, revision và thứ tự câu; migration/restore trên DB fixture, có rollback |
| BE-4 | D03/D04/D10/D11 | Dùng bộ tài liệu sinh trong test; mở rộng file hỏng/ảnh xấu/công thức/Word; port import/export Python và đối chiếu file thực |
| BE-5 | D06/D12/D13/D16 và bộ test | Giữ Node baseline; tích hợp job/SSE/cancel Python, CI và báo cáo regression; phân biệt test fixture, thủ công và model thật |

Task và reviewer cụ thể giữ trong [backlog](../team/BACKLOG.md). Khi báo xong một bước, dẫn mã Dxx, commit và test mới; mô tả rõ phần kế thừa/phần tự làm. Chưa đủ tiêu chí thì báo tiến độ hoặc vướng mắc, không đóng task.
