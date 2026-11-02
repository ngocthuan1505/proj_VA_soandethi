# Làm việc cùng nhóm

Đọc [quy trình và phân công hiện hành](docs/team/README.md) trước khi nhận task. Mỗi issue có mã vai trò, phụ thuộc và tiêu chí nghiệm thu trong [backlog](docs/team/BACKLOG.md). Mọi thao tác thực tế trên GreenNode do **Thuận/BE-1** thực hiện; người khác chỉ gửi source/test qua PR.

1. Clone repo. Backend chính dùng Python 3.12+ + uv: trong `backend` chạy `uv sync --frozen`. Node.js 24+ / `npm ci` dùng UI/build và demo legacy.
2. Tạo nhánh riêng: `git switch -c ten-ban/mo-ta-thay-doi`.
3. Sửa Python chạy pytest/Ruff/ty trong backend; chạy `npm test`, `npm run check:team` cho UI/baseline, thử luồng bị ảnh hưởng.
4. Commit, push nhánh và tạo pull request về `main`. Ghi rõ thay đổi và cách đã kiểm tra.

Đọc [README](README.md) để chọn bộ kiểm tra giao diện phù hợp. Bộ kiểm tra Node và UI fixture không cần API key thật; không tự gọi API trả phí khi kiểm thử.

Không commit `.data`, `.runtime`, `.env`, API key, token, mật khẩu, dữ liệu giáo viên hoặc trọng số mô hình. `.gitignore` chỉ bảo vệ tệp chưa được theo dõi; luôn xem `git diff --cached` trước khi commit. Chỉ dùng dữ liệu mẫu được phép chia sẻ trong test.

Chỉnh editor ở `editor-engine.js`, sau đó chạy `npm run build-editor` và commit cả bundle `assets/editor-engine.js` cùng thông tin giấy phép đi kèm. Khi đổi phụ thuộc, cập nhật và commit `package-lock.json`.

Không thêm giấy phép mã nguồn hoặc thay đổi quyền truy cập repo thay cho chủ dự án. Giữ thông tin giấy phép của các thành phần trong `THIRD_PARTY.md`.
