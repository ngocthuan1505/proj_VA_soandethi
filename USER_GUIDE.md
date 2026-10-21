# Mạch 6.0 — Bàn soạn thông minh

Ứng dụng hỗ trợ chạy cục bộ và chế độ online có đăng nhập/phân quyền. Cấu hình triển khai tại [deploy/README.md](deploy/README.md); bản clone không kèm dữ liệu hay kết nối server của chủ dự án.

Ứng dụng tiếng Việt chạy tại máy: **http://127.0.0.1:4173/**. Mở `START-DEMO.cmd` và giữ cửa sổ server mở. Sau khi khởi động lại máy cần mở launcher một lần. Đề và dữ liệu cũ được giữ trong kho.

Trên Windows, sau khi cài phụ thuộc có thể mở `START-DEMO.cmd` hoặc `OPEN-MACH.ps1`. Shortcut của máy chủ dự án không đi kèm repo.

## Công cụ theo môn, không cần nhớ mã

Bấm **Chèn nội dung theo môn** ở cột trái hoặc **Thư viện theo môn** trong trợ lý. Có thể dùng ngay từ trang trống.

- **Toán:** phân số, căn bậc hai/bậc n, lũy thừa, hệ 2–3 phương trình: chọn hình mẫu và điền ô. Công thức phức tạp có MathLive để sửa trực tiếp bằng con trỏ/bàn phím ký hiệu. Mã LaTeX được thu gọn trong **Nâng cao**.
- **Vật lí:** vận tốc, Newton, Ohm, công suất, động năng, bước sóng; có chú giải đại lượng, đơn vị và điều kiện. Đây là mẫu để soạn, không phải bộ tự giải mọi bài.
- **Hoá học:** điền chất tham gia/sản phẩm/điều kiện; chất, ion, phản ứng thuận nghịch, mol/nồng độ. Phản ứng đơn giản có đối chiếu số nguyên tử hai vế; không tự cân bằng mọi phản ứng hoặc kiểm mọi điện tích.
- **Sinh học:** ADN, nguyên phân, phép lai và bảng Punnett chỉnh sửa được.
- **Ngữ văn:** nhập ngữ liệu/thơ, giữ dòng, tác giả và nguồn do thầy cô cung cấp; khung câu hỏi đọc hiểu/dàn ý. Không tự gán nguồn/tác giả.
- **Tiếng Anh:** đoạn đọc, điền từ và câu hỏi chỉnh sửa được. Không tự khẳng định đáp án từ một mẫu chưa được duyệt.

Thư viện 6.0 có **485 mục trong 19 nhóm môn**: 429 biểu thức/công cụ ký hiệu và 56 mẫu văn bản/bảng. Chọn **Môn học → Lớp gợi ý (1–12) → Chủ đề → Loại mẫu**. Có tìm không dấu, tìm tất cả môn và tùy chọn gồm kiến thức lớp trước. Danh sách hiện 30 mục mỗi lượt để tránh tải hàng trăm biểu thức cùng lúc.

Ngoài sáu môn nhanh, bộ chọn mở Khoa học/KHTN tích hợp Lý–Hóa–Sinh, Địa lí, Tin học, Công nghệ, Kinh tế & tài chính, Lịch sử, Đạo đức/GDCD, Âm nhạc, Mĩ thuật, Giáo dục thể chất, GDQP & an ninh, Ngoại ngữ khác và Trải nghiệm/hướng nghiệp. Tiếng Việt tiểu học nằm trong Ngữ văn. Môn ít dùng công thức có khung nội dung, không coi đó là công thức toán học.

Ma trận, định thức, hàm từng khoảng, giới hạn, đạo hàm, tích phân, tổng/tích, chỉ số, đồng vị và đơn vị có ô nhập. Công thức có tên, ghi chú và gợi ý điều kiện; MathLive cho phép sửa tự do, không bắt buộc nhớ LaTeX. Nội dung chèn là công thức/bảng/văn bản thật, giữ qua tải lại và hoàn tác; Ctrl+Enter hoặc Ctrl+S lưu lần chèn. Mẫu, bộ nhập và phông chạy cục bộ, không cần API AI. Bản xuất Word giữ ký hiệu mới bằng OMML chỉnh sửa được.

