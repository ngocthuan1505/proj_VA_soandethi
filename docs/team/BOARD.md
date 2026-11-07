# Bảng tiến độ đồ án

- [Bảng kéo thả — Bảng tiến độ](https://github.com/users/ngocthuan1505/projects/1/views/1)
- [Dạng bảng — Danh sách công việc](https://github.com/users/ngocthuan1505/projects/1/views/2)
- [Điểm bắt đầu của nhóm — issue #25](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/25)

Project **Soạn đề thi — Tiến độ đồ án Python** và repo đều đang riêng tư. Bảng dùng issue gốc, không tạo bản sao công việc trên Excel: 24 task kỹ thuật #1–#24 và thêm 6 hồ sơ môn CT-01…06 (xem [link issue](../course/github-issues.json)). Mỗi người có ba gói việc kỹ thuật theo [phân công](ROLES.md): 3 UI và 5 backend; Thuận là BE-1, chỉ Thuận vận hành GreenNode. Hồ sơ CT là đầu ra chung, không thêm thành viên hoặc tính hai lần phần code.

## Nhận và thực hiện công việc

1. Chọn vai trò UI-1…UI-3 hoặc BE-1…BE-5 đã thống nhất với nhóm. Tìm mã vai trò trong ô Filter hoặc lọc nhãn `role:UI-1` tương ứng.
2. Bấm tiêu đề thẻ để xem phạm vi file, phụ thuộc, tiêu chí nghiệm thu và cách kiểm tra. Đọc hết trước khi nhận; task Bị chặn cần giải quyết phụ thuộc trước.
3. Bình luận nhận việc, gán tài khoản của mình vào Assignees khi có quyền. Mỗi người chỉ giữ một task Đang làm.
4. Kéo thẻ sang cột phù hợp hoặc sửa ô Status trong dạng bảng. Trường Status là nguồn chính về tiến độ; nhãn `status:*` của issue không tự đồng bộ, cần sửa thủ công nếu dùng các bộ lọc nhãn cũ.
5. Khi có PR, liên kết `Closes #...`, đưa thẻ sang Chờ duyệt. Chỉ đưa sang Hoàn thành sau khi đạt nghiệm thu, kiểm thử và review; kéo thẻ không thay cho việc merge PR/đóng issue.

| Cột | Khi nào dùng |
|---|---|
| Sẵn sàng | Đã rõ đầu ra và không còn phụ thuộc cần chờ |
| Đang làm | Thành viên đã nhận và đang thực hiện |
| Chờ duyệt | Có PR hoặc sản phẩm kiểm chứng được để người khác review |
| Bị chặn | Thiếu hợp đồng, đầu vào hoặc phụ thuộc; ghi rõ cách gỡ chặn |
| Hoàn thành | Đã review, kiểm thử, nghiệm thu và đóng issue/merge PR phù hợp |

Lúc khởi tạo ngày 02/11/2026: **24 task, 8 Sẵn sàng, 16 Bị chặn, 0 Hoàn thành**. Đây là ảnh chụp trạng thái ban đầu; xem số hiện tại trên bảng. Không có deadline tự đặt khi nhóm chưa chốt.

## Báo tiến độ và nhận thông báo

Mở [trang hướng dẫn báo cáo](BAO_CAO.md) để chọn form tiến độ, vướng mắc, nghiệm thu hoặc mẫu comment trong task. Issue **Nhật ký tiến độ chung** giữ link tổng hợp tuần/vòng, không thay issue task. Lọc `label:type:course` để xem hồ sơ môn, `label:type:task` để chỉ xem 24 việc kỹ thuật. Các issue báo cáo có nhãn riêng để không lẫn số task.

Thành viên chọn **Subscribe** trong issue mình cần theo dõi. Bình luận ngắn khi có tiến triển, vướng mắc hoặc cần review:

```text
Đã làm: ...
Bằng chứng: link PR / ảnh / kết quả kiểm tra ...
Đang vướng: ... (không có thì ghi không)
Bước tiếp theo: ...
```

GitHub gửi thông báo theo đăng ký và cài đặt thông báo của từng tài khoản; có thể nhắc đúng người bằng @username khi cần hỗ trợ. Chỉ kéo thẻ chưa bảo đảm mọi người nhận thông báo. Chưa cài bot gửi email/chat hoặc nhắc lịch tự động; không có phần trăm tiến độ tự suy đoán.

## Quyền của thành viên

Thuận thêm đúng username vào repo và **Project → Settings → Manage access** với quyền Write cho người cần cập nhật bảng. Quyền repo không tự cấp quyền Project riêng tư. Hiện còn thiếu username của bảy thành viên nên chưa mời/gán họ. Không chia sẻ tài khoản chủ, không mở bảng hoặc repo công khai để tránh bước cấp quyền.

## Python và quy ước nội dung

Python là ngôn ngữ chính theo môn học. FastAPI hiện mới có nền tảng health/readiness; nghiệp vụ core/auth/database/AI/tài liệu còn phải chuyển theo [kế hoạch](../architecture/PYTHON_MIGRATION.md). Chưa phải bản full Python. JavaScript vẫn hỗ trợ UI/editor và backend Node cũ còn làm tham chiếu; không sửa thống kê ngôn ngữ để che phần chưa chuyển.

Commit, tiêu đề/mô tả PR, task và hướng dẫn viết tiếng Việt. Giữ tên kỹ thuật, mã task, đường dẫn và lệnh bằng tiếng Anh khi cần. Ví dụ: `Hoàn thiện lưu đề và xử lý xung đột phiên bản`.

Không ghi URL server thật, khóa API, dữ liệu giáo viên hoặc mã mời vào bảng/issue. Thay đổi cần chạy trên GreenNode đưa qua PR và runbook để Thuận tự thực hiện.
