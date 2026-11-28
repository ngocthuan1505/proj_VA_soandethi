# Mở demo và xem log thật theo từng bước

Đây là công cụ **chỉ đọc** app PoC local đang chạy. Không bật server, không đổi key/model,
không tạo lượt gọi AI và không xác nhận lưu thay người dùng. Các file này chưa được đẩy GitHub.

## Cách mở khi máy sẵn sàng quay

1. Trong app, chọn **đề QA riêng muốn quay**. Nếu muốn theo dõi từ trước lúc sinh, dùng đề
   mới chưa có tác vụ. Không dùng đề thật của giáo viên để thử ✓/✕.
2. Từ thư mục gốc dự án, chạy `scripts\xem-demo-poc.cmd 4183`.
   Cổng 4183 dành cho QA của chat Lý thuyết; chỉ dùng 4182 khi thực sự muốn xem app chính.
   Launcher mở Chrome `--new-window` có thanh URL và CMD đọc API. Nó không dùng `--app`.
3. Thao tác một bước trên web → xem các dòng log vừa xuất hiện → giải thích → bước tiếp theo.
   Chưa có video mới được quay bằng launcher này. Không mở nó khi Thuận đang dùng desktop.
4. Ctrl+C chỉ dừng đọc log. Đóng Chrome/CMD cũng không dừng app hoặc tác vụ đang chạy.
   Mặc định theo dõi 900 giây, có thể mở lại để đọc tiếp.

Để ghim đúng một lượt đã có, mở Terminal tại thư mục dự án rồi chạy (thay hai UUID):

```powershell
backend\.venv\Scripts\python.exe scripts\theo-doi-poc.py --port 4183 --exam-id UUID_DE --job-id UUID_JOB
```

Thêm `--once` để lấy một mẫu API rồi thoát; `--seconds 1800` để theo dõi 30 phút.
Lệnh trực tiếp đã được kiểm với stdout cp1252 và tự xuất UTF-8. Không cần nhập khóa.

## Đọc các dòng như thế nào

| Nhãn | Dữ liệu thực sự được đọc |
|---|---|
| `APP_TRACE` | Sự kiện từ API `/trace`, giữ thứ tự bằng `index` và cùng `jobId`. Chỉ xuất tên công cụ, kết quả, mã lỗi được cho phép và thời lượng nếu API cung cấp. |
| `QUAN_SAT_API` | Phiên bản đề, số câu đã lưu, số góp ý/vướng mắc, cờ bỏ đề xuất, độ dài undo/redo và việc tìm thấy job trong lịch sử lưu. Đây là mẫu trạng thái API, không phải sự kiện model. |
| `DIEN_GIAI` | Chú thích cố định của công cụ đọc log; không phải lời suy nghĩ của model hoặc log app. |

`observedAt` là thời điểm **đọc**, không phải thời điểm sự kiện model xảy ra.
`durationMs`/`seconds` chỉ xuất khi có trong log gốc; không tự dựng thời gian cho từng sự kiện.
Không cộng thời lượng các hàng kiểm vì một số hàng dùng chung lời gọi AI.

`complete` chỉ là vòng sinh hoàn tất. `savedHistoryObserved=true` nghĩa API đã có bản ghi lịch
sử mang ID job đó; không phải receipt API và không chứng minh nội dung đang còn áp dụng sau undo.
Đọc kèm `questionCount`, `revision`, `undoCount`, `redoCount` và màn hình web.
Không biến thay đổi trạng thái thành sự kiện “đã nhấn ✓/✕” tự chế.

## Phạm vi và giới hạn

- Công cụ ghim đề đầu tiên quan sát được, rồi ghim job đầu tiên thấy trong đề đó. Không tự chạy
  theo việc chuyển đề hoặc lượt sinh tiếp. Nếu đề đã có job cũ, công cụ đọc **job cũ**; mở lại
  với `--exam-id`/`--job-id` để chọn lượt khác. Khi quay lại lượt cũ phải ghi “đọc lại lượt đã chạy”.
- Các dòng có `fixture=true` là kiểm phần mềm bằng phản hồi giả lập, không chứng minh model
  thật đã tự sửa hoặc kiến thức đã đúng. Bộ kiểm đạt vẫn cần người có chuyên môn rà nội dung.
- `/trace` không chứa toàn bộ nhật ký provider. Các sự kiện đổi key/retry của Gemini hiện có
  trong file log gốc của lượt chạy, không được công cụ này tự dựng vào API trace.
- Chu kỳ đọc một giây có thể bỏ lỡ trạng thái thoáng qua hoặc thay đổi bị đảo lại ngay.
  Trace vẫn giữ thứ tự sự kiện đã lưu. Các API được đọc lần lượt, không là một snapshot giao dịch.
- Không xuất nguồn, câu hỏi, tên người rà, thông báo provider nguyên văn, config hoặc khóa.
  Chỉ chấp nhận loopback 4182/4183/4184 và không theo redirect. Không thay cho log gốc đầy đủ.
- Chrome/CMD có thanh URL đã có launcher; khả năng công cụ quay nhìn thấy cửa sổ và video
  thao tác thật còn chờ kiểm khi Thuận cho phép dùng desktop. Không dùng ảnh terminal dựng.

Kiểm mã: `backend/tests/test_poc_observer.py`. Bằng chứng lượt này nằm ở
`outputs/local-demo/kiem-ban-giao-r7/`; không đưa dữ liệu/log chạy thật lên GitHub.
