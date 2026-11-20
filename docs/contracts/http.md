# Bản đồ API và quyền truy cập

Đầu ra W01–W05 cho [BE-2-001 #5](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/5). Tài liệu phân biệt rõ ba mức trạng thái: `[Hiện có / Đã chạy bằng Python]`, `[Fixture / Mock]` và `[Chờ review nhóm / Thành viên xác nhận]`. Phần trên ghi API Node legacy đã đối chiếu trong mã nguồn và điểm review ghép FastAPI; phần dưới bổ sung đặc tả đang chạy trên FastAPI (`local_workspace` và `team_workspace`), bảo mật phiên/CSRF/upload (W04) và danh mục fixture kiểm thử chéo (W05). FastAPI foundation trên `main` có `GET /api/health` và `GET /api/readiness` (trả `503` với danh sách phần còn thiếu). Toàn bộ backend/core chính xây dựng trên Python tại `backend/src/mach_backend/`, không proxy lõi nghiệp vụ sang Node. [Node HTTP](../../mvp-server.mjs) · [Node trợ lý](../../workbench-server.mjs) · [FastAPI hiện tại](../../backend/src/mach_backend/main.py)

## Route Node và nơi gọi

| Method và đường dẫn | Input chính | Phản hồi hoặc lỗi quan sát trong mã | Caller và mảng port |
|---|---|---|---|
| GET `/api/health`, `/api/status` | Host hợp lệ | Health trả `ok`. Status trả phiên bản, tính năng và phần cấu hình đã lọc theo quyền. Guest online bị 401 ở status. | `mvp.js` và phép thử vận hành · BE-2 |
| GET `/api/account` | Cookie phiên nếu có | `user`, `workspace`, `credits`, `online`, `admin`, `localOnly`. Guest online có user và credits null. | `workbench.js` · BE-2 |
| POST `/api/account/register`, `/api/account/login` | Email, mật khẩu. Register thêm tên và mã mời online. | `user` và Set-Cookie. Lỗi đăng nhập hoặc mã mời đi qua JSON lỗi chung. | `assets/online-login.js`, `workbench.js` · BE-2 |
| POST `/api/account/logout` | Phiên hiện tại | `ok`, hết hạn cookie và thu hồi phiên phía server. | `workbench.js` · BE-2 |
| GET `/api/kv` | `key=state` hoặc `key=file:<id>` | `value`, `revision`, `updated`. Khóa chưa có trả `value:null,revision:0`. | `storage.js` · BE-2/3 |
| PUT `/api/kv` | `key`, `value`, If-Match dạng số nếu có | `revision` mới. Sai phiên bản KV trả 409. UI gửi If-Match cho state và giữ bản đang chờ ghi. | `storage.js` · BE-2/3 |
| POST `/api/config`, `/api/test-provider` | Mục cấu hình hoặc tên provider | Cấu hình công khai đã bỏ key, hoặc kết quả kiểm kết nối. Member online trả 403. | `mvp.js` · BE-1/2 |
| POST `/api/extract`, `/api/ocr`; GET `/api/page-image` | `fileId`, `name`, trang OCR tùy chọn. Ảnh trang dùng query `file`, `page`. | Dữ liệu trích/OCR hoặc PNG. Đọc tệp theo owner trước khi xử lý. Thiếu tệp đi qua lỗi chung. | `mvp.js` · BE-2/4 |
| POST `/api/parse-questions` | `text`, `images` tùy chọn | `questions`. Chặn văn bản sai kiểu hoặc trên một triệu ký tự. | `mvp.js` · BE-4 |
| POST `/api/ai/matrix`, `/api/ai/generate` | Văn bản ma trận hoặc nguồn, ma trận, môn/lớp, yêu cầu, tùy chọn consent | Ma trận gợi ý hoặc câu hỏi kèm nguồn và model. | `mvp.js` · BE-1/2 |
| POST `/api/ai/patch`, `/api/ai/check` | Câu hỏi, yêu cầu/đoạn chọn hoặc nguồn, consent | Đề xuất sửa hoặc lời giải độc lập, căn cứ và trạng thái. | `mvp.js` · BE-1/2 |
| POST `/api/assistant/plan` | `text`, đề, pending, ma trận/nguồn nếu có | Hỏi làm rõ hoặc kế hoạch có slots. Có thể đọc nguồn ma trận khi được phép. | `workbench.js` · BE-1/2 |
| POST `/api/assistant/patch` | Đề, scope, yêu cầu, consent, mức effort | `edits`, lời mô tả, revision, reference, credits. Đề hiện có mà revision lệch bị từ chối. UI còn xác nhận trước khi lưu. | `workbench.js` · BE-1/2/3 |
| POST `/api/assistant/chat` | Văn bản, ngữ cảnh, consent, effort | Tin trả lời và credits. | `workbench.js` · BE-1/2 |
| POST `/api/assistant/stream` | Kế hoạch đã duyệt, `examId`, `revision`, nguồn, consent, effort | SSE `job`, `stage`, `block`, `done` hoặc `error`. Job giữ theo owner. Lỗi sau khi mở stream đi qua event. | `workbench.js` · BE-1/5 |
| GET `/api/assistant/job`; POST `/api/assistant/cancel` | Query `id` hoặc `examId` để lấy job. Hủy nhận `id` trong body. | Snapshot job hoặc `ok,status`. Thiếu job trong phạm vi owner trả 404. Hủy đặt trạng thái cancelling và chặn kết quả tiếp theo. | `workbench.js` · BE-2/5 |
| POST `/api/save-export`; GET/HEAD `/exports/<name>` | Loại đề/backup, snapshot, định dạng, chế độ giáo viên. Tải theo tên bản xuất. | `filename,url,bytes` hoặc tệp. Online cần phiên và quyền sở hữu bản xuất. | `app.js`, `mvp.js` · BE-2/4 |
| POST `/api/share`, `/api/share/revoke` | `examId`, có đáp án, cho sao chép; hoặc token thu hồi | URL/token chia sẻ hoặc `ok`. Tạo từ đề lưu của owner và thu hồi theo owner. | `workbench.js` · BE-2/3 |
| GET `/s/<token>`; GET `/api/share/read/<token>` | Token snapshot | HTML chỉ xem, hoặc JSON theo cờ cho sao chép. Liên kết thu hồi/mất trả 404. JSON online cần phiên. | Link chia sẻ và `workbench.js` · BE-2/3 |
| POST `/api/search`, `/api/read-web` | Query hoặc URL, consent | Kết quả tìm/đọc web. Giữ riêng khi port và review quyền gửi dữ liệu ra ngoài. | `mvp.js` · BE-1/4 |

Route API không tồn tại thường trả 404 sau khi qua kiểm Host, Origin và phiên. Nhiều lỗi nghiệp vụ ở Node trả 400 với `{error: string}`. `revision` KV của workspace, revision đề và phiên bản câu là ba giá trị khác nhau.

## Quyền ở chế độ online Node

| Thao tác | Guest | Member | Admin |
|---|---|---|---|
| Health, xem trạng thái phiên, đăng nhập/đăng ký | Health/account/login/register được phép. Register cần mã mời. | Có | Có |
| Đọc/ghi workspace và tệp | 401 | Theo owner của phiên | Theo owner của phiên |
| Xem status và cấu hình | 401 | Model/route đã lọc, URL rỗng, hasKey false | Cấu hình công khai có hasKey và URL; bỏ giá trị key |
| Cập nhật cấu hình, thử provider | 401 | 403 | Có |
| Tạo đề xuất/job, đọc và hủy job | 401 | Job theo owner. AI ngoài máy cần consent theo adapter. | Cùng kiểm owner |
| Tạo và tải bản xuất | 401 | Bản xuất của phiên | Bản xuất của phiên |
| Tạo hoặc thu hồi chia sẻ | 401 | Đề hoặc liên kết của phiên | Đề hoặc liên kết của phiên |
| Xem HTML snapshot có token | Có | Có | Có |
| Đọc JSON snapshot để sao chép | 401 | Cần token hợp lệ và cờ cho sao chép | Cùng quy tắc |

Admin online do email cấu hình xác định. Session dùng cookie HttpOnly, SameSite=Strict, Secure ở online, hạn 30 ngày và token băm trong DB. Kiểm Host trước API và Origin cho các phương thức thay đổi dữ liệu. Chế độ local có kho local/guest riêng và hành vi quản trị khác online. Khi review phiên Python, chốt thời hạn, thu hồi, kiểm CSRF và xác minh email/khôi phục tài khoản trước khi mở rộng truy cập. [Phiên Node](../../accounts.mjs) · [Cấu hình HTTP](../../deployment.mjs)

## Điểm cần review khi ghép FastAPI

- Owner lấy từ phiên. Repository tra đề, tệp, bản xuất, job và snapshot theo quyền. Tài liệu gửi lên được kiểm theo giới hạn dung lượng và định dạng trước khi đọc. API public chỉ trả DTO được phép.
- Tách `workspaceRevision`, `baseRevision` của đề và `questionVersion` của câu khi ghép UI. Luồng xác nhận ghi trong giao dịch theo phiên bản gốc và trả xung đột 409 khi đề đã thay đổi. Cần chốt cách biểu diễn HTTP If-Match với UI và BE-3 trước khi phát hành. [Kế hoạch dữ liệu](../architecture/DATA_PLAN.md)
- Đề xuất lỗi Python dùng `code` và `message` ổn định. Phiên thiếu/hết hạn là 401, Host/Origin hoặc vai trò sai là 403, resource ngoài phạm vi trả 404 để không lộ sự tồn tại, payload sai schema là 422. Luồng SSE cần quy ước event cuối khi đã mở stream.
- API AI nhận ID và yêu cầu thao tác từ UI. Backend đọc snapshot và đáp án lưu theo phiên, sau đó dựng đúng kiểu dữ liệu service. UI nhận đề xuất để xem trước và gửi xác nhận riêng. Hợp đồng AI và điểm cần review nằm ở [PR #39](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/39).

## Bằng chứng chạy lại

`node --test tests/deployment.test.mjs` dùng hai tài khoản mẫu và DB tạm. T02 có thử tệp theo ID và bản xuất theo tài khoản. T03 có Origin lệch, logout thu hồi phiên và PUT workspace với revision cũ. [Kiểm thử HTTP](../../tests/deployment.test.mjs)

Đối chiếu phục vụ R2/R5/R6/R7 và CT-03/05/06. Cần thêm OpenAPI đã review và ca chạy qua FastAPI trước khi tính T01–T03 đạt trên Python.

## Đối chiếu với bản tích hợp FastAPI

| Thao tác | Hợp đồng quan sát được |
| --- | --- |
| Mở kho và lưu | `GET /api/kv?key=state` trả `value` và `revision`. `PUT /api/kv` nhận JSON với `key` và `value`, trả `revision`. Bàn soạn gửi phiên bản kho qua `If-Match`. API trả 422 nếu thiếu trường hoặc sai dạng JSON, 400 nếu phiên bản hoặc nội dung kho không hợp lệ, 409 với mã `stale_snapshot` nếu phiên bản đã cũ. |
| Đăng nhập và mở tài nguyên nhóm | `GET /api/account` trả thông tin của phiên hiện tại. Kho, tệp nguồn và bản xuất dùng phạm vi tài khoản. Khi UI gửi `X-Workspace-Context` của tab cũ sau khi đổi tài khoản, API trả 409 với mã `workspace_context_changed`. Logout thu hồi phiên. |
| Đổi kết nối AI | `GET /api/config` trả thiết lập và trạng thái đã có khóa. Trong chế độ nhóm, `POST /api/config` chỉ dành cho quản trị viên. Thành viên dùng kết nối chung mà không nhận giá trị khóa. |
| Chia sẻ | `POST /api/share` tạo bản chụp. Chủ bản chia sẻ xem danh sách qua `GET /api/share?examId=…` và thu hồi qua `POST /api/share/revoke`. Người có đường dẫn mở `GET /s/{token}`. `GET /api/share/read/{token}` chỉ kèm dữ liệu đề khi chủ bật cho sao chép. Liên kết đã thu hồi trả 404. |
| Khôi phục | `POST /api/workspace/restore/preview` đọc và kiểm tra bản sao. `POST /api/workspace/restore` kiểm lại phiên bản hiện tại trước khi ghi. Chế độ nhóm khôi phục trong kho của phiên hiện tại. |

[Kiểm thử quyền và phiên](../../backend/tests/test_team_workspace.py) · [Kiểm thử chia sẻ](../../backend/tests/test_workspace_shares.py) · [Kiểm thử kết nối](../../backend/tests/test_poc_connections.py) · [Kiểm thử khôi phục](../../backend/tests/test_workspace_backup.py)

### Ví dụ lưu kho trống

Ví dụ dùng kho thử mới có revision `0`. Khi lưu kho đang sử dụng, lấy revision từ lần đọc hiện tại và gửi đầy đủ trạng thái cần giữ.

```http
PUT /api/kv
Content-Type: application/json
If-Match: 0

{"key":"state","value":{"exams":[],"prefs":[]}}
```

Phản hồi lần lưu đầu là `200 {"revision":1}`. Gửi lại cùng `If-Match: 0` nhận 409 và dữ liệu vẫn ở revision 1. Đọc lại kho qua `GET /api/kv?key=state`.

Schema của bàn soạn tại máy có ở `/openapi.json`, gồm `WorkspaceWrite`, `WorkspaceRevision`, `WorkspaceSnapshot` và header `if-match`. Chế độ nhóm chuyển yêu cầu kho vào FastAPI của tài khoản qua mounted ASGI app, nên OpenAPI ở app nhóm chỉ liệt kê route trực tiếp của lớp nhóm. [Kiểm thử schema và revision](../../backend/tests/test_local_workspace.py)

## Bảo mật phiên, CSRF và kiểm soát tệp tải lên (W04)

### 1. Phiên, cookie `soande_team_session`, logout và TTL (`[Hiện có / Đã chạy bằng Python]`)

| Thành phần | Quy chuẩn đang chạy trong Python (`team_workspace.py`, `team_accounts.py`) | Đối chiếu Node legacy (`accounts.mjs`, `deployment.mjs`) | Điểm cần siết trước khi mở public (`[Chờ review nhóm / Thành viên xác nhận]`) |
|---|---|---|---|
| Tên & cờ cookie | `COOKIE = "soande_team_session"`; `httponly=True`, `samesite="strict"`, `secure=False`, `max_age=SESSION_SECONDS`. | `soande_session`; `HttpOnly`, `SameSite=Strict`, bật `Secure` khi chạy online HTTPS. | Bắt buộc chuyển `secure=True` khi đặt sau HTTPS công khai. |
| Sinh & lưu token phiên | Sinh bằng `secrets.token_urlsafe(32)`; DB SQLite bảng `sessions(token, user_id, expires)` **chỉ lưu hàm băm SHA-256** (`digest(token)`). Kiểm độ dài chuỗi cookie `<= 100`. | Lưu token băm trong kho phiên. | Giữ nguyên không lưu plaintext token vào SQLite hay log. |
| Lưu mật khẩu | Băm bằng `scrypt(n=16384, r=8, p=1, dklen=64)` với `salt` ngẫu nhiên 16 byte; kiểm khớp bằng `hmac.compare_digest`. | Băm mật khẩu có salt theo bản Node cũ. | Độ dài mật khẩu hợp lệ `Register` / `SignIn`: `10..200` ký tự (`Register` thêm `name` `1..100`, `inviteCode` `20..100`). |
| TTL / hết hạn | `SESSION_SECONDS = 8 * 3600` (8 giờ). Mỗi lần tạo phiên mới (`new_session`), dọn các dòng `sessions WHERE expires <= now`; đọc phiên kiểm `sessions.expires > now`. | 30 ngày (`30 * 86400` giây). | Chốt với BE-2/UI-1 xem 8 giờ là mặc định sản phẩm hay cho gia hạn phiên chủ động. |
| Thu hồi phiên (`logout` & reset) | `POST /api/account/logout` xóa bản ghi `digest(token)` trong SQLite và gọi `delete_cookie(COOKIE, httponly=True, samesite="strict")`, trả `{"ok": true}`. Helper CLI `accounts.reset_password()` thu hồi **toàn bộ** phiên của `user_id` đó và xóa `attempts`; hàm `login()` kiểm lại hash sau khi băm để không cấp phiên bằng mật khẩu vừa bị reset đồng thời. | `POST /api/account/logout` xóa phiên và hết hạn cookie. | Bổ sung endpoint cho người dùng tự đăng xuất tất cả thiết bị nếu cần. |

### 2. Chế độ `invite-only`, chống brute-force và lưu ý mở đăng ký rộng

- **Cơ chế `invite-only` (`[Hiện có / Đã chạy bằng Python]`)**: chỉ `admin` gọi được `POST /api/account/invitations` (tài khoản `member` nhận HTTP `403`, chưa đăng nhập nhận `401`). Mã mời 32 byte chỉ trả một lần trong JSON `{inviteCode, email, expiresIn: 86400}` (24 giờ) và lưu băm SHA-256 trong bảng `invites`. Khi `POST /api/account/register` tiêu thụ mã, giao dịch `BEGIN IMMEDIATE` kiểm `used=0`, `expires > now`, ràng buộc đúng `email` (nếu mã mời gán cho email cụ thể) rồi đặt `used=1`.
- **Chống brute-force (`[Hiện có / Đã chạy bằng Python]`)**: bảng `attempts(key, count, started)` trong SQLite dùng khóa `digest(client_host + "\0" + email)`. Nếu thất bại `>= 10` lần trong cửa sổ `600` giây (10 phút), `login()` trả HTTP `429`; đăng nhập đúng sẽ xóa dòng `attempts` tương ứng. Khác với Node lưu `Map` trong RAM, bộ đếm SQLite được giữ qua khởi động lại tiến trình.
- **Giới hạn cần lưu ý trước khi mở đăng ký rộng (`[Chờ review nhóm / Thành viên xác nhận]` — BE-2/BE-5)**:
  1. **Chưa có xác minh email và tự khôi phục mật khẩu**: tài khoản tạo qua mã mời hoạt động ngay không gửi thư xác nhận; việc đặt lại mật khẩu hiện chỉ thực hiện qua CLI `reset_password()` của người quản lý máy.
  2. **Khóa đếm `attempts` phụ thuộc `request.client.host`**: nếu đặt sau reverse proxy cần cấu hình lớp đọc IP thật từ proxy tin cậy (`X-Forwarded-For`), đồng thời cân nhắc thêm giới hạn theo IP tổng để chặn dò mật khẩu dàn trải trên nhiều email khác nhau.
  3. **Cache `workspaces` theo tiến trình và bộ nhớ trong `team_workspace.py`**: mỗi `user_id` đăng nhập được giữ app FastAPI riêng trong dict `workspaces` trên RAM cho tới khi restart; cần giới hạn số workspace hoạt động đồng thời hoặc dọn cache theo phiên nhàn rỗi trước khi mở cho nhiều người dùng.

### 3. Cơ chế `Host`/`Origin`/CSRF và header đồng bộ theo từng transport (`[Hiện có / Đã chạy bằng Python]`)

| Cơ chế / Header | `local_workspace.py` (`loopback_boundary`) | `team_workspace.py` (`boundary`) | Ghi chú đối chiếu & review |
|---|---|---|---|
| Kiểm `Host` | Chỉ nhận `{"127.0.0.1", "localhost", "testserver"}`; ngoài danh sách trả `403`. | Chỉ nhận `{"127.0.0.1", "localhost", "testserver"}`; ngoài danh sách trả `403`. | Node `deployment.mjs` dùng `allowedHosts` lấy từ `APP_PUBLIC_URL`; bản HTTPS Python sau này cần danh sách host tin cậy tương đương (`[Chờ review nhóm / Thành viên xác nhận]`). |
| Kiểm `Origin` (chống CSRF) | Mọi method khác `GET`/`HEAD`/`OPTIONS` phải có `Origin == str(request.base_url).rstrip("/")`, sai hoặc thiếu trả `403`. | Cùng điều kiện `Origin == str(request.base_url).rstrip("/")` (trả `403`), kết hợp cookie `SameSite="strict"`. | Bảo đảm thao tác mutate không thể gọi từ trang web ngoài qua form/fetch kèm cookie. |
| Header bảo mật phản hồi | Route `/api/exams/.../check` gắn `Cache-Control: no-store`. | Gắn `Cache-Control: no-store` và `X-Content-Type-Options: nosniff` cho mọi response. | Nên thống nhất gắn `no-store` và `nosniff` trên cả hai lớp ứng dụng (`[Chờ review nhóm / Thành viên xác nhận]`). |
| Giới hạn kích thước body (`Content-Length`) | `MAX_BACKUP` (`150 MiB`) cho `BACKUP_PATHS`; `30 MiB` cho các path còn lại (vượt trả `413`). | `8192` byte cho `/api/account/*`; `150 MiB` cho `BACKUP_PATHS`; `30 MiB` cho phần còn lại (vượt trả `413`). | Ngăn payload tài khoản/auth cỡ lớn gây tốn CPU khi băm mật khẩu hoặc JSON lớn. |
| Header `X-Workspace-Context` | Không bắt buộc (workspace đơn `owner="local"`). | Với mọi `/api/*` có header này: chưa đăng nhập trả `401`; khác `"team:" + current["id"]` trả `409 {"code": "workspace_context_changed"}`. | `storage.js` gửi `"team:<userId>"` để ngăn tab cũ ghi đè sang tài khoản vừa đăng nhập ở tab khác. |
| Header `If-Match` | Dùng cho `PUT /api/kv` (`re.fullmatch(r"[0-9]{1,19}", if_match)`, sai định dạng trả `400`, cũ hơn revision hiện tại trả `409 stale_snapshot`) và bắt buộc ở `POST /api/workspace/restore`. | Chuyển tiếp nguyên header `If-Match` vào FastAPI mounted theo tài khoản và trả cùng mã `400`/`409`. | Hiện `PUT /api/kv` cho phép bỏ trống `if_match` (`None`) nếu client không gửi; cần chốt bắt buộc `If-Match` cho `key=state` và quy ước ETag giữa UI và BE-2/BE-3 (`[Chờ review nhóm / Thành viên xác nhận]`). |
| Header `X-PoC-Config` | Với `AgentGeneration`, bắt buộc khớp `provider.connection_stamp` ở `/proposals/generate`, `/check`, `/api/assistant/patch`; lệch trả `409 config_changed`. Đổi `/api/config` khi AI bận trả `409 job_limit`. | Thành viên không gọi được `POST /api/config` (`403`); app tự đồng bộ cấu hình admin trong RAM trước khi phục vụ thành viên. | Phục vụ xác nhận nơi gửi nguồn trước khi chạy model. |

### 4. Chính sách xử lý tệp tải lên không tin cậy (`[Hiện có / Đã chạy bằng Python]`)

Nguyên tắc chung trong [local_documents.py](../../backend/src/mach_backend/local_documents.py), [matrix_import.py](../../backend/src/mach_backend/matrix_import.py), [workspace_backup.py](../../backend/src/mach_backend/workspace_backup.py), [word_export.py](../../backend/src/mach_backend/word_export.py), [export_assets.py](../../backend/src/mach_backend/export_assets.py), [source_ocr.py](../../backend/src/mach_backend/source_ocr.py) và [share_snapshot.py](../../backend/src/mach_backend/share_snapshot.py): **không tin đuôi tệp hoặc MIME khai báo chung** (`""` hoặc `application/octet-stream`); kiểm giới hạn dung lượng trước, giải mã base64 chuẩn (`validate=True`), xác thực chữ ký nhị phân / ảnh / cấu trúc archive trước khi lưu hoặc đưa sang AI, và escape/cô lập trước khi xuất HTML hoặc DOCX.

- **Giới hạn dung lượng và cấu trúc đọc từ mã nguồn**:
  - `MAX_DOCUMENT = MAX_FILE = 15 * 1024 * 1024` (`15 MiB`) áp dụng cho tệp nguồn (`extract_text`), tệp ma trận (`decode_file`), tệp đính kèm trong bản sao (`check_file`) và đường dẫn tải nguồn `GET /api/source-file/{file_id}` (tiền kiểm chuỗi data URL `<= MAX * 4 // 3 + 200`; trong khi Node legacy từng cho phép `20 MiB`).
  - `MAX_BACKUP = 150 * 1024 * 1024` (`150 MiB`) cho bản sao lưu; duyệt cây JSON giới hạn tối đa độ sâu `50` và `500.000` nút; từ chối `NaN`/`Infinity` qua `finite_float`.
  - Giới hạn văn bản & trang trích xuất: `local_documents.extract_text` chặn tổng văn bản `<= 200.000` ký tự và PDF `1..100` trang; `matrix_import.decode_file` chặn `MAX_TEXT = 40.000` ký tự; OCR AI qua [source_ocr.py](../../backend/src/mach_backend/source_ocr.py) nhận tối đa `20` trang mỗi lượt.
  - Giới hạn chia sẻ & xuất Word: tối đa `300` câu, snapshot chia sẻ JSON tối đa `25 MB` (`25_000_000` byte), rich text sâu tối đa `64` tầng và `50.000` nút, tệp `.docx` đầu ra tối đa `30 MiB`, bảng `1..200` hàng.
- **Kiểm chứng định dạng theo nội dung thật (Magic bytes, ZIP/XML, SVG)**:
  - **PDF**: bắt buộc bắt đầu bằng magic bytes `b"%PDF-"`; `pdf_pages()` cấu hình `pypdf.PdfReader(..., strict=True, xref_stream_maximum_entries=100000)` với giới hạn luồng giải nén `8_000_000` byte/luồng, từ chối tệp mã hóa (`encrypted_document`) và `GET /api/source-file/{file_id}` chỉ phát tệp khi `startswith(b"%PDF-")`.
  - **Ảnh raster (`PNG`, `JPEG`, `WEBP`)**: mọi luồng nhập/sao lưu/xuất chỉ nhận 3 định dạng này; dùng Pillow `Image.open(..., formats=...)` + `image.load()` / `image.verify()`, giới hạn **`width * height <= 20_000_000` pixel** (ngăn bomb ảnh `DecompressionBombError`). Khi xuất Word/HTML (`word_export.image_bytes()`), bắt buộc ảnh đơn khung (`n_frames == 1`) và tái mã hóa sang PNG sạch trước khi nhúng. Ở bản sao lưu có MIME trống/`application/octet-stream`, `check_file()` chỉ chấp nhận khi toàn bộ tham chiếu trỏ đúng 1 loại tệp và `image.format` khớp loại đã suy ra.
  - **OOXML (`DOCX`, `XLSX`, `PPTX` — ZIP + XML)**: mở qua `zipfile.ZipFile`. `matrix_import.decode_file()` chặn zip bomb với tổng `file_size <= MAX_FILE * 2` (`30 MiB`) và `len(z.infolist()) <= 2000`, giới hạn cột bảng tính `<= 100` và từ chối ô chứa công thức `<f>` (`matrix_formula`). `local_documents.extract_text()` kiểm tổng `file_size` của `word/document.xml` hoặc `ppt/slides/slideN.xml` `<= 15 MiB` và phân tích bằng `xml.etree.ElementTree.fromstring` (Python 3.12 stdlib không nạp thực thể XML ngoài). `workspace_backup.check_file()` kiểm tiền tố nội bộ `word/`, `xl/`, `ppt/`. *(Cần review BE-2/BE-4 `[Chờ review nhóm / Thành viên xác nhận]`: bổ sung chặn số lượng entry `<= 2000` và từ chối khai báo `<!DOCTYPE` / `<!ENTITY` đồng bộ cho `local_documents.extract_text()` tương tự `matrix_import` / `word-import.mjs`).*
  - **SVG & nội dung HTML/Rich text**: **từ chối hoàn toàn tải lên tệp SVG không tin cậy** ở nhập nguồn, nhập ma trận, ảnh câu hỏi và khôi phục bản sao (`extract_text`, `decode_file`, `check_file`, `image_bytes`). Mọi SVG xuất hiện khi xem HTML hoặc chia sẻ đều do backend tự dựng từ dữ liệu có cấu trúc đã kiểm (`figure` tọa độ hình học trong `share_snapshot.figure_copy` và `dataChart` số liệu trong `word_export.data_chart`) bằng Chromium headless cô lập mạng (`export_assets.py` chạy `export-render.mjs` với `--no-proxy-server`, `--host-resolver-rules=MAP * ~NOTFOUND`, KaTeX `trust=false`) và raster hóa sang PNG khi nhúng DOCX. Toàn bộ văn bản xuất HTML đi qua `html.escape(..., quote=True)`, liên kết rich text chỉ cho phép `http`/`https`.

## Danh mục fixture hợp đồng cho kiểm thử chéo (W05)

Trạng thái hiện tại: các bộ dữ liệu là **`[Fixture / Mock]`** dùng chạy lại tự động trong CI và Python/Node; bảng phân mảnh `owner`, `ID`, `version` dưới đây đang **`[Chờ review chéo UI-1/3 và BE-1/3/4/5]`** để thống nhất kiểm thử hợp đồng đầu cuối giữa giao diện và FastAPI.

| Nguồn fixture / suite kiểm thử | Phân tách `owner` | Các `ID` đại diện | Các `version` / `revision` kiểm chứng | Mục đích kiểm thử chéo UI / BE |
|---|---|---|---|---|
| [tests/fixtures/be3-legacy-kv.json](../../tests/fixtures/be3-legacy-kv.json) · [test_be3_migration.py](../../backend/tests/test_be3_migration.py) | `a1000000000000000000000000000001` (`gv.toan@...`), `b2000000000000000000000000000002` (`gv.dia@...`), `corrupt-user` | Đề `exam-math-001`, `exam-geo-001`, `exam-deleted-999`; câu `q-math-001`, `q-math-002`, `q-geo-001`; tệp `file-shared-pdf`, `file-shared-pdf-b`, `file-orphan-01`, `file-corrupt-b64`; job `job-math-001`, `job-deleted-exam-999`; 2 share token | KV state `rev=2` (Toán) vs `rev=1` (Địa); đề `revision=2` vs `1`; câu `q-math-001` `v=2`, `q-math-002` `v=1`, `q-geo-001` `v=1`; tệp/job `rev=1` | Đối chiếu cô lập dữ liệu theo 2 chủ sở hữu khác nhau, phát hiện dữ liệu hỏng (`corrupt_extra_rows`), chuyển đổi sang bảng SQLite (BE-3, BE-2, UI-1). |
| [tests/fixtures/ai-patch-local.json](../../tests/fixtures/ai-patch-local.json) · [test_ai_patch.py](../../backend/tests/test_ai_patch.py) · [test_patch_confirmation.py](../../backend/tests/test_patch_confirmation.py) | `ownerId` giả lập trong test Python (`chu-de-mau`, `teacher-1`, `teacher-2`) | `questionId = 5907b3d3-6402-40ba-9b6e-5e0faf6d46a3`, `blockId = d274a7ce-2c6c-4b06-aad6-5ca1a7e44293`; `examId`/`jobId`/`sourceId` cấp theo ca thử | `baseRevision=4`, `questionVersion=2`, `sourceVersion=3` (kèm ca tăng `revision` và `questionVersion` sau `confirm`) | Kiểm định vị UTF-16 có emoji (`🔎`), 3 ca biên (`giu-ngoai-vung`, `doi-tien-to`, `doi-hau-to`), lệch phiên bản/chủ sở hữu `404`/`409` (BE-1, BE-2, BE-3, UI-3). |
| [tests/fixtures/ai-sinh-kiem.json](../../tests/fixtures/ai-sinh-kiem.json) · [test_ai_questions.py](../../backend/tests/test_ai_questions.py) · [test_generation_confirmation.py](../../backend/tests/test_generation_confirmation.py) | Chủ sở hữu tách riêng giữa các test (`teacher-1` vs `teacher-2`) | `sourceId = d9ce320a-dbd2-4465-9335-75d6c4b104e4`; 4 dạng câu (`mcq`, `truefalse`, `short`, `essay`), mỗi câu `pointsQ4=10` (tổng `40`) | `sourceVersion = 3`; kiểm các ca đổi `baseRevision` và đổi `sourceVersion` trong khi chạy hoặc trước khi `confirm` | Kiểm đủ 4 dạng câu, sinh & kiểm mù, cấp UUID câu/khối mới ở `v=1` khi lưu đề (BE-1, BE-3, BE-5, UI-3). |
| [tests/fixtures/ui2-editor-golden.json](../../tests/fixtures/ui2-editor-golden.json) | Đề dùng chung mức ứng dụng cho UI-2 / xuất tài liệu | `multiSubjectExam` (`id = cc62f9d2-918f-4ef7-a5e7-437ed5e603f6`, 3 câu `d74903bf-...`, `73ab288e-...`, `377daef0-...`); `longPaginatedExam` (`id = 46473f2e-a903-49fc-a996-6d2cf9896ce7`, 10 câu); nhóm `edgeCases` | Toàn bộ các đề và câu trong mẫu dùng `revision = 1`, `v = 1` | Kiểm bảo toàn rich document (`richDoc`, `mathInline`, bảng, phân trang, ký tự đặc biệt) giữa UI-2 và backend xuất Word/HTML/chia sẻ (UI-2, BE-3, BE-4). |
| [tests/fixtures/ai-math-structure.json](../../tests/fixtures/ai-math-structure.json) · [test_math_structure.py](../../backend/tests/test_math_structure.py) | Không gắn owner | 17 biểu thức mẫu (`fractions`, `roots`, `systems`, `matrices`, `escaped`, `truncated`, ...) | N/A | Đối chiếu khớp 100% kiểm cấu trúc LaTeX giữa Python `validate_ai_text` và renderer UI (BE-1, UI-2). |
| [backend/poc-data/bio-tham-thau.json](../../backend/poc-data/bio-tham-thau.json) · [backend/poc-data/thu-vien.json](../../backend/poc-data/thu-vien.json) | `ownerId = "poc-local"` | Sinh học: `jobId = c237d350-...`, `examId = 3f2378b0-...`, 3 nguồn `652e7539-...901/902/903`; Ngữ văn: `jobId = 108e80de-...`, `examId = 02af8760-...`, nguồn `cf5fe178-...` | `baseRevision = 1`, `sourceVersion = 1` | Fixture PoC chuẩn hóa cho kiểm thử sinh từ ngữ liệu và đánh giá agent (BE-1, BE-5, UI-3). |
| Bộ test HTTP đa chủ sở hữu FastAPI: [test_team_workspace.py](../../backend/tests/test_team_workspace.py), [test_workspace_shares.py](../../backend/tests/test_workspace_shares.py), [test_workspace_backup.py](../../backend/tests/test_workspace_backup.py), [test_ai_routes.py](../../backend/tests/test_ai_routes.py), [test_check_routes.py](../../backend/tests/test_check_routes.py) | 2+ tài khoản động (`admin` vs `member`, `owner-a` vs `owner-b`) trong SQLite tạm | UUID sinh động theo từng test cho đề, câu, khối, nguồn, job, token chia sẻ và tệp `file:<id>` | Đẩy tăng `kv revision` (`0 -> 1 -> 2`), `exam baseRevision`, `questionVersion`, `sourceVersion` qua nhiều bước và thử `If-Match` cũ | Kiểm đầu cuối quyền `401`/`403`/`404`/`409`/`429`, `X-Workspace-Context`, `If-Match`, và đối chiếu chéo với [tests/deployment.test.mjs](../../tests/deployment.test.mjs) phía Node legacy (`[Hiện có / Đã chạy bằng Python]` trên kho tạm). |

### Các điểm cần nhóm chốt ở vòng review chéo W05 (`[Chờ review chéo UI-1/3 và BE-1/3/4/5]`)

- Thống nhất với UI-1/2/3 và BE-2/3 về việc bắt buộc gửi `If-Match` cho mọi ghi `PUT /api/kv?key=state` (thay vì tùy chọn `None` khi bỏ qua header) và chuẩn định dạng số hay chuỗi ETag có dấu ngoặc kép.
- Thống nhất một envelope lỗi JSON chuẩn (`{code, message}` vs `{error, code}`) giữa các route PoC cũ (`local_workspace` / `team_workspace`) và bộ router chuẩn mới (`patch_routes`, `check_routes`).
- Xác nhận danh sách fixture tối thiểu UI-1/3 dùng làm golden input khi tích hợp màn hình đăng nhập nhóm, chỉnh sửa rich text và xem trước/xác nhận đề xuất AI trên FastAPI.
