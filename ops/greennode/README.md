# GreenNode — chỉ Thuận vận hành

**Đích backend chính là Python/FastAPI. Các lệnh supervisor web Node dưới đây chỉ dành bản thử cũ, không phải cách triển khai Python mới. BE-1 sẽ bàn giao runbook Python sau khi các slice đủ chức năng; scaffold không được dùng thay app thật.**

Thành viên khác chỉ đọc source, tạo fixture/test và gửi PR. **Không đăng nhập server, không nhận token và không chạy lệnh triển khai thay Thuận.** Repo này không mang URL truy cập thật, trọng số, kho đề, key hay thông tin tài khoản server.

## Những file đã chuẩn bị

| File | Dùng cho |
|---|---|
| `server-kit/preflight.py` | Kiểm tra đọc trong ProJ_VA trước cài AI |
| `server-kit/setup_ai.py`, `start_ai.sh`, `stop_ai.py`, `worker.py` | Cài/chạy/dừng worker AI riêng; setup tải model/biên dịch và cần Thuận đọc trước |
| `greennode.mjs`, `tests/greennode.test.mjs` | Bridge app và test hàng đợi giả lập, nhóm dùng local |
| `server-kit/green_web_supervisor.py` | Giám sát web/ngrok của cài đặt đã có; không phải bộ cài server trắng |
| `server-kit/store_web_token.py` | Thuận nhập ngrok token bằng getpass, không in giá trị; từ chối ghi đè |
| `runtime-config.example.json` | Mẫu cấu hình web **chưa dùng được**; điền đường dẫn runtime/release thật riêng trên server |
| `ai-request.example.json` | Minh họa request worker, không chứa dữ liệu thật |
| `docs/team/RELEASE.md` | Checklist trước mở web/model thật |

**Chưa chạy bộ cài, cập nhật source hoặc bật web trên GreenNode trong đợt tổ chức repo này.** Bộ script AI hiện có phải được Thuận kiểm lại theo GPU/runtime hiện tại; không coi số liệu cấu hình cũ là tài nguyên bảo đảm.

## Thư mục được phép

```text
/network-volume/ProJ_VA/
  soande_ai/          # worker/model/runtime/cache/log/jobs riêng
  mach_web/
    releases/        # source + node_modules theo bản phát hành
    .data/           # dữ liệu thật, không commit
    .runtime/        # node/browser/config/token/flags riêng, không commit
    supervise_web.py
    web-process.json # metadata đường dẫn node/app của cài đặt hiện có
```

Không sửa Jupyter toàn cục, process hoặc dữ liệu dự án khác. Phát hiện Jupyter cho truy cập không xác thực thì Thuận xử lý ở quyền quản trị GreenNode trước khi đưa dữ liệu thật lên; giữ kín link không đủ thay bảo vệ đăng nhập.

## Cập nhật bản thử đang có — Thuận tự thực hiện

1. Xem commit/PR, backup theo phương án DB hiện tại trên bản sao; xác minh đủ quyền và dung lượng.
2. Tạm dừng web bằng lệnh bên dưới, chờ process dừng trước khi thao tác DB. Không dừng worker/model nếu không cần.
3. Tải source vào **release mới**, `npm ci` với Node 24 đã cài riêng. Giữ nguyên `.data`, `.runtime`, secret và bản cũ. Không chạy clean/reset/giải nén chồng toàn bộ mach_web.
4. Test local/fixture của release mới bằng DB tạm, không dùng kho thật. Mọi migration cần BE-3 hướng dẫn và rollback đã diễn tập.
5. Khi đã đạt, cập nhật `web-process.json` (chỉ đường dẫn app/node mới trong mach_web) và config riêng theo cài đặt thực tế. Supervisor đọc `.runtime/private-runtime.json` khi start; không ghi đè bằng template chưa điền.
6. Thuận mới bật lại; kiểm `api/health`, đăng nhập, hai user, AI, Word/PDF. Nếu lỗi dừng candidate và phục hồi đường dẫn release cũ, không xóa DB.

MVP trên volume mạng chỉ cho một process SQLite ở chế độ EXCLUSIVE/DELETE; kiểm thử cũ không bảo đảm an toàn mọi lỗi NFS. Nếu mở rộng nhiều người, chốt ADR dữ liệu trước.

## Dừng cả app web và ngrok (cài đặt đã có)

```sh
cd /network-volume/ProJ_VA/mach_web
touch .runtime/STOP
rm -f .runtime/PUBLIC_READY
```

Supervisor nhận STOP rồi đóng process con và tự thoát. Đợi dừng và kiểm port/health không còn trả thành công. Không xóa thư mục dữ liệu. Chỉ xóa PUBLIC_READY khi không có STOP là đóng Internet nhưng để app nội bộ chạy.

## Bật lại — chỉ khi Thuận muốn công khai

```sh
cd /network-volume/ProJ_VA/mach_web
rm -f .runtime/STOP
touch .runtime/PUBLIC_READY
nohup python3 supervise_web.py >> supervisor.log 2>&1 < /dev/null &
```

Cần đúng bộ cài/config/token đã có; lệnh không tự cài runtime, mua ngrok hoặc xác thực hộ. Kiểm khóa supervisor để tránh chạy trùng, HTTPS và quota sau khi start. Chưa thiết lập tự khởi động notebook hoặc bảo đảm 24/7.

## Nhóm test AI mà không vào server

`npm test` có `tests/greennode.test.mjs` mô phỏng Jupyter queue và test provider; UI dùng fixture `tests/*browser.mjs`. Không cần real URL/token. Kết quả fixture phải ghi rõ fixture, không dùng làm bằng chứng model thật hoạt động.
