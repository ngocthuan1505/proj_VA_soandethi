# Soạn đề thi · hướng dẫn bản ứng viên (Ứng viên 59)

## Cài và mở app

Giải nén ZIP. Trên Windows, cài [uv](https://docs.astral.sh/uv/getting-started/installation/) rồi mở một trong các tệp bên dưới. Lần đầu chạy cần Internet để `uv` cài Python 3.12 và các thư viện phụ thuộc (không cần Node/npm). Cần Chrome hoặc Edge để xuất PDF.

| Muốn thử | Tệp mở | Địa chỉ |
| --- | --- | --- |
| Soạn tại máy (tự gắn query chống cache mới nhất) | `CHAY_THU_NHOM.cmd` | `http://127.0.0.1:4182/` |
| Đăng nhập và dùng kho riêng theo tài khoản | `CHAY_NHOM_CO_TAI_KHOAN.cmd` | `http://127.0.0.1:4185/` |
| Mở app cùng CMD ghi log lượt AI mới | `CHAY_DEMO_VA_LOG.cmd` | `http://127.0.0.1:4188/` |

Chế độ tài khoản mở trang tạo quản trị viên lần đầu. Sau khi vào app, dùng **Tài khoản → Mời thành viên**. Mỗi chế độ có kho SQLite riêng trong thư mục giải nén. Giữ CMD mở khi dùng, nhấn `Ctrl+C` để dừng. Nếu cổng `4182` đã được dùng, chọn chế độ tài khoản hoặc demo có cổng riêng.

## Giao diện 2 hàng phẳng gọn, 4 bước soạn đề & Bộ công cụ VIP (Ứng viên 59)

Ứng dụng sử dụng **giao diện sáng phẳng 2 hàng** chuẩn bàn soạn văn bản: **2 hàng đầu trang** (hàng menu + thanh định dạng gọn kèm công tắc `Đề / Đáp án`), cột **Mục lục / Mẫu đề thi** bên trái (**hỗ trợ kéo–thả để đổi thứ tự câu hỏi** + `Ctrl+Z` hoàn tác, kèm 2 nút gọn `ƒ Công thức & mẫu` và `＋ Thêm câu hỏi`), tờ giấy A4 ở giữa, **chân trang 1 dòng gọn** (`Đề gốc` · `Nguồn` · `Ma trận` · `Tạo mã đề` · **`Ngân hàng`** · **`Phân tích`** · công tắc `Học sinh · Ẩn đáp án / Giáo viên · Hiện đáp án` · đếm `Trang / câu / từ`), và **khung Trợ lý AI** bên phải (kèm chip **`· Trí nhớ`** ngay cạnh tiêu đề).

1. **Bước 1 — Nạp nguồn & Kho bài học mẫu đa môn (15 bộ / 31 bài):**
   - **Kéo–thả trực tiếp** tệp `.docx`, `.pdf`, `.txt`, `.md`, `.pptx` hoặc ảnh (`PNG`, `JPEG`, `WEBP`, tối đa `15 MB`) thẳng vào khung Trợ lý AI, hoặc dùng dải nhanh **`+ Kho tài liệu`**, **`Bài SGK`** (mở thẳng kho Bộ sách / Chương / Bài SGK), **`Đề cộng đồng`** ngay trên khung nhập chat. PDF scan hoặc ảnh chỉ gửi AI OCR sau khi thầy cô xác nhận đồng ý.
   - Hoặc bấm **`Nguồn`** ở chân trang / **`＋ Nguồn (4 kênh)`** để chọn theo 4 kênh: **`SGK / Bài học`** (**15 bộ / 31 bài học mẫu tự biên soạn** thuộc 7 môn: Toán, Ngữ văn, Tiếng Anh, Khoa học tự nhiên, Vật lí, Hoá học, Sinh học), **`Đề của tôi`**, **`Cộng đồng`**, **`Tệp/OCR`**.
2. **Bước 2 — Ma trận đề (`0,05`, `+ Nhánh` và cảnh báo `Lệch điểm`):**
   - Bấm **`Ma trận`** ở chân trang (hoặc **Xem → Ma trận**). Hỗ trợ nhập `docs/testing/Ma-tran-demo-8-cau.csv`, nhập điểm thập phân bước **`0,05`** (`0,10`, `0,40`, `9,60`…), bấm **`+ Nhánh`** / **`Đổi nhánh`** cho `Tự chọn A / B`, và lập ma trận ngược **`↻ Lập ma trận từ đề`** kèm cảnh báo **`Lệch điểm`** / **`Cần rà`** trước khi xác nhận.
3. **Bước 3 — Soạn, kéo–thả mục lục, Ngân hàng câu hỏi, Phân tích đề & Chat M11 siêu nhanh:**
   - **Kéo–thả Mục lục trái:** Kéo trực tiếp từng câu hỏi ở cột **Mục lục** bên trái để sắp xếp lại thứ tự câu trên đề, giữ nguyên UUID câu và hỗ trợ hoàn tác `Ctrl+Z`.
   - **Thanh thao tác nhanh từng câu & Ngân hàng câu hỏi thông minh (`★`):** Chọn một câu để hiện thanh thao tác nhanh (chọn phạm vi AI, công thức `ƒ`, ảnh, bảng có ảnh & KaTeX, hình học `◇`, `Duyệt`, nhân bản `❐`, lên/xuống, thuộc tính `⚙`, và **`★` Lưu vào Ngân hàng câu hỏi**). Bấm **`Ngân hàng`** ở chân trang (hoặc `Ctrl+K` → Ngân hàng câu hỏi) để lưu cả đề (`★ Lưu cả đề vào kho`), tìm kiếm không dấu tiếng Việt, lọc theo Môn / Lớp / Dạng / Mức độ và bấm **`＋ Chèn vào đề`** (cấp mới UUID, hỗ trợ `Ctrl+Z`).
   - **Phân tích chất lượng & Ma trận đề (`Phân tích`):** Bấm **`Phân tích`** ở chân trang (hoặc **Công cụ → Phân tích chất lượng đề** / `Ctrl+K`) để xem **Điểm sẵn sàng (`/100`)**, tổng điểm, ước lượng thời lượng làm bài, số câu đã duyệt, biểu đồ **4 mức độ nhận thức (`NB / TH / VD / VDC`)**, phân bố đáp án trắc nghiệm **`A / B / C / D`** (cảnh báo lệch đáp án hoặc lặp liên tiếp), phát hiện câu gần trùng lặp và **bấm cảnh báo để nhảy thẳng tới đúng câu cần sửa**.
   - **Khung Trợ lý AI tự nhiên (`M11`) siêu nhanh & UX nâng cấp:**
     - Tự động tối ưu định tuyến chat nhanh cho chế độ `Nhanh (2p)` / `Chuẩn (5p)`, hiển thị **huy hiệu nguồn AI + thời gian phản hồi** (ví dụ `DeepSeek · 4,5s`) và nút **`Sao chép`** trên từng câu trả lời.
     - Khi chưa bật cho phép gửi AI, thẻ xác nhận **Cho phép và gửi ngay** tự cuộn rõ trong khung nhìn và nhắc trực quan nếu bấm gửi lại — không im lặng.
     - Mọi đề xuất thay đổi đề (**Diff 2 cột** hoặc **Thẻ hành động 1-chạm** đưa câu hỏi đề xuất vào đề) **tuyệt đối không tự động ghi đè đề** — giáo viên luôn chủ động xác nhận và có thể hoàn tác.
     - Chip **`· Trí nhớ`** ngay cạnh tiêu đề Trợ lý mở nhanh các nguyên tắc ra đề thầy cô đã xác nhận; dropdown thời gian chạy AI (`2p / 5p / 20p / 60p`, tối đa `7200s`) và ngăn **Quản trị khóa mã hóa cục bộ (Windows DPAPI)** hỗ trợ đa khóa Gemini (`AIza`/`AQ.`), cổng OpenAI-compatible tùy chỉnh kèm trần chi phí USD, AGY CLI cục bộ và Ollama.
4. **Bước 4 — Xuất đề tách rạch Học sinh / Giáo viên, Gói khóa QR & Phiếu OMR Bộ GD&ĐT 2025:**
   - Bấm **`Tạo mã đề`** ở chân trang hoặc nút **`Mã đề`** trên thanh đầu trang (hoặc **Tệp → Xuất Word / PDF**). Hộp thoại **Xuất đề & Mã đề** gồm 4 mục:
     - **1. Đối chiếu bản in & OCR**: so ngắt trang giữa bàn soạn với A4 dự kiến và liệt kê thành phần OCR cần rà.
     - **Tạo nhiều mã đề**: chọn ≥ 2 câu độc lập để trộn câu/phương án và xem trước mã đề.
     - **2. Tách bản Học sinh & Giáo viên**: tách riêng **Bản học sinh** (`HỌC SINH · SẠCH 100% ĐÁP ÁN`) và **Bản giáo viên** (`GIÁO VIÊN · ĐỦ ĐÁP ÁN & BAREM`) ở cả **`Word (.docx)`**, **`PDF`** và **`HTML`**.
     - **3. Đáp án/Barem, Ma trận/Đặc tả A4 & Gói khóa QR**: xuất Đáp án & Barem, Ma trận & Đặc tả (có tùy chọn **Khổ A4 ngang**) và **`Gói khóa đáp án & QR (.zip)`** chuẩn chung `KEY|V1|...` *(tương thích trực tiếp app chấm phiếu ngoài như TNMaker chưa được xác minh độc lập)*.
     - **4. Phiếu trả lời trắc nghiệm OMR (Bộ GD&ĐT 2025):** xuất **`Phiếu OMR Học sinh (A4)`** (`0` rò đáp án, đủ khung Số báo danh 6 cột, Mã đề 3 cột, Phần I Trắc nghiệm, Phần II Đúng–Sai, Phần III Trả lời ngắn), **`Phiếu OMR Học sinh (PDF)`** và **`Phiếu OMR Đáp án GV`** (tô sẵn đáp án đối chiếu).

Để ôn tập trên lớp, xuất **Bản học sinh → HTML**, mở tệp vừa tải và chọn **Trình chiếu**. Dùng nút **Câu trước / Câu sau** hoặc phím mũi tên để chuyển câu. Nhấn `Esc` để quay lại toàn đề. Tệp HTML hoạt động ngoại tuyến ngay cả khi đã tắt app.

Để đối chiếu khi demo Toán 5, gói có sẵn [đề mẫu đã hiệu chỉnh](docs/testing/DE_DEMO_TOAN_5.md) và [đáp án, hướng dẫn chấm](docs/testing/DAP_AN_DEMO_TOAN_5.md).

## Xem log và chuyển kho

- Mỗi lần mở `CHAY_DEMO_VA_LOG.cmd`, cửa sổ dòng lệnh chờ một lượt sinh phát sinh sau dòng **Sẵn sàng**. Khi thấy `DA_LUU_JSON`, mở thư mục `JSON-demo` cạnh tệp CMD để xem `trace.json`, `report.json`, `result.json`.
- Trong lượt soạn, mở **Chi tiết lượt xử lý → Nhật ký tự kiểm và sửa** và bấm **Tải log** để lấy JSON của đúng lượt.
- Muốn chuyển kho (bao gồm cả Ngân hàng câu hỏi), vào **Tệp → Tải bản sao toàn bộ** ở app nguồn rồi **Tệp → Khôi phục bản sao JSON** ở app đích.

Đây là bản ứng viên cho nhóm kiểm thử. Chất lượng OCR, nội dung do AI sinh và mức tương thích với phần mềm chấm ngoài cần được giáo viên kiểm tra trực tiếp trước khi dùng chính thức.
