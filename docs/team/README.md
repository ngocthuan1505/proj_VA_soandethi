# Bắt đầu làm việc nhóm

**Ràng buộc môn học: Python là ngôn ngữ chính. Đọc [kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md) và [backend/README](../../backend/README.md). Node backend hiện có chỉ là legacy reference, không phải kiến trúc đích.**

Repo Private này là nguồn chung duy nhất. Tiếp tục từ MVP đang có; không tạo tám bản ứng dụng độc lập và không đổi framework chỉ để chia việc.

1. Đọc [phạm vi sản phẩm](../product/MVP.md), [phân công 8 người](ROLES.md), [backlog](BACKLOG.md).
2. Backend chính: Python 3.12+ và uv, vào backend chạy `uv sync --frozen` và pytest. Demo UI legacy: dùng Node.js 24, chạy `npm ci`, `npm test`, `npm start` và mở `http://127.0.0.1:4173`.
3. Chọn issue theo nhãn `role:UI-1`…`role:BE-5`. Chưa có username nên nhãn là phân công vai trò, chưa phải GitHub assignee. BE-1 là Thuận (`@ngocthuan1505`).
4. Nhận issue trong comment, gán chính mình khi được cấp quyền; tạo nhánh `feat/UI-1-001-ten-ngan` hoặc `fix/BE-2-001-ten-ngan`.
5. PR nhỏ, liên kết `Closes #...`, nêu cách kiểm tra, ảnh UI nếu có, ảnh hưởng dữ liệu/API và cách quay lui. Đợi một người khác review trước khi merge.

## Quy tắc phối hợp

- `main` luôn chạy được. Dùng nhánh theo task, không tạo nhánh vĩnh viễn cho từng người; cập nhật từ main mỗi ngày và trước PR.
- Luồng issue: `status:ready` → `status:doing` → `status:review` → đóng issue khi PR merge và nghiệm thu. `status:blocked` phải ghi phụ thuộc và người cần hỗ trợ. Mỗi issue chỉ có một nhãn status, mỗi người tối đa một việc đang làm.
- File dùng chung `app.js`, `mvp-server.mjs`, `workbench-server.mjs`, `core.js`, `package*.json`: hẹn người giữ file trong issue trước khi sửa. API mới cần hợp đồng/fixture thống nhất với UI trước.
- [Phạm vi module](../architecture/CURRENT_STATE.md) là ranh giới trách nhiệm, chưa di chuyển toàn bộ source. Chỉ tách module khi task có nhu cầu và giữ test/caller tương ứng.
- Chỉ Thuận đăng nhập/thao tác GreenNode. Thành viên khác dùng dữ liệu mẫu, fixture và mock/local AI; chuyển thay đổi worker/triển khai bằng PR để Thuận review và tự chạy.
- Không chia sẻ tài khoản GitHub hoặc server. Không thêm server URL thật, khóa, `.data`, `.runtime`, kết quả OCR chứa dữ liệu thật vào issue/PR/log.

## Review và hoàn thành

PR phải đạt CI, có kiểm tra phù hợp thay đổi, không làm mất dữ liệu cũ, có trạng thái lỗi/tải/rỗng và không tự gọi AI trả phí. Tác vụ liên quan auth hoặc thay đổi schema cần BE-2/BE-3 review; GreenNode cần Thuận review. Không đánh dấu task xong chỉ vì giao diện hiển thị được.

Chưa bật bắt buộc branch protection hoặc trả phí GitHub: quy tắc review hiện là quy ước nhóm, CODEOWNERS hỗ trợ yêu cầu review nhưng không tự cưỡng chế. Không bật auto-deploy tới GreenNode.

## Khi có username

Thuận thêm người tại Settings → Collaborators, chờ họ nhận lời mời, rồi cập nhật `roster.json`. Chạy công cụ đồng bộ để gán các issue còn trống theo vai trò; không ghi đè assignee người khác đã chọn. Không tự gửi lời mời khi chưa biết đúng tài khoản.

Thuận có thể xem kế hoạch trước bằng `node scripts/bootstrap-github.mjs` (dry-run). Chỉ khi muốn cập nhật GitHub, chạy `node scripts/bootstrap-github.mjs --apply` bằng tài khoản có quyền admin đã đăng nhập Git; script không lưu/in token. Sau đó commit `github-issues.json`, `github-setup.json` và `BACKLOG.md` nếu thay đổi. Chạy lại không tạo task trùng hoặc đặt lại nhãn trạng thái; nội dung người khác sửa được giữ nguyên. Nút đồng bộ không tự gửi lời mời.

CI chạy Python chính và Node legacy/UI trên Ubuntu, mỗi job giới hạn 15 phút, dùng fixture, không có secret/server. Theo dõi phút Actions gói miễn phí; không mua thêm phút hoặc dịch vụ. Không có lịch cron hoặc runner GreenNode.
