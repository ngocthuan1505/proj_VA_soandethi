# Bảo toàn và khôi phục khi đổi GreenNode

## Tình trạng kiểm tra ngày 04/11/2026

Sau khi Thuận cho phép ngoại lệ **chỉ đọc để sao lưu**, trang Jupyter cũ trả HTTP 200 nhưng đường dẫn `network-volume/ProJ_VA` trả HTTP 404, báo không có thư mục. Metadata gốc Jupyter không thấy `ProJ_VA` hoặc `network-volume`. **Chưa tải được file nào từ server trong đợt này.** Không tạo kernel, sửa file, chạy cài đặt, bật/tắt dịch vụ hoặc truy cập nội dung dự án khác.

Điều này không xác nhận volume đã bị xóa. Có thể dữ liệu nằm trên volume chưa gắn hoặc không còn được notebook hiện tại hiển thị. Thuận cần kiểm tra volume cũ trong tài khoản GreenNode hoặc nhờ hỗ trợ của nhà cung cấp xác nhận khả năng gắn lại. Khi volume hiện lại, cần đối chiếu thay đổi chỉ có trên server trước khi thay bằng source từ GitHub.

## Những gì đã giữ được

| Thành phần | Nơi lưu | Bằng chứng / giới hạn |
|---|---|---|
| Source app từng triển khai | Repo hiện tại và lịch sử `main` | Đã kiểm SHA-256 gói triển khai local cũ: 167 file; 141 khớp bản hiện tại sau chuẩn hóa xuống dòng, 26 có blob trong lịch sử Git còn truy cập được |
| Worker AI, cài model, start/stop, supervisor web, nhập token | [server-kit](../../server-kit/README.md) | Cả 9 file khớp bản local đã lưu, không phải file mới tải từ server |
| Các bước dựng Node, app, Chromium/font, ngrok, supervisor | [legacy-bootstrap](legacy-bootstrap/README.md) | Bổ sung 5 script lịch sử còn nằm ngoài repo; địa chỉ notebook riêng được thay bằng địa chỉ mẫu |
| Mẫu cấu hình không chứa khóa | [runtime-config.example.json](runtime-config.example.json) | Phải điền lại đường dẫn/runtime và thông tin riêng trên server mới |
| Backend Python và kế hoạch nhóm | [backend](../../backend/README.md), [kế hoạch Python](../../docs/architecture/PYTHON_MIGRATION.md) | Mới có nền FastAPI, chưa chuyển xong nghiệp vụ |
| Kết quả đối chiếu | [recovery-status.json](recovery-status.json) | Có checksum và nguồn gốc; phân biệt file local với phần chưa lấy được từ server |

Không ghi đè source hiện tại bằng bản triển khai cũ chỉ để tái tạo giao diện. Lịch sử Git giữ các phiên bản cũ để đối chiếu/khôi phục có chọn lọc.

## Những phần chưa cứu được từ server

- `mach_web/.data`: database, tài khoản, kho đề, tệp tải lên và bản xuất của bản online.
- `mach_web/.runtime`: cấu hình đang chạy, khóa API, token ngrok, mã mời và thông tin riêng. Không đưa phần này vào Git dù repo Private.
- `soande_ai/models`: trọng số và manifest model thực tế đã tải. Có source bộ tải model trong repo, nhưng chưa có bản sao trọng số/manifest cũ để bảo đảm tải lại đúng từng byte.
- Mọi sửa đổi chỉ có trên server sau các snapshot local đã biết. Không thể xác nhận chúng khi chưa đọc lại volume.

Clone repo sẽ lấy lại **source**, không lấy lại tài khoản, đề riêng hoặc cấu hình AI cũ. Nếu không cứu được `.data`, bản online dựng lại sẽ cần dữ liệu và tài khoản mới.

## Khi lấy lại được volume cũ — Thuận thực hiện

