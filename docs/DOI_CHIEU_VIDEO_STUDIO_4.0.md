# Đối chiếu video và nghiệm thu Studio 4.0

Ngày: 18/10/2026. Bản chạy: http://127.0.0.1:4173/. Báo cáo này thay thế đánh giá 3.0 về giao diện và các phần được sửa trong 4.0.

## Những gì đã xem và thay đổi

Đã xem lại contact sheet và các khung hình riêng của ba clip Bandicam: 18:41:28 (khoảng 2:09), 18:44:33 (khoảng 5:31), 18:51:28 (khoảng 2:45), ngày 16/10/2026. Bảng dưới ghi chức năng quan sát được; không suy ra các dịch vụ ẩn hoặc khả năng của tài khoản soandethi.com.

| Quan sát trong video | Bản 4.0 | Bằng chứng |
|---|---|---|
| Bố cục menu, toolbar, mục lục, trang giấy, trợ lý | Dàn lại tỷ lệ ba cột, nền, thước, kiểu chữ, bong bóng chat và ô nhập | Studio_Final_Giao_dien.png |
| Hỏi thông tin → đề xuất Có/Không → ghi đề và khóa sửa | Giữ pipeline SSE, ghi từng bài, cập nhật mục lục, một lần undo | 13 luồng workbench UI |
| Bảng chấm ba cột và nội dung dài | Trang A4 có số, chia bảng theo hàng và lặp tiêu đề; nhãn bài gộp trong từng trang | Studio_Final_Barem.png, Studio UI |
| Sửa trực tiếp trong đáp án, không chỉ đề bài | TipTap riêng cho lời giải, phương án và bước chấm; lưu định dạng/công thức | Studio UI: sửa, lưu, tải lại, Ctrl+Z |
| Bôi đen và gắn yêu cầu vào AI | Chọn cả lời giải/barem, chip ngữ cảnh đúng trường; UUID và giới hạn phạm vi | Node + cả hai bộ UI |
| Popup công thức (clip 18:51:28, khoảng 01:36) | Đúng editor/vùng chọn, giữ mở khi cuộn và phân trang, trực tiếp xem KaTeX | Studio_Cong_thuc_barem.png |
| Menu Chèn (clip 18:44:33, khoảng 00:08) | Math, hóa học, bảng lưới, ảnh, hình, đầu đề, câu hỏi, liên kết, trang/đường kẻ | Studio UI chèn bảng thật 3×2 |
| Mức suy luận (clip 18:51:28, khoảng 00:24) | Giữ ba mức với thanh trượt; thay chỉ dẫn độ chi tiết theo adapter | UI và cấu hình AI |
| Đính kèm đề Word có toán và hình | Đọc OMML, ảnh nhúng, tách bài/điểm; mở thành đề riêng để sửa tiếp | Studio UI tải DOCX thật rồi nhập lại |
| Hình toán trong đề | SVG từ solver, chỉnh tọa độ và kéo điểm; điểm phụ thuộc tự dựng lại | Studio_Final_Hinh_hoc.png, Studio_Sua_hinh.png |
| Làm việc qua chat | Render công thức/đậm/danh sách, giữ vị trí khi đọc tin cũ, nút Dừng AI | Studio UI |

## Những phần được nâng thêm

- Tìm/thay thế xuyên đề, phương án, lời giải và bước chấm; hoàn tác một giao dịch.
- Kéo điểm tự do trong popup hình; kiểm ràng buộc tam giác và cập nhật chân cao/tâm/trực tâm.
- Hủy soạn AI giữ nguyên đề gốc, mở khóa, hoàn điểm; chặn sửa xung đột khi AI đang viết.
- Gộp các lần gõ cùng trường; chỉ dựng editor đáp án khi gần vùng đang xem; gộp các yêu cầu lưu chờ để tránh ghi liên tục snapshot cũ.
- Nhúng phông KaTeX trong HTML/PDF: bản xuất độc lập giữ dấu khác, hệ và các glyph riêng. Lỗi thiếu phông trong quá trình kiểm đã được sửa và thêm regression test.
- Giữ định dạng lời giải/barem trong bản xuất; giữ tỷ lệ ảnh khi đưa vào Word; chặn dùng richDoc cũ khi nội dung chuỗi đã đổi.

