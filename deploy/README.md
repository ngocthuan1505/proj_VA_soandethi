# Triển khai máy chủ riêng

**Tài liệu này áp dụng prototype Node cũ, không phải backend Python chính của đồ án. Xem [kế hoạch Python](../docs/architecture/PYTHON_MIGRATION.md) và [backend](../backend/README.md). Không triển khai scaffold thay app hoàn chỉnh; GreenNode do riêng Thuận vận hành.**

Dùng Ubuntu/Debian x86_64, ưu tiên 4 GB RAM cho PDF/OCR; chưa kiểm tra tải nhiều giáo viên. Cài Docker Engine và Compose theo [hướng dẫn chính thức](https://docs.docker.com/engine/install/ubuntu/). Docker phải tự chạy sau reboot. Chỉ mở SSH, TCP 80/443; không công khai cổng 4173. Trỏ bản ghi DNS A về IPv4 VPS, chỉ tạo AAAA khi IPv6 đã cấu hình đúng. Caddy tự xin/gia hạn chứng chỉ khi tên miền và hai cổng truy cập được.

Clone repo vào thư mục dự án trên VPS. Từ thư mục repo chạy `cd deploy`, sau đó:

```sh
cp .env.example .env
chmod 600 .env
openssl rand -hex 32
```

Sửa `.env` trực tiếp trên máy chủ: đặt `MACH_DOMAIN`, `APP_ADMIN_EMAIL`, và chuỗi ngẫu nhiên vừa tạo vào `APP_SIGNUP_CODE`. Chưa chia sẻ mã mời cho ai cho đến khi chính chủ tạo xong tài khoản quản trị. Email này được đối chiếu theo cấu hình, chưa có bước xác minh email qua thư; người giữ mã mời có thể đăng ký một email còn trống.

```sh
docker compose config --quiet
docker compose up -d --build
docker compose ps
curl --fail https://TEN_MIEN_CUA_BAN/api/health
```

Mở tên miền, bấm **Có mã mời? Tạo tài khoản**, đăng ký đúng email chủ app và mật khẩu riêng ít nhất 10 ký tự. Sau đó mới phát mã mời cho giáo viên khác. Đề, tệp gốc, phiên đăng nhập và bản xuất lưu trong volume `mach_data`; tài khoản thường không chỉnh được kết nối AI. Đăng xuất vô hiệu hóa phiên phía máy chủ. Liên kết chia sẻ là liên kết bí mật: ai có link đều xem được bản snapshot đã chia sẻ; có thể thu hồi trong app.

`restart: unless-stopped` tự bật lại tiến trình bị thoát và container sau reboot khi Docker đang chạy. Healthcheck phát hiện lỗi phản hồi nhưng Compose không tự khởi động lại tiến trình còn sống mà bị treo. Đây không phải cam kết uptime tuyệt đối.

## Giữ cấu hình AI qua lần khởi động lại

Chủ app dùng màn hình Kết nối AI như bản tại máy. Khóa nhập ở đó chỉ tồn tại trong bộ nhớ phiên server. Để giữ qua reboot, đặt JSON trong `APP_AI_CONFIG` của `.env` (không đưa vào mã nguồn, không gửi vào chat).

Cấu hình dùng worker hiện tại, không cần nhập khóa dịch vụ API trả phí:

```dotenv
APP_AI_CONFIG='{"greennode":{"url":"https://your-notebook.notebook.console.greennode.ai","model":"qwen3:8b"},"routes":{"generate":"greennode","patch":"greennode","check":"greennode"}}'
```

Bridge đã cố định đường dẫn `/network-volume/ProJ_VA/soande_ai`; không dùng thư mục dự án khác. Worker GreenNode vẫn phải chạy và cho VPS kết nối. Nếu Jupyter bật token, chủ app nhập token trong cấu hình bảo mật trên server. Không tắt bảo vệ Jupyter để triển khai web. Các khóa Gemini/GPT/Claude có thể thêm vào từng provider trong JSON qua thao tác nhập riêng; không tự bật hoặc gọi nhà cung cấp trả phí.

Sau sửa `.env`: `docker compose up -d`. Cấu hình AI trong môi trường có ưu tiên khi khởi động; nếu sửa cùng trường trong UI, lần restart sau sẽ dùng lại giá trị môi trường.

## Sao lưu, cập nhật, khôi phục

SQLite và bản xuất nằm trong volume, độc lập với image. **Không chạy `docker compose down -v`**, vì `-v` xóa dữ liệu. Không sao chép tệp SQLite đang chạy bằng `cp` đơn lẻ.

Sao lưu nhất quán, có gián đoạn ngắn; chạy Bash trên VPS trong `app/deploy`:

```sh
umask 077
mkdir -p backups
docker compose stop app
docker compose run --rm --no-deps --entrypoint tar app -cz -C /var/lib/mach . > "backups/mach-$(date +%Y%m%d-%H%M%S).tar.gz"
docker compose start app
```

Nếu lệnh sao lưu lỗi, vẫn chạy `docker compose start app` và không coi archive lỗi là bản lưu hợp lệ. Bản sao chứa dữ liệu riêng, tài khoản băm mật khẩu và phiên đăng nhập; giữ bí mật, tải một bản ra nơi khác. Sao lưu cùng VPS không bảo vệ khỏi mất toàn bộ VPS. Chưa thiết lập lịch sao lưu ngoài máy tự động.

Trước cập nhật hãy sao lưu. Upload mã mới rồi `docker compose up -d --build`, giữ nguyên `.env` và volume. Để khôi phục: dừng app, khôi phục archive đã kiểm tra vào volume trống bằng tài khoản quản trị VPS, giữ quyền UID 1000; không giải nén chồng lên dữ liệu đang dùng. Cần kiểm chứng khôi phục trên VPS thật trước khi dùng cho đề quan trọng.

## Đã kiểm tra và giới hạn

Đã kiểm tra Node và trình duyệt bằng máy chủ/dữ liệu tạm; HTTP contracts kiểm tra tách tài khoản, CSRF, quyền admin, bản xuất riêng, chia sẻ và giữ dữ liệu sau restart. Browser thử TLS qua proxy cục bộ với chứng chỉ tạm chỉ dùng trong QA; không cài chứng chỉ vào máy. Có thử tải Word/PDF sau đăng nhập. Kết quả nằm trong bộ báo cáo đi kèm.

Máy Windows này chưa có Docker: chưa build/chạy image Linux, chưa kiểm chứng Caddy, DNS/chứng chỉ công khai, tự phục hồi sau reboot, sao lưu/khôi phục hay tải đồng thời trên VPS thật. Chưa chuyển kho đề cũ lên mạng. Bản online có đăng ký bằng mã mời, chưa có tự đặt lại mật khẩu qua email, trang quản trị thành viên hoặc bảo đảm SLA; phù hợp nhóm nhỏ được mời sau khi hoàn tất bước triển khai và kiểm tra thực tế.
