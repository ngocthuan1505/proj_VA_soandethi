# Soạn đề thi · hướng dẫn bản ứng viên

## Cài và mở app

Giải nén ZIP. Trên Windows, cài [uv](https://docs.astral.sh/uv/getting-started/installation/) rồi chọn tệp bên dưới. Lần đầu cần Internet để cài Python 3.12 và các thư viện. Chrome hoặc Edge được dùng để xuất PDF.

| Muốn thử | Tệp mở | Địa chỉ |
| --- | --- | --- |
| Soạn tại máy | `CHAY_THU_NHOM.cmd` | `http://127.0.0.1:4182/` |
| Đăng nhập và dùng kho riêng | `CHAY_NHOM_CO_TAI_KHOAN.cmd` | `http://127.0.0.1:4185/` |
| Mở app cùng CMD ghi log lượt mới | `CHAY_DEMO_VA_LOG.cmd` | `http://127.0.0.1:4188/` |

Chế độ tài khoản mở trang tạo quản trị viên lần đầu. Sau khi vào app, dùng **Tài khoản → Mời thành viên**. Mỗi chế độ có kho riêng trong thư mục giải nén. Giữ CMD mở khi dùng, nhấn Ctrl+C để dừng. Nếu cổng 4182 đã được dùng, chọn chế độ demo hoặc tài khoản có cổng riêng.

## Chạy demo

1. Mở `CHAY_DEMO_VA_LOG.cmd` và đợi dòng **Sẵn sàng**. Trình duyệt tự mở. Tạo đề mới. Có thể mở **Mở ví dụ Sinh học** trong khung trợ lý để thử với ngữ liệu tự viết đi kèm.
2. Mở **Soạn theo ma trận** và tải `docs/testing/Ma-tran-demo-8-cau.csv` để thử cấu trúc 8 câu, 4 dạng, tổng 10 điểm. Có thể nhập ma trận riêng. Chọn thông tin đề nếu app hỏi, rà điểm từng hàng rồi bấm **Dùng ma trận này**.
3. Nếu chạy AI thật, mở **Kết nối**, chọn kết nối đã được cấp phép và dùng ngữ liệu tự viết. Xác nhận cho phép gửi yêu cầu rồi bấm **Bắt đầu soạn**. Xem bộ câu trong đề và bấm **Chấp nhận** để lưu hoặc **Bỏ đề xuất** để giữ bản đang soạn.
4. Mở **Xuất đề** và chọn bản học sinh hoặc giáo viên. Mở tệp vừa xuất để đối chiếu công thức và đáp án. Bản học sinh không có lời giải.

Để ôn tập trên lớp, xuất **Bản học sinh → HTML**, mở tệp và chọn **Trình chiếu**. Dùng nút **Câu trước / Câu sau** hoặc phím mũi tên để đổi câu. Nếu đề có đoạn đọc hoặc bảng dữ kiện, bấm **Ngữ liệu** để mở cùng câu. Nhấn Esc để quay lại toàn đề. Tệp HTML vẫn dùng được khi đã tắt app.

Để đối chiếu khi demo Toán 5, gói có [đề mẫu đã hiệu chỉnh](docs/testing/DE_DEMO_TOAN_5.md) và [đáp án, hướng dẫn chấm](docs/testing/DAP_AN_DEMO_TOAN_5.md). Hai tệp dựa trên lượt Gemini của bản 13 và có phần rà của Codex. Lượt AI trong demo sẽ sinh bộ câu mới.

## Xem log và chuyển kho

- Mỗi lần mở CMD demo, màn hình chờ một lượt sinh phát sinh sau dòng **Sẵn sàng**. Khi thấy `DA_LUU_JSON`, mở thư mục `JSON-demo` cạnh tệp CMD và chọn thư mục có thời điểm cùng `jobId` hiện trên màn hình. `trace.json` ghi các bước, `report.json` ghi kết quả kiểm và `result.json` ghi trạng thái. App còn mở để xem, chấp nhận hoặc xuất đề. Chỉ nhấn Enter trong CMD khi muốn đóng app demo.
- Trong lượt soạn, mở **Chi tiết lượt xử lý → Nhật ký tự kiểm và sửa**. Sau lượt chạy, bấm **Tải log** để lấy JSON của đúng lượt. Mở tệp bằng Notepad hoặc VS Code, rồi tìm `jobId`, `tool_call`, `generation_result` và `run_end`. Kết quả qua bộ kiểm và thao tác lưu đề là hai bước riêng.
- Trong thư mục app, log chi tiết của chế độ tại máy nằm dưới `outputs/team-test/data/agent-logs/<jobId>/`. Log có thể chứa nội dung đề hoặc nguồn. Chỉ chia sẻ dữ liệu mẫu đã kiểm.
- Muốn chuyển kho, vào **Tệp → Tải bản sao toàn bộ** ở app nguồn. Tải thêm bản sao của kho đích nếu đang có đề cần giữ. Trong app đích chọn **Tệp → Khôi phục bản sao JSON**, đọc số đề và tệp trước khi xác nhận thay kho. Có thể nhập lại bản sao đích để quay về trạng thái trước đó.

Đây là bản ứng viên cho nhóm kiểm thử. Chất lượng OCR và nội dung do AI sinh cần được rà với dữ liệu được phép sử dụng.
