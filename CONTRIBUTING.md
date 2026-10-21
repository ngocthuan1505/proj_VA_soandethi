# Làm việc cùng nhóm

1. Clone repo, cài Node.js 24+ và chạy `npm ci`.
2. Tạo nhánh riêng: `git switch -c ten-ban/mo-ta-thay-doi`.
3. Sửa, chạy `npm test`, tự thử luồng bị ảnh hưởng bằng `npm start`.
4. Commit, push nhánh và tạo pull request về `main`. Ghi rõ thay đổi và cách đã kiểm tra.

Đọc [README](README.md) để chọn bộ kiểm tra giao diện phù hợp. Bộ kiểm tra Node và UI fixture không cần API key thật; không tự gọi API trả phí khi kiểm thử.

Không commit `.data`, `.runtime`, `.env`, API key, token, mật khẩu, dữ liệu giáo viên hoặc trọng số mô hình. `.gitignore` chỉ bảo vệ tệp chưa được theo dõi; luôn xem `git diff --cached` trước khi commit. Chỉ dùng dữ liệu mẫu được phép chia sẻ trong test.

Chỉnh editor ở `editor-engine.js`, sau đó chạy `npm run build-editor` và commit cả bundle `assets/editor-engine.js` cùng thông tin giấy phép đi kèm. Khi đổi phụ thuộc, cập nhật và commit `package-lock.json`.

Không thêm giấy phép mã nguồn hoặc thay đổi quyền truy cập repo thay cho chủ dự án. Giữ thông tin giấy phép của các thành phần trong `THIRD_PARTY.md`.
