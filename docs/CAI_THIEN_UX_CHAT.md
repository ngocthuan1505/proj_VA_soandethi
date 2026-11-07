# Rà soát và cải thiện trải nghiệm Soạn đề thi — 19/10/2026

## Vấn đề đã đo

Trên viewport 1366×768, khung trợ lý cao 632 px nhưng hội thoại chỉ còn 90 px. Ô soạn, nguồn và tùy chọn chiếm 374 px; thư viện/dãy môn và tiêu đề chiếm thêm 166 px. Ở 844×390, ô soạn tràn khỏi đáy trợ lý/cửa sổ. Ngoài ra có lệch vị trí panel ở breakpoint trung gian, chat ẩn trong chế độ Tập trung, cuộn tự dịch khi có phản hồi và trang A4 bị cắt ngang ở mức 100%.

## Thay đổi

- Hội thoại laptop 1366×768 tăng từ **90 lên 357 px**, gần **4 lần**. Ô soạn giảm từ **374 xuống 178 px**. Đây là số đo trên tài liệu/chat kiểm thử cùng nội dung, không phải cam kết mọi màn hình đều đúng các kích thước đó.
- Gỡ dãy môn lặp khỏi vùng cố định. Vẫn chọn đủ các môn trong thư viện qua một nút; ba học liệu tên dài nằm trong một hàng cuộn. Không nguồn thì không chiếm một khối trống.
- Chuyển tùy chọn AI, tự đồng bộ, kết nối và xóa chat vào bảng cài đặt có nhãn. Giữ đúng lựa chọn đang có, không bật/tắt AI ngầm.
- Giới hạn chiều cao ô nhập; Enter gửi, Shift+Enter xuống dòng, giữ Ctrl+Enter và chặn Enter khi còn gõ IME.
- Mở ở tin mới nhất. Đọc tin cũ không bị kéo xuống; có nút về cuối/báo tin mới. Loại bỏ cuộn mượt/neo cuộn gây dịch vị trí khi thay nội dung.
- Có mở rộng/thu gọn chat và Esc; điện thoại dùng toàn chiều ngang/chiều cao; theo visual viewport để bố trí lại khi bàn phím thay vùng nhìn. Đã thử các viewport nhỏ, chưa dùng điện thoại thật với mọi bàn phím Android/iOS.
- Sửa breakpoint ẩn/hiện 900 px, mở trợ lý từ Tập trung, đóng mục lục overlay. Không che nút gửi ở cửa sổ thấp.
- Trang đề mặc định Vừa ngang, vẫn chọn lại 100%/mức khác. Nút Đề/Đáp án có nhóm riêng, không chồng lên công cụ định dạng. Hàng định dạng vẫn cuộn ngang khi không đủ chỗ.
- Hộp thoại dài có vùng nội dung cuộn riêng; kiểm tra được nút lưu cuối màn hình thấp. Popup giới hạn trong viewport.

## Kiểm chứng

- `kiem_thu_Node_UX.txt`: **94/94** kiểm tra Node.
- `kiem_thu_UX_chat.json`: **13/13** ca UX mới.
- `kiem_thu_chon_sua_chat.json`: **9/9** ca chọn vùng, patch, rich text và chat.
- `kiem_thu_workbench_UX.json`: **13/13** ca soạn, sửa, lịch sử, offline, tài khoản và khôi phục.
- `kiem_thu_Studio_UI.json`: **11/11** ca editor, hình, nhập Word, công thức và mobile.
- `kiem_thu_Mach_UI_6.0.json`: **12/12** ca thư viện đa môn, MathLive, bảng, phím tắt và mobile; cập nhật thao tác chọn môn theo nút thư viện mới.

Tổng **58 luồng trình duyệt**, không có lỗi JavaScript ghi nhận. Dữ liệu kiểm thử dùng kho riêng và câu trả lời AI fixture cục bộ; không lấy nội dung đề cá nhân để gọi AI. Phạm vi QA là các luồng/màn hình được nêu, chưa phải nghiên cứu có giáo viên tham gia hoặc kiểm định tiếp cận đầy đủ.

Ảnh: `Mach_Chat_thoang.png`, `Mach_Chat_dien_thoai.png`; số đo trước/sau: `kiem_tra_UX_truoc.json`, `kiem_tra_UX_sau.json`.

## Áp dụng

Bản local hiện tại đã phục vụ module/CSS mới, HTTP 200. Không khởi động lại server và không sửa khóa/tuyến AI, đề đã lưu hoặc cơ sở dữ liệu người dùng. Tải lại trang đang mở bằng Ctrl+F5; shortcut Desktop tiếp tục gọi cùng thư mục app. Không công khai ứng dụng lên Internet.
