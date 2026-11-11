# Bản đồ API và quyền truy cập

Đầu ra W01, W03 và một phần W05 cho [BE-2-001 #5](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/5). Cột hành vi ghi API Node đã đối chiếu trong mã nguồn. Phần đề xuất ở cuối cần BE-3, UI-1/2/3 và BE-5 review trước khi đưa vào OpenAPI. FastAPI trên main có `GET /api/health` và `GET /api/readiness`. Readiness trả 503 với danh sách phần còn thiếu. [Node HTTP](../../mvp-server.mjs) · [Node trợ lý](../../workbench-server.mjs) · [FastAPI hiện tại](../../backend/src/mach_backend/main.py)

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