1. Xác nhận đúng `/network-volume/ProJ_VA`; không thao tác volume/dự án khác. Trước khi thay file, tải một bản sao riêng của source, metadata cần thiết và dữ liệu dự án ra máy an toàn.
2. Dữ liệu `.data` và cấu hình `.runtime` phải nằm ngoài repo. Giữ archive riêng, hạn chế quyền truy cập; không đính kèm vào issue, PR hay GitHub Release của nhóm.
3. Nếu database còn được process sử dụng, không sao chép riêng file SQLite bằng `cp`. Dùng phương án backup nhất quán đã được chủ dự án kiểm tra, hoặc Thuận tự dừng đúng app rồi sao lưu. Ngoại lệ truy cập của đợt này chỉ là đọc, không tự dừng app.
4. Đối chiếu source server với Git; chỉ đưa các file code đã rà soát và loại khóa vào nhánh/PR. Xác minh checksum archive và thử đọc database/bản xuất trên **bản sao**, giữ nguyên bản gốc.

## Khi có server mới — chuẩn bị trước, chưa mở web

Chỉ Thuận chạy các bước này. Toàn bộ source, model, cache, dữ liệu và runtime của dự án đặt trong `/network-volume/ProJ_VA`.

1. Xác nhận volume, dung lượng, quyền ghi, Linux/GPU/CUDA và bảo vệ đăng nhập Jupyter. Không coi cấu hình H100 MIG cũ là cấu hình được bảo đảm cho server mới.
2. Đặt source vào một thư mục mới bên trong ProJ_VA. Có thể clone repo Private bằng quyền GitHub của Thuận hoặc giải nén gói source sạch đã tải trên máy. Không nhúng token GitHub vào URL/lệnh; không giải nén chồng lên `.data`/`.runtime` đang có.
3. AI cục bộ: đọc [server-kit](../../server-kit/README.md), chạy preflight trước. Chép các file AI cần thiết từ `server-kit` sang `soande_ai` theo cấu trúc cũ, rồi Thuận mới quyết định chạy `setup_ai.py`. Bộ cài có tải vài GB và biên dịch CUDA; không tự chạy trong đợt sao lưu này. Giữ manifest/checksum sau khi cài lại. Đọc lựa chọn GPU và model trước khi start worker.
4. App demo cũ còn dùng Node 24; cài dependencies bằng `npm ci` từ lockfile. Chromium, thư viện Linux và font phục vụ PDF/OCR cần kiểm lại theo image mới; 5 script lưu trữ là tài liệu kỹ thuật của bản cũ, **không phải bộ cài một lệnh cho server mới**. Không chạy lại script cũ chưa chỉnh vì chúng có đường dẫn, checksum và thứ tự trạng thái riêng.
5. Tạo cấu hình riêng từ mẫu: điền địa chỉ notebook mới, runtime thực tế, email chủ app và mã mời mới. Nhập khóa/token riêng trên server, quyền hạn chế; không commit. Không chép PID, lock, cờ `PUBLIC_READY` hoặc cấu hình chứa địa chỉ server cũ sang máy mới.
6. Nếu cứu được dữ liệu, khôi phục vào thư mục mới khi app chưa chạy, giữ bản backup gốc. Với runtime tự dựng cần chuẩn bị `web-process.json` chứa đường dẫn app/node mới và `.runtime/private-runtime.json`; supervisor hiện có chỉ hiểu bản legacy và không tự cài chúng.
7. Giữ `HOST=127.0.0.1`, chưa tạo `PUBLIC_READY`; không mở tunnel. Kiểm health, chặn truy cập ẩn danh, đăng nhập, đọc/lưu đề trên bản sao, Word/PDF, AI và quyền giữa hai tài khoản trước khi mở Internet.
8. Chỉ mở web/ngrok khi Thuận quyết định test. Xem [runbook vận hành](README.md). Việc chuyển sang FastAPI hoàn chỉnh tiếp tục theo task của nhóm; không dùng scaffold thay app hoàn chỉnh.

**Chưa kiểm thử khôi phục trên server mới.** Các bản nguồn lưu offline không thay cho sao lưu database và secret riêng; cần diễn tập khôi phục dữ liệu trước khi dùng cho đề quan trọng.
