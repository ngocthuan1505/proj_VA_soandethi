# Bắt đầu làm việc nhóm

**Hai chat nghiên cứu và thực hành:** đọc [điểm bắt đầu và bản bàn giao chung](../context/README.md); cập nhật phần mình làm để bên kia kế thừa quyết định và bằng chứng mà không phải lục lại toàn bộ chat.

**Ràng buộc môn học: Python là ngôn ngữ chính. Đọc [kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md) và [backend/README](../../backend/README.md). Node backend hiện có chỉ là legacy reference, không phải kiến trúc đích.**

Repo Private này là nguồn chung duy nhất. Tiếp tục từ MVP đang có; không tạo tám bản ứng dụng độc lập và không đổi framework chỉ để chia việc.

**Trước khi nhận task:** đọc [bảng chức năng demo sẵn có theo vai trò](../product/DEMO_DA_CO.md), [cách bật app và đi một vòng test](CHAY_VA_TEST_DEMO.md), [baseline đã thực chạy](../testing/BASELINE_2026_11_05.md). Dùng lại source/fixture; ghi rõ phần kế thừa, phần mới và phần chưa test. Không tính demo Node là task Python đã xong.

**Vào nhóm từ đây:** [Nhật ký chung #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32) · [Báo tiến độ / vướng mắc / nghiệm thu](BAO_CAO.md) · [Tài liệu môn và 6 hồ sơ CT](../course/README.md) · [Khung báo cáo đồ án](../reports/BAO_CAO_DO_AN.md). Chưa có username bảy thành viên, lịch nộp của lớp và bằng chứng người dùng; các phần này được ghi rõ cần bổ sung.

Mở [bảng tiến độ kéo thả](https://github.com/users/ngocthuan1505/projects/1/views/1) hoặc [bảng danh sách](https://github.com/users/ngocthuan1505/projects/1/views/2). Đọc [hướng dẫn nhận việc, cập nhật và thông báo](BOARD.md); mỗi thẻ dẫn tới issue có chi tiết nghiệm thu.

1. Đọc [phạm vi sản phẩm](../product/MVP.md), [phân công 8 người](ROLES.md), [backlog](BACKLOG.md) và [đối chiếu slide môn](../course/README.md).
2. Backend chính: Python 3.12+ và uv, vào backend chạy `uv sync --frozen` và pytest. Demo UI legacy: dùng Node.js 24, chạy `npm ci`, `npm test`, `npm start` và mở `http://127.0.0.1:4173`.
3. Chọn issue theo nhãn `role:UI-1`…`role:BE-5`. Chưa có username nên nhãn là phân công vai trò, chưa phải GitHub assignee. BE-1 là Thuận (`@ngocthuan1505`).
4. Nhận issue trong comment, gán chính mình khi được cấp quyền; tạo nhánh `feat/UI-1-001-ten-ngan` hoặc `fix/BE-2-001-ten-ngan`.
5. PR nhỏ, liên kết `Closes #...`, nêu cách kiểm tra, ảnh UI nếu có, ảnh hưởng dữ liệu/API và cách quay lui. Đợi một người khác review trước khi merge.

24 task kỹ thuật là gói việc theo ba giai đoạn, mỗi task có input, bước làm, output, pattern và reviewer. Sáu task CT riêng bổ sung Problem Brief/WBS/model/PoC/thuật toán/đánh giá; không thay 24 task và không tính các issue báo cáo là công việc đã hoàn thành. Danh sách link thật ở [github-issues.json của hồ sơ môn](../course/github-issues.json).

**Không làm lại hồ sơ đã có:** nhóm đã chuẩn bị proposal/baseline, Decomposition–Pattern 23 trang và Abstraction (UML/Schema/ADT/Interface) ở chat còn lại. Đọc [bản đối chiếu bằng chứng và việc còn thiếu](../course/HO_SO_DA_CO.md) trước khi nhận CT-01/02/03 hoặc thiết kế DTO. Vai trò mới chỉ điều phối phần tiếp theo, không gán công lao tài liệu cũ cho người chưa xác nhận.

## Quy tắc phối hợp

- `main` luôn chạy được. Dùng nhánh theo task, không tạo nhánh vĩnh viễn cho từng người; cập nhật từ main mỗi ngày và trước PR.
- Trạng thái chính xem ở trường Status trên bảng: Sẵn sàng → Đang làm → Chờ duyệt → Hoàn thành; dùng Bị chặn khi cần chờ phụ thuộc, ghi rõ việc và người cần hỗ trợ. Mỗi người tối đa một việc đang làm. Nhãn issue `status:ready/doing/review/blocked` không tự đồng bộ với bảng; cập nhật thủ công nếu dùng bộ lọc nhãn, mỗi issue chỉ giữ một nhãn status. Đóng issue khi PR merge và nghiệm thu.
- Commit, tiêu đề/mô tả PR, task và hướng dẫn dùng tiếng Việt; giữ tên kỹ thuật, định danh và lệnh bằng tiếng Anh khi cần. Không đổi lịch sử commit đã đẩy chỉ để dịch tên.
- File dùng chung `app.js`, `mvp-server.mjs`, `workbench-server.mjs`, `core.js`, `package*.json`: hẹn người giữ file trong issue trước khi sửa. API mới cần hợp đồng/fixture thống nhất với UI trước.
- [Phạm vi module](../architecture/CURRENT_STATE.md) là ranh giới trách nhiệm, chưa di chuyển toàn bộ source. Chỉ tách module khi task có nhu cầu và giữ test/caller tương ứng.
- Chỉ Thuận đăng nhập/thao tác GreenNode. Thành viên khác dùng dữ liệu mẫu, fixture và mock/local AI; chuyển thay đổi worker/triển khai bằng PR để Thuận review và tự chạy.
- Không chia sẻ tài khoản GitHub hoặc server. Không thêm server URL thật, khóa, `.data`, `.runtime`, kết quả OCR chứa dữ liệu thật vào issue/PR/log.

## Review và hoàn thành

PR phải đạt CI, có kiểm tra phù hợp thay đổi, không làm mất dữ liệu cũ, có trạng thái lỗi/tải/rỗng và không tự gọi AI trả phí. Tác vụ liên quan auth hoặc thay đổi schema cần BE-2/BE-3 review; GreenNode cần Thuận review. Không đánh dấu task xong chỉ vì giao diện hiển thị được.

Chưa bật bắt buộc branch protection hoặc trả phí GitHub: quy tắc review hiện là quy ước nhóm, CODEOWNERS hỗ trợ yêu cầu review nhưng không tự cưỡng chế. Không bật auto-deploy tới GreenNode.

## Khi có username

Thuận thêm người tại Settings → Collaborators, chờ họ nhận lời mời, rồi cập nhật `roster.json`. Cấp thêm quyền Write trong phần Manage access của Project riêng tư để họ cập nhật bảng; quyền repo và Project là hai phần riêng. Chạy công cụ đồng bộ để gán các issue còn trống theo vai trò; không ghi đè assignee người khác đã chọn. Không tự gửi lời mời khi chưa biết đúng tài khoản.

Thuận có thể xem kế hoạch trước bằng `node scripts/bootstrap-github.mjs` (dry-run). Chỉ khi muốn cập nhật GitHub, chạy `node scripts/bootstrap-github.mjs --apply` bằng tài khoản có quyền admin đã đăng nhập Git; script không lưu/in token. Sau đó commit `github-issues.json`, `github-setup.json` và `BACKLOG.md` nếu thay đổi. Chạy lại không tạo task trùng hoặc đặt lại nhãn trạng thái; nội dung người khác sửa được giữ nguyên. Nút đồng bộ không tự gửi lời mời.

CI chạy Python chính và Node legacy/UI trên Ubuntu, mỗi job giới hạn 15 phút, dùng fixture, không có secret/server. Theo dõi phút Actions gói miễn phí; không mua thêm phút hoặc dịch vụ. Không có lịch cron hoặc runner GreenNode.
