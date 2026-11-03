# Script dựng môi trường của bản thử cũ

Năm script này được lấy từ bản local lưu trong quá trình triển khai tháng 10/2026, không phải vừa tải từ GreenNode. Giữ lại để không mất các bước cài đặt từng dùng, đặc biệt thư viện Chromium/font nằm riêng trong thư mục dự án.

| File | Vai trò lịch sử |
|---|---|
| `prepare-greennode-node.py` | Tải Node Linux x64, kiểm checksum chính thức, giải nén runtime riêng |
| `prepare-greennode-app.py` | Kiểm gói source theo checksum cũ, npm ci, tạo cấu hình riêng và chạy bản thử nội bộ |
| `prepare-greennode-browser.py` | Tải Chromium và thư viện/font riêng; kiểm PDF/Word/OCR rồi khởi động lại app của dự án |
| `prepare-greennode-ngrok.py` | Tải agent ngrok, kiểm version; chưa tự tạo tunnel |
| `prepare-greennode-supervisor.py` | Chuyển cấu hình/dữ liệu sang thư mục ẩn, cấu hình và thử supervisor |

**Đây là code lưu trữ, không chạy ngay hoặc chạy nguyên xi trên server mới.** Một số script tạo tiến trình nền, di chuyển dữ liệu hoặc dừng/khởi động lại app. Chúng giả định đúng bộ cài, PID, trạng thái bước trước, Linux x64 và đường dẫn của bản thử cũ. Tệp app còn tham chiếu SHA-256 gói source cũ; gói lấy từ GitHub hiện tại có checksum khác. Không bỏ kiểm checksum chỉ để chạy tiếp.

Địa chỉ notebook riêng trong script app đã thay bằng `https://YOUR-NOTEBOOK.example.test`. Không có khóa/token/database thật trong thư mục này. Manifest nguồn gốc và checksum nằm tại [recovery-status.json](../recovery-status.json). Không nhập secret vào source để hoàn thiện các script này.

Trước khi dùng lại, Thuận cần đọc và điều chỉnh trên bản sao theo [hướng dẫn khôi phục](../KHOI_PHUC.md), kiểm đường dẫn/phụ thuộc và thử bằng dữ liệu mẫu. Đợt bảo toàn hiện tại chỉ kiểm cú pháp Python của cả wrapper và script lồng bên trong, **không chạy cài đặt, tải model, sửa server hoặc mở web**.
