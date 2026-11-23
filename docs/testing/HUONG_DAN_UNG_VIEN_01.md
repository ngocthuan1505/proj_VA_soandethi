# Soạn đề thi · hướng dẫn bản ứng viên (Ứng viên 58)

## Cài và mở app

Giải nén ZIP. Trên Windows, cài [uv](https://docs.astral.sh/uv/getting-started/installation/) rồi mở một trong các tệp bên dưới. Lần đầu chạy cần Internet để `uv` cài Python 3.12 và các thư viện phụ thuộc (không cần Node/npm). Cần Chrome hoặc Edge để xuất PDF.

| Muốn thử | Tệp mở | Địa chỉ |
| --- | --- | --- |
| Soạn tại máy (tự gắn query chống cache mới nhất) | `CHAY_THU_NHOM.cmd` | `http://127.0.0.1:4182/` |
| Đăng nhập và dùng kho riêng theo tài khoản | `CHAY_NHOM_CO_TAI_KHOAN.cmd` | `http://127.0.0.1:4185/` |
| Mở app cùng CMD ghi log lượt AI mới | `CHAY_DEMO_VA_LOG.cmd` | `http://127.0.0.1:4188/` |

Chế độ tài khoản mở trang tạo quản trị viên lần đầu. Sau khi vào app, dùng **Tài khoản → Mời thành viên**. Mỗi chế độ có kho SQLite riêng trong thư mục giải nén. Giữ CMD mở khi dùng, nhấn `Ctrl+C` để dừng. Nếu cổng `4182` đã được dùng, chọn chế độ tài khoản hoặc demo có cổng riêng.

## Giao diện mới 2 hàng phẳng gọn và luồng soạn 4 bước

Ứng dụng sử dụng **giao diện sáng phẳng 2 hàng** chuẩn bàn soạn văn bản: **2 hàng đầu trang** (hàng menu + thanh định dạng gọn kèm công tắc `Đề / Đáp án`), cột **Mục lục / Mẫu đề thi** bên trái thay cho cột rail dọc cũ, tờ giấy A4 ở giữa, **chân trang 1 dòng gọn** (`Đề gốc` · `Nguồn` · `Ma trận` · `Tạo mã đề` · công tắc `Học sinh · Ẩn đáp án / Giáo viên · Hiện đáp án` · đếm `Trang / câu / từ`), và **khung Trợ lý AI** bên phải.

1. **Bước 1 — Nạp nguồn & Kho bài học mẫu đa môn (15 bộ / 31 bài):**
   - **Kéo–thả trực tiếp** tệp `.docx`, `.pdf`, `.txt`, `.md`, `.pptx` hoặc ảnh (`PNG`, `JPEG`, `WEBP`, tối đa `15 MB`) thẳng vào khung Trợ lý AI (hoặc dùng dải nhanh `+ Kho tài liệu`, `Bài SGK`, `Đề cộng đồng` ngay trên khung nhập chat) để đọc nguồn tại máy và gắn làm ngữ liệu cho đề. PDF scan hoặc ảnh chỉ gửi AI OCR sau khi thầy cô xác nhận đồng ý.
   - Hoặc bấm **`Nguồn`** ở chân trang / **`＋ Nguồn (4 kênh)`** để chọn theo 4 kênh: **`SGK / Bài học`**, **`Đề của tôi`**, **`Cộng đồng`**, **`Tệp/OCR`**. Riêng kênh **`SGK / Bài học`** có sẵn **15 bộ / 31 bài học mẫu đa môn tự biên soạn** (7 môn: Toán, Ngữ văn, Tiếng Anh, Khoa học tự nhiên, Vật lí, Hoá học, Sinh học; lớp 5, 9, 10, 11, 12), hỗ trợ tìm không dấu và trích xuất vào ngữ liệu đề. Có thể chọn **Mở ví dụ mẫu để thử nhanh** trong khung Trợ lý khi bắt đầu với đề trống.
2. **Bước 2 — Ma trận đề (`0,05`, `+ Nhánh` và cảnh báo `Lệch điểm`):**
   - Bấm **`Ma trận`** ở chân trang (hoặc **Xem → Ma trận** / **Soạn theo ma trận**). Có thể nhập `docs/testing/Ma-tran-demo-8-cau.csv` (8 câu, 4 dạng, tổng 10 điểm) hoặc tự chỉnh trực tiếp từng dòng:
     - Ô **Điểm/câu** hỗ trợ bước thập phân **`0,05`** (như `0,10`, `0,20`, `0,40`, `9,60`) hoặc để trống để tự chia phần điểm còn lại.
     - Bấm **`+ Nhánh`** / **`Đổi nhánh`** ở từng dòng để phân bổ câu theo **`Tự chọn A`** / **`Tự chọn B`** (mỗi nhánh đủ `10,00 đ`).
     - Khi bấm **`↻ Lập ma trận từ đề`** (hoặc **Lập ma trận ngược từ đề đang mở**), nếu các câu cùng chủ đề/loại/mức nhưng khác điểm hoặc thiếu thông tin, hệ thống tách dòng riêng và hiển thị cảnh báo kèm nhãn **`Lệch điểm`** / **`Cần rà`** để giáo viên kiểm lại trước khi tích **Tôi xác nhận cơ cấu này** và bấm **Lưu ma trận** / **Dùng ma trận này**.
3. **Bước 3 — Soạn, sửa, Chat tự nhiên M11, Thời gian chạy & Quản trị khóa DPAPI:**
   - Khi chọn một câu hỏi trên bàn soạn, **thanh thao tác nhanh** luôn hiển thị ngay đầu câu (gọn trên cả màn hình máy tính lẫn di động `390px`): **Chọn câu** để gửi vào phạm vi Trợ lý, mở nhanh composer công thức (**`ƒ`**), chèn ảnh, chèn bảng (hiển thị cả ảnh trong ô bảng lẫn công thức KaTeX), sửa hình học tọa độ (**`◇`**), **`Duyệt` / `Đã duyệt`**, nhân bản (**`❐`**, cấp UUID mới), di chuyển lên/xuống (**`↑` / `↓`**) và mở thuộc tính/nguồn câu (**`⚙`**).
   - **Khung Trợ lý AI tự nhiên (`M11`) & Thẻ hành động 1-chạm (`0` auto-save):** Hiển thị thẻ gợi ý theo ngữ cảnh hiện tại của đề, cho phép hỏi đáp sư phạm tự nhiên, gợi ý câu hỏi, phân tích ma trận hoặc đề xuất sửa. Mọi đề xuất thay đổi đề (như **Diff 2 cột** hoặc **Thẻ hành động 1-chạm**) **tuyệt đối không tự động ghi đè đề** — giáo viên luôn xem trước và bấm **`✓ Chấp nhận đề xuất`** để lưu, hoặc **`✕ Bỏ đề xuất`** / **`↶ Hoàn tác bước trước`** để giữ nguyên bản đang soạn.
   - **Chọn khung thời gian chạy AI (`2p / 5p / 20p / 60p`, tối đa `7200s`):** Ngay cạnh nút gửi trong khung chat có **1 dropdown thời gian** chọn nhanh 4 mức (`Nhanh 2p`, `Chuẩn 5p`, `Kỹ sâu 20p`, `Mở rộng 60p`; có thể cấu hình sâu tới tối đa `7200s` kèm checkpoint tự phục hồi trong phần Kết nối AI).
   - **Ngăn Quản trị khóa mã hóa cục bộ (Windows DPAPI):** Mở **Công cụ → Kết nối AI & tìm nguồn** (hoặc biểu tượng cài đặt AI) để cấu hình và lưu khóa mã hóa cục bộ theo từng máy Windows (không ghi plain-text ra repo/ZIP):
     - **Đa khóa Gemini (6–8 khóa):** Nhập nhiều khóa Gemini (`AIza...` hoặc `AQ....`), tự động luân phiên khóa khi gặp giới hạn `429` và tự chọn đúng endpoint tương thích.
     - **Cổng OpenAI-compatible tùy chỉnh:** Nhập **HTTPS Base URL**, **API key**, chọn model chính / dự phòng (như `deepseek-v4.1-flash`, `deepseek-v4-pro`, `qwen3.8-max`, `deepseek-chat`, `deepseek-reasoner`) kèm **trần chi phí USD** an toàn theo phiên và tổng tích lũy.
     - **AGY CLI cục bộ:** Tự phát hiện `agy.exe` trên máy và chạy trong hộp cát thư mục tạm chỉ đọc, tước hoàn toàn biến môi trường bí mật.
     - **Ollama cục bộ:** Chạy model hoàn toàn tại máy khi không dùng dịch vụ đám mây.
4. **Bước 4 — Xuất đề tách rạch Học sinh / Giáo viên & Gói khóa QR:**
   - Bấm **`Tạo mã đề`** ở chân trang hoặc nút **`Mã đề`** trên thanh đầu trang (hoặc **Tệp → Xuất Word / PDF**). Hộp thoại **Xuất đề & Mã đề** gồm:
     - **1. Đối chiếu bản in & OCR**: so ngắt trang giữa bàn soạn với A4 dự kiến và liệt kê thành phần OCR cần rà.
     - **Tạo nhiều mã đề**: chọn ≥ 2 câu cùng phần/cùng dạng/cùng ngữ liệu bảng để trộn câu hoặc phương án và xem trước mã đề.
     - **2. Tách bản Học sinh & Giáo viên**: tách riêng **Bản học sinh** (`HỌC SINH · SẠCH 100% ĐÁP ÁN`, không chứa đáp án, lời giải hay hội thoại) và **Bản giáo viên** (`GIÁO VIÊN · ĐỦ ĐÁP ÁN & BAREM`), xuất ở cả **`Word (.docx)`**, **`PDF`** và **`HTML`**.
     - **3. Đáp án/Barem, Ma trận/Đặc tả A4 & Gói khóa QR**: xuất Đáp án & Barem, Ma trận & Đặc tả (có tùy chọn **Khổ A4 ngang (landscape)**) và **`Gói khóa đáp án & QR (.zip)`** gồm `DapAn.xlsx` và `QR_DapAn.png` (`KEY|V1|...`). Lưu ý: đây là gói xuất theo chuẩn chung; **tương thích nhập trực tiếp với phần mềm chấm phiếu ngoài (như TNMaker) chưa được xác minh độc lập**.

Để ôn tập trên lớp, xuất **Bản học sinh → HTML**, mở tệp vừa tải và chọn **Trình chiếu**. Dùng nút **Câu trước / Câu sau** hoặc phím mũi tên để chuyển câu. Nếu đề có đoạn đọc hoặc bảng dữ kiện, bấm **Ngữ liệu** để xem kèm câu. Nhấn `Esc` để quay lại toàn đề. Tệp HTML hoạt động ngoại tuyến ngay cả khi đã tắt app.

Để đối chiếu khi demo Toán 5, gói có sẵn [đề mẫu đã hiệu chỉnh](docs/testing/DE_DEMO_TOAN_5.md) và [đáp án, hướng dẫn chấm](docs/testing/DAP_AN_DEMO_TOAN_5.md). Hai tệp dựa trên lượt Gemini của bản 13 và có phần rà của Codex; lượt AI trong demo sẽ sinh bộ câu mới.

## Xem log và chuyển kho

- Mỗi lần mở `CHAY_DEMO_VA_LOG.cmd`, cửa sổ dòng lệnh chờ một lượt sinh phát sinh sau dòng **Sẵn sàng**. Khi thấy `DA_LUU_JSON`, mở thư mục `JSON-demo` cạnh tệp CMD và chọn thư mục có thời điểm cùng `jobId` hiện trên màn hình. `trace.json` ghi các bước, `report.json` ghi kết quả kiểm và `result.json` ghi trạng thái. App vẫn mở để xem, chấp nhận hoặc xuất đề; chỉ nhấn `Enter` trong CMD khi muốn đóng app demo.
- Trong lượt soạn, mở **Chi tiết lượt xử lý → Nhật ký tự kiểm và sửa**. Sau lượt chạy, bấm **Tải log** để lấy JSON của đúng lượt. Mở tệp bằng Notepad hoặc VS Code, tìm `jobId`, `tool_call`, `generation_result` và `run_end`. Kết quả qua bộ kiểm và thao tác lưu đề là hai bước riêng.
- Trong thư mục app, log chi tiết của chế độ tại máy nằm dưới `outputs/team-test/data/agent-logs/<jobId>/`. Log có thể chứa nội dung đề hoặc nguồn; chỉ chia sẻ dữ liệu mẫu đã kiểm.
- Muốn chuyển kho, vào **Tệp → Tải bản sao toàn bộ** ở app nguồn. Tải thêm bản sao của kho đích nếu đang có đề cần giữ. Trong app đích chọn **Tệp → Khôi phục bản sao JSON**, kiểm tra số đề và tệp trước khi xác nhận thay kho. Có thể nhập lại bản sao đích để quay về trạng thái trước đó.

Đây là bản ứng viên cho nhóm kiểm thử. Chất lượng OCR, nội dung do AI sinh và mức tương thích với phần mềm chấm ngoài cần được giáo viên kiểm tra trực tiếp trước khi dùng chính thức.
