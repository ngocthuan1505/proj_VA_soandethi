# Checklist merge và bàn giao bản thử

## Từng PR

- [ ] Liên kết issue, đúng scope, không chứa URL/token server hoặc dữ liệu giáo viên.
- [ ] Kiểm caller/test/config/assets/export bị ảnh hưởng; không ghi đè việc nhóm khác.
- [ ] `npm test` và test mục tiêu đạt; UI có ảnh fixture/viewport và keyboard khi cần.
- [ ] Có lỗi/loading/empty; sửa đề không mất dữ liệu/nguồn/định dạng ngoài vùng.
- [ ] Thay API/schema có compatibility/migration/rollback được review.
- [ ] Một người khác review; Thuận review mọi thay đổi GreenNode trước merge.

## Candidate do BE-5 tổng hợp

- [ ] Core/backend chạy Python/FastAPI, không proxy nghiệp vụ về Node; bản demo chính không cần Node API.
- [ ] Pytest, Ruff và ty đạt; uv lock khớp và UI E2E gọi Python.

- [ ] Ghi đúng commit SHA, hướng dẫn clone sạch và cài `npm ci`.
- [ ] Hai user/guest/admin, ownership đề/file/export/share, session/logout đã kiểm tra.
- [ ] Tạo → sửa → undo → reload → xuất giáo viên/học sinh chạy được trên fixture.
- [ ] Job cancel/disconnect/stale/duplicate/timeouts không ghi kết quả muộn.
- [ ] Editor/công thức/bảng/đa môn ở mobile/desktop, bản in được đối chiếu.
- [ ] BE-3 đã restore DB bản sao và mô tả migration/rollback.
- [ ] Bug còn mở và giới hạn tải/AI/OCR có bằng chứng, không tuyên bố production-ready khi còn blocker.

## Chỉ Thuận thao tác GreenNode

- [ ] Review [runbook](../../ops/greennode/README.md); chỉ trong `/network-volume/ProJ_VA`.
- [ ] Kiểm xác thực Jupyter/network trước thử; repo Private không thay thế xác thực server.
- [ ] Sao lưu và xác minh restore; giữ bản phát hành cũ, config/keys riêng.
- [ ] Tải source đúng commit, kiểm release local/fixture trước; không chồng `.data`/`.runtime`.
- [ ] Smoke model thật trên dữ liệu mẫu được phép, đúng model/task/timeout và hủy.
- [ ] Thuận quyết định mở web; kiểm HTTPS, login/ownership, exports và đóng lại được.
- [ ] Nếu lỗi, dừng candidate, quay lại release trước; không xóa volume/DB để chữa nhanh.

Không tự chạy checklist này từ CI; không tự mở endpoint, không tự thuê/nâng cấp dịch vụ. Quyết định phát hành không đồng nghĩa với có cam kết uptime hoặc đã đánh giá mọi môn học.