**Phạm vi:** đây là thư viện khởi tạo rộng cho lớp 1–12, không phải chứng nhận đã bao trọn mọi công thức, mọi bộ sách hay mọi chuyên đề nâng cao. Lớp là gợi ý theo chủ đề, không thay thế phân phối chương trình. Các công cụ ký hiệu dùng được mọi lớp không có nghĩa là nội dung đó bắt buộc học ở mọi lớp. Chi tiết và danh mục: `THU_VIEN_LOP_1_12_6.0.md` đi kèm.


## Giao diện riêng

Nhận diện Mạch: thanh điều hướng bên trái, cột cấu trúc dạng thẻ, bàn giấy trung tâm và trợ lý màu xanh trầm. Nút **Tập trung** mở rộng bàn soạn; **Ctrl+K** tìm công cụ. Tạo đề mới có lựa chọn sáu môn và vẫn nhập được môn khác. Giữ định dạng trang đề trung tính để in.

Cơ sở và đánh giá thiết kế: xem [tài liệu](docs/NGHIEN_CUU_UI_UX_MACH_5.0.md) đi kèm. Đây là nghiên cứu tài liệu + walkthrough/kiểm tra kỹ thuật, chưa phải thử nghiệm có giáo viên tham gia hoặc chứng nhận WCAG.

## Sửa bằng chat và vùng bôi đen — cập nhật 19/10/2026

Bôi đen chữ trong đề, lời giải, phương án hoặc bước chấm rồi bấm **Hỏi AI**. Chat hiện rõ **Bài → phần → bước/mục → đoạn được chọn**. Không cần bôi đen nếu ghi rõ “Viết lại đề bài 2 cho rõ hơn”, “Sửa lời giải bài 1” hoặc “Kiểm tra đáp án cả đề”. Khi gỡ chip, app bỏ ngữ cảnh thật; chọn lại vùng hoặc ghi số bài để sửa tiếp.

Bộ chọn **Khi gửi** có **Tự hiểu yêu cầu**, **Chỉ hỏi / giải thích**, **Đề xuất sửa**. Chế độ Chỉ hỏi giữ nguyên tài liệu. Luồng sửa dùng bản đề hiện tại và tối đa sáu tin nhắn gần đây để hiểu yêu cầu tiếp nối như “câu khác khó hơn”, “sửa vào đi”. Phạm vi vẫn được kiểm tra độc lập, không lấy lịch sử làm quyền sửa bài khác.

Đề xuất có xem trước, áp dụng theo một lần và hoàn tác cả lần sửa. App chặn chữ/ô ngoài vùng, giữ định dạng và công thức ngoài đoạn thay, chặn vùng đã đổi thay vì mở rộng ngầm. Khi lỗi, yêu cầu chat được giữ lại. Tự cập nhật đáp án chỉ chạy khi được bật; đề cũ đã bật vẫn giữ lựa chọn đó.

Với thay đổi cắt ngang cấu trúc bảng không thể bảo toàn, app giữ nguyên đề và yêu cầu chọn riêng ô/đoạn nhỏ hơn. Chưa hỗ trợ một vùng bôi đen kéo qua hai editor khác nhau. Chi tiết kiểm thử: [tài liệu](docs/CAI_THIEN_CHON_SUA_CHAT.md) trong gói.

## Chat và bàn soạn gọn hơn — cập nhật 19/10/2026

Hội thoại được ưu tiên chiều cao; nguồn trống được thu gọn và mẫu theo môn mở qua một nút **Thư viện mẫu theo môn**. Cài đặt gửi AI/tự đồng bộ, kết nối và xóa hội thoại nằm trong nút **Cài đặt trò chuyện** (☷) trên đầu trợ lý. Không đổi lựa chọn AI đang bật/tắt của đề cũ.

Ô nhập tự cao theo nội dung, tối đa khoảng 5 dòng; **Enter** gửi, **Shift+Enter** xuống dòng; **Ctrl+Enter** vẫn dùng được. Enter trong lúc gõ IME không gửi nhầm. Mở chat ở tin mới nhất; cuộn lên đọc tin cũ giữ nguyên vị trí, có nút **Có tin mới / Cuối hội thoại**. Nút ⤢ mở rộng chat và Esc thu lại. Điện thoại mở chat toàn màn hình, có nút × trở lại đề.

