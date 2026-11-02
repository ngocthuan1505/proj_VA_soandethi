# Phạm vi bản ứng dụng nhóm sẽ hoàn thiện

**Yêu cầu môn học: Python là ngôn ngữ chính cho core/backend. JavaScript chỉ hỗ trợ UI/build/test, không dùng một Python facade để giữ core Node.**

Mục tiêu: giáo viên tạo, sửa, lưu và xuất đề nhiều môn nhanh hơn, kiểm soát được AI và không cần nhớ LaTeX. Source hiện tại là MVP sử dụng được; các task nhằm hoàn thiện và kiểm chứng, không coi toàn bộ hành vi hiện có đã đạt chất lượng production.

## Luồng bắt buộc

1. Đăng nhập, mở kho đề riêng, tạo/chọn mẫu và đặt môn/lớp/thời gian.
2. Nhập nguồn hoặc ma trận; xem trước nội dung trích xuất, không tự gửi sang AI.
3. Soạn trực tiếp với công thức trực quan, bảng, hình; lưu và undo giữ định dạng.
4. Hỏi hoặc sửa đúng ngữ cảnh; xem diff, xác nhận, hủy khi cần; không sửa ngoài vùng chọn.
5. Lời giải/barem có phiên bản; giáo viên duyệt, không xem lời AI là đáp án đã xác thực.
6. Xuất bản học sinh/giáo viên Word/PDF, phân quyền tệp, chia sẻ snapshot có thu hồi.

## Điều kiện phát hành thử

- Chạy luồng chính với Python API và không khởi động Node API; pytest bao phủ nghiệp vụ/auth/DB/jobs/document mới.

- Hai tài khoản không đọc/sửa đề, file hoặc export riêng của nhau; vai trò thường không đổi cấu hình AI.
- Tải lại/mất mạng/trùng phiên không mất nội dung đã lưu hoặc ghi đè im lặng; lỗi báo cách khôi phục.
- End-to-end tạo → sửa vùng → hủy/undo → lưu → xuất vượt qua kiểm tra với dữ liệu giả.
- Các câu hỏi dài/công thức/bảng hoạt động ở desktop, mobile, phím/tab và trạng thái loading/error.
- Import có giới hạn dung lượng/loại tệp; export không lộ đáp án trong bản học sinh.
- DB có diễn tập backup/restore trên bản sao; migration có rollback và không chạy tự động trên dữ liệu thật.
- Test AI chạy fixture trong CI; test model thật chỉ do Thuận chạy riêng trên dữ liệu cho phép, ghi hạn chế chất lượng.

## Chưa làm trong đợt này

Thanh toán, chấm thi tự động, đồng biên tập thời gian thực, marketplace đề, huấn luyện model và viết lại toàn bộ bằng framework mới chưa nằm trong phạm vi. Hệ thống tài khoản thật cần xác minh email/khôi phục mật khẩu trước khi mở đăng ký rộng; task BE-2 sẽ thiết kế, không sử dụng email provider trả phí nếu chưa được duyệt.

Không đặt deadline giả định: nhóm chốt ngày thực tế cho ba milestone sau buổi kickoff. Mốc phụ thuộc nghiệm thu, không phải lời hứa số ngày phát triển.