## Kết quả kiểm tra

| Bộ kiểm tra | Kết quả | Phạm vi |
|---|---|---|
| Node | 67/67 đạt | Logic/phiên bản/vùng chọn/hình/điểm, backend, OCR thật, xuất file, adapter AI fixture, rich field, OMML, phông KaTeX |
| Workbench UI | 13/13 đạt, không pageerror | SSE, khóa, undo/redo, patch retry/diff, công thức, share/revoke, kho đề, offline, auto-answer, tách tài khoản, phục hồi mất tab |
| Studio UI | 11/11 đạt, không pageerror | A4/đủ hàng chấm, sửa barem/lời giải, popup công thức, selection chip, bảng lưới, tìm/thay, kéo điểm, chat toán, hủy/hoàn điểm, DOCX ảnh+toán, mobile |
| Qwen3:8b thật | Thành công, 6,541 giây | Đổi số 11→13 đúng vùng; lời giải thành x=5, barem cập nhật; bài khác giữ nguyên; undo phục hồi |
| Đầu ra mẫu | 2 DOCX + 2 PDF | Tách học sinh/giáo viên; đã render PDF bằng Chromium và Poppler để xem hình/ký hiệu; Word kiểm OOXML và nhập ngược |

Hai bộ UI dùng **fixture AI ghi nhãn**, không chứng minh chất lượng sinh đề của mô hình. Lần Qwen thật dùng dữ liệu Toán tự soạn trong workspace kiểm thử, không chỉnh đề người dùng. Thao tác GreenNode chỉ dùng hàng đợi dự án `/network-volume/ProJ_VA/soande_ai`.

Báo cáo máy: `kiem_thu_Node_4.0.txt`, `kiem_thu_workbench_UI_4.0.json`, `kiem_thu_Studio_UI.json`, `kiem_thu_Studio_AI_that.json`. Các báo cáo AI thật bản 3.0 là bằng chứng lịch sử riêng, không tính là phép kiểm mới của 4.0.

## Giới hạn còn lại

Không tuyên bố giống từng pixel hoặc toàn bộ dịch vụ soandethi.com. Bản này phục vụ MVP cục bộ; chưa có cộng tác trực tuyến, auth/email/cloud sync hoặc thanh toán thật. Link chia sẻ loopback chỉ dùng trên máy chạy app. Các adapter Gemini/Claude/GPT có sẵn nhưng tài khoản/quota trả phí chưa kiểm thật.

Editor chia theo câu/dòng bảng, chưa chia một câu hoặc một hàng cực dài qua nhiều trang như Google Docs. Word/PDF dùng bộ dàn trang riêng. DOCX hỗ trợ các cấu trúc toán phổ biến và ảnh nhúng, chưa hoàn hảo mọi shape/chart/trường của Word; chưa xem trong Microsoft Word/LibreOffice. PDF/ảnh scan vẫn cần rà OCR, chưa có mô hình OCR công thức chuyên dụng. Kiểm đại số/hình chỉ bao phủ các dạng triển khai, không chứng nhận mọi đề AI hoặc mọi môn đúng chương trình.

## Cách thử nhanh

1. Tải lại app. Mẫu đề thi → **Tuyển sinh 10 · Đề hoàn chỉnh**. Một đề riêng được mở, đề cũ vẫn trong kho.
2. Bấm Đáp án, gõ trực tiếp vào lời giải/barem. Bấm một công thức để sửa; thử Ctrl+Z.
3. Bôi đen nội dung → Hỏi AI → nhập yêu cầu → xem diff → áp dụng.
4. Đưa chuột lên hình → Sửa hình → kéo đỉnh A → Lưu.
5. Tệp → nhập Word → tách câu → Mở thành đề mới. Xuất bản học sinh/giáo viên và đối chiếu.

Gói mới: `Tro-ly-soan-de-Studio-4.0.zip`. Không chứa dữ liệu tài khoản, khóa API, `.data`, `.runtime`, node_modules hoặc tệp người dùng.
