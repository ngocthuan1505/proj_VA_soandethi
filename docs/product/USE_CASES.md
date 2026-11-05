# 11 use case để nhóm thống nhất phạm vi

Cập nhật 05/11/2026. Đây là **phạm vi nghiệm thu đề xuất cho app Python**, kế thừa [demo](DEMO_DA_CO.md) và [hồ sơ nhóm](../course/HO_SO_DA_CO.md); chưa phải 11 luồng đã chuyển xong. R1 của đề bài yêu cầu 8–12 use case đại diện. Chủ sản phẩm/nhóm review rồi ghi điều chỉnh, không suy từ bảng ra điểm môn đã đạt.

| Mã | Tác vụ giáo viên / điều kiện vào | Đầu ra cần thấy | Lỗi/biên phải giữ an toàn | Vai trò phối hợp / yêu cầu |
|---|---|---|---|---|
| UC-01 | Đăng nhập, tạo/mở/tìm/đổi tên/nhân bản đề trong kho riêng | Đúng owner và đề; trạng thái lưu thật | Hết phiên, kho rỗng, account khác, revision conflict | UI-1, BE-2/3; R6/R7 |
| UC-02 | Nhập DOCX/PDF/PPTX/text/ảnh hợp pháp làm nguồn, xem preview | SourceDocument có version/trang/locator, vùng không chắc để duyệt | File hỏng/giả đuôi/quá lớn, OCR sai, nguồn của user khác | BE-4/3/2, UI-2; R3/R7 |
| UC-03 | Chọn môn/lớp/cấu trúc/điểm/ma trận và preference đã xác nhận | Yêu cầu/ma trận rõ; hỏi lại khi còn thiếu, xác nhận trước sinh | Preference nháp, thiếu dữ kiện, điểm không khớp, sửa cấu trúc sau xác nhận | UI-1/3, BE-1/2/3; R1/R2/R5 |
| UC-04 | Sinh đề từ yêu cầu và nguồn được chọn bằng AI đã cấu hình | Job theo dõi được, câu/nguồn/đáp án ở trạng thái cần giáo viên duyệt | Thiếu provider/consent/nguồn, output sai schema, timeout/rate-limit, không fallback trả phí ngầm | UI-3, BE-1/5/2; R3/R4/R5/R6 |
| UC-05 | Soạn tay, chèn/sửa công thức đa môn, bảng/hình/ngữ liệu; lưu/mở/undo | RichDoc/UUID/định dạng giữ được, không bắt nhớ LaTeX | Node trùng text, IME, câu dài/bảng qua trang, lưu thất bại | UI-2, BE-3/2/4; R2/R6/R7 |
| UC-06 | Bôi đen hoặc chỉ định câu, hỏi rồi đề xuất sửa, xem diff và confirm | Hỏi không đổi đề; chỉ sửa scope/version đã duyệt, undo cả transaction | Stale, quá vùng, confirm lặp, lỗi giữa apply, response muộn | UI-3/2, BE-1/2/3/5; R2/R5/R7 |
| UC-07 | Kiểm/giải độc lập đáp án, rà phần bị ảnh hưởng và giáo viên duyệt | Tách verificationStatus/approvalStatus/draftStatus; lưu bằng chứng/giới hạn | AI bất đồng, thiếu căn cứ, đổi nội dung sau duyệt, bài chưa hỗ trợ | BE-1/2/3, UI-3; R2/R3/R4/R7 |
| UC-08 | Đổi dữ kiện có liên kết bảng/hình/phép tính và rà các câu bị ảnh hưởng | Liên kết theo ID, đề/lời giải/barem không mâu thuẫn, undo khôi phục cụm | Xóa nguồn dữ kiện, unit sai/thiếu, thay một phần bị lỗi | BE-3/2/1, UI-2; R2/R3/R7 |
| UC-09 | Chọn/so sánh phiên bản ngữ liệu, giữ tác giả/nguồn do người dùng cung cấp | Version/locator rõ, đoạn đã chọn không đổi ngầm khi sửa câu | Trích dẫn không tìm được, thiếu quyền/bản quyền, nguồn đổi version | BE-3/1/4, UI-2; R3/R5/R7 |
| UC-10 | Xuất Word/PDF/HTML bản học sinh/giáo viên, chia sẻ snapshot và thu hồi | Nội dung/bản in đúng; snapshot cố định, bản học sinh không lộ đáp án/chat | File khác owner, export lỗi, link bị thu hồi, chart/shape không giữ | BE-4/2/3, UI-1/2; R3/R6/R7 |
| UC-11 | Dừng/retry/reconnect job, offline/lưu lại, backup/restore workspace | Không ghi kết quả muộn/lặp, khôi phục đúng ID/revision, không mất bản trước | Cancel sát commit, crash giữa migration, backup thiếu file, vượt giới hạn cấu hình | BE-5/3/2/1, UI-3; R2/R5/R7/R8 |

## Giới hạn phạm vi

- Giữ luồng kế thừa của demo theo fixture trước khi đổi hành vi. UC-08/09 không là bộ giải mọi môn hoặc công cụ tự gán trích dẫn; phần không được kiểm chứng phải báo cần duyệt.
- Chưa có đồng biên tập thời gian thực, thanh toán, marketplace, chấm thi tự động, huấn luyện model hoặc bao trọn mọi bộ sách. Không thêm vector DB/framework/model mới chỉ để đủ mục trong bảng.
- Mẫu đa môn/485 mục không có nghĩa AI đã được đánh giá toàn chương trình; không dùng HTTP 200 hoặc dấu xanh làm bằng chứng đúng tuyệt đối.
- Tài khoản/email recovery trước khi mở đăng ký rộng và hạ tầng thật theo quyết định owner; không tự mua dịch vụ hoặc dùng server thay thành viên.

## Truy vết tới task và test

Mỗi task có `detail.useCases`/`detail.requirements`, bước Wxx và ca Txx trong [backlog kỹ thuật](../team/BACKLOG.md) hoặc [backlog hồ sơ](../course/BACKLOG_CT.md). [Kế hoạch test tích hợp](../testing/KIEM_THU_TICH_HOP.md) kiểm hành trình xuyên module. Chưa thấy đủ khảo sát giáo viên/benchmark thật thì giữ mục đó pending theo CT-01/06, không tự hoàn thành từ bảng này.
