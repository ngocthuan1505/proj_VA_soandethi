# Điểm bắt đầu chung cho nghiên cứu và thực hành

Cập nhật: 04/11/2026. Thuận chia hai chat trong cùng dự án: một bên nghiên cứu, hồ sơ môn và thuyết trình; một bên xây app. Cả hai dùng thư mục dự án hiện tại và các file này làm bản bàn giao chung. Không tạo bản ứng dụng riêng cho từng chat.

## Đọc khi bắt đầu mỗi lượt làm việc

1. Đọc file này và hai bản bàn giao ngắn: [Lý thuyết](LY_THUYET.md), [Thực hành](THUC_HANH.md).
2. Chỉ mở tài liệu gốc liên quan tới việc sắp làm. Không mặc định đọc lại toàn bộ chat bên kia; chỉ tra một đoạn cụ thể khi bản bàn giao chưa đủ hoặc bằng chứng mâu thuẫn.
3. Sau một thay đổi có ý nghĩa, cập nhật bản bàn giao của mảng vừa làm trước khi kết thúc lượt: kết quả, đường dẫn/bằng chứng, điều ảnh hưởng bên kia, việc còn thiếu. Ghi ngày và phân biệt đề xuất với quyết định đã chốt. Không ghi đè phần của bên kia nếu chưa kiểm chứng.

Đây là quy ước đọc/ghi file, không phải đồng bộ toàn bộ lịch sử hay trí nhớ tự động giữa hai chat. File phải được lưu thì bên kia mới thấy. Không gửi prompt qua lại, tạo lịch chạy hoặc gọi AI nền chỉ để giữ liên kết.

## Phân vai

| Mảng | Nơi cập nhật | Trách nhiệm |
|---|---|---|
| Lý thuyết, research, hồ sơ môn, thuyết trình | [LY_THUYET.md](LY_THUYET.md) | Nguồn, thiết kế đã chốt, phản hồi giảng viên, slide/notes, yêu cầu cần chứng minh bằng code |
| Thực hành, UI/backend/database, tích hợp và kiểm thử | [THUC_HANH.md](THUC_HANH.md) | Hành vi thực sự đã triển khai, commit/test, giới hạn và bằng chứng đưa vào báo cáo |
| Công việc thành viên và tiến độ nhóm | [Bảng GitHub](https://github.com/users/ngocthuan1505/projects/1/views/1), [nhật ký #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32) | Status, người nhận, phụ thuộc, vướng mắc và nghiệm thu; không lấy ghi chú chat thay trạng thái đã kiểm trên bảng |

## Những điều cả hai bên phải giữ

- **Python là ngôn ngữ chính.** Backend/core/auth/database/jobs/AI validation mới đặt trong `backend/`. JavaScript hỗ trợ trình duyệt/editor/build; Node API hiện tại là legacy. [Kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md).
- **Thiết kế đã có phải được kế thừa:** proposal/baseline, Decomposition–Pattern 23 trang, Abstraction với UML/Schema/ADT/Interface. [Bằng chứng và phần còn thiếu](../course/HO_SO_DA_CO.md), [yêu cầu đồ án](../course/DE_BAI_GOC.md).
- Thiết kế/slide mô tả đích đến; code và test mới chứng minh đã triển khai. Không viết báo cáo rằng tính năng đã chuyển Python, chạy AI thật hoặc đạt số đo nếu chưa có bằng chứng.
- Giữ ID/phiên bản/phạm vi sửa, công thức và rich document. Đề xuất AI phải được xác nhận trước khi lưu. Không gộp trạng thái kiểm tra hệ thống, duyệt câu của giáo viên và trạng thái cả đề.
- Nhóm 3 UI + 5 backend, Thuận là BE-1; chưa biết đủ username thì không tự gán danh tính. [Phân vai](../team/ROLES.md). Nhóm 8 người cần lưu xác nhận của giảng viên theo đề bài, không tự bỏ thành viên.
- Chỉ Thuận thao tác GreenNode. Không đưa khóa, server URL thật, tài liệu giáo viên hoặc toàn bộ hội thoại vào GitHub. Repo giữ Private.
- Thay đổi ảnh hưởng cả hai mảng: ghi tác động trong bản bàn giao, dẫn issue/PR; khi chưa thống nhất thì ghi rõ đang đề xuất, không tự sửa slide hoặc schema/code để che khác biệt.

## Tránh mất thay đổi khi hai chat cùng làm

Trước khi sửa, đọc file hiện tại và kiểm tra Git. Mỗi bên ưu tiên bản bàn giao của mình; sửa file dùng chung phải phối hợp qua issue theo [quy tắc nhóm](../team/README.md). Không reset/clean/stash hoặc chép cả thư mục đè lên thay đổi của bên kia. Nếu phải dùng clone tạm, ghi rõ clone đó, chuyển bằng commit/PR rồi cập nhật thư mục chung an toàn; không để hai bản được coi là nguồn chính.

Quy ước file chỉ dẫn dựa trên [OpenAI Docs về AGENTS.md và context](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex). Bản bàn giao là cách làm của dự án, không phải tính năng tự hợp nhất chat của Codex.