Trang đề mặc định **Vừa ngang** theo diện tích bàn soạn; chọn 100% hoặc mức khác để phóng to/pan khi cần. Nút **Đề / Đáp án** tách khỏi dãy công cụ cuộn ngang. Hộp thoại dài giữ tiêu đề và cho phần giữa cuộn; mở trợ lý từ Tập trung và ẩn/hiện ở màn hình trung gian đã được sửa.

## Các chức năng MVP đã giữ

TipTap/KaTeX/mhchem, trang A4 và bảng chấm phân trang; sửa trực tiếp đề/đáp án/barem; hình dựng theo ràng buộc/kéo điểm; AI hỏi tối đa một lượt → cấu trúc Có/Không → SSE từng bài/khóa sửa; patch UUID/vùng chọn/phiên bản/diff/retry/undo; dừng AI và hoàn điểm; tự cập nhật đáp án có bật/tắt/cho phép; kho đề, tài khoản cục bộ, chia sẻ snapshot; SQLite và bản lưu khi offline; nhập DOCX/PDF/PPTX/ảnh, OCR; Word OMML và PDF/HTML nhúng phông.

Sinh/Sửa/Kiểm có cấu hình riêng cho GreenNode, Ollama, API tương thích, Gemini, Claude, GPT. Người chạy tự chọn mô hình/kết nối trong màn hình Kết nối AI. Chỉ dùng thư mục dự án `/network-volume/ProJ_VA/soande_ai`. Không dùng key từng gửi trong chat. API key nhập trong màn hình Kết nối và chỉ giữ trong bộ nhớ phiên server; không tự fallback sang dịch vụ trả phí.

## Chạy và kiểm tra

Máy khác: Node.js 24+, Chrome/Edge → trong thư mục app: `npm ci`, `npm start`. Editor, KaTeX, MathLive và OCR assets có trong gói; không kèm dữ liệu, node_modules, runtime hoặc trọng số. MathLive 0.111.1 được vendored từ npm chính thức, giữ LICENSE.txt; chỉ tải module khi mở bộ nhập.

- `npm test` — bộ kiểm tra Node.
- `node tests/usability-browser.mjs` — 13 luồng trải nghiệm chat, cuộn, phím tắt, cài đặt, viewport và modal; AI fixture.
- `node tests/selection-browser.mjs` — 9 luồng chọn vùng/sửa/chat/hoàn tác, AI fixture.
- `node tests/workbench-browser.mjs` — 13 luồng cũ, AI fixture.
- `node tests/studio-browser.mjs` — 11 luồng editor/Word/hình, AI fixture.
- `node tests/curriculum-browser.mjs` — 13 luồng thư viện lớp 1–12, không gọi AI.
- `node tests/authoring-browser.mjs` — 12 luồng nhập trực quan/sáu môn/UI, không gọi AI.

## Giới hạn

Mẫu soạn đa môn không có nghĩa đã đánh giá chất lượng AI trên toàn bộ chương trình. Giáo viên cần duyệt nội dung, điều kiện và barem. Kiểm nguyên tố Hóa chỉ hỗ trợ công thức đơn giản; chưa giải phản ứng oxi hóa–khử hoặc dựng cấu trúc phân tử. Mẫu Lý/Sinh không có bộ giải hoặc mô phỏng chuyên môn tổng quát. Ngữ liệu bản quyền do người dùng quản lý.

MVP có chế độ online và tài khoản riêng; chưa có đồng biên tập thời gian thực, email hoặc thanh toán thật. Link loopback chỉ dùng trên máy đang chạy app. Trang editor chia theo câu/dòng bảng, một block cực dài có thể làm trang dài ra; Word/PDF tự dàn trang riêng. DOCX chưa chuyển hoàn hảo mọi chart/shape và chưa kiểm trực quan bằng Microsoft Word. OCR ảnh chưa có mô hình nhận dạng công thức chuyên dụng.

