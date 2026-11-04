# Mô hình và hợp đồng cần chốt

Trạng thái: bản chuẩn bị review, chưa phải OpenAPI/DB đã triển khai. Nguồn phương pháp: Topic 3 trang 18; Topic 4 trang 22–24, 30–34. BE-3 giữ [đề xuất dữ liệu](../architecture/DATA_PLAN.md); BE-2 giữ OpenAPI của FastAPI. Bảng dưới chỉ giúp nhóm không bỏ sót thông tin trước khi đặt DTO/schema cụ thể.

| Khái niệm | Thông tin cần thống nhất | Bất biến cần kiểm |
|---|---|---|
| Đề/phiên bản | UUID, owner, revision, nội dung richDoc, môn/lớp, điểm | ID và công thức không đổi khi round-trip; quyền theo tài khoản; quy tắc tăng revision rõ |
| Phạm vi sửa | ID câu/khối, revision gốc, đoạn chọn và giới hạn | Không diễn giải mơ hồ “câu này”; không sửa ngoài danh sách cho phép |
| Job AI | ID, owner, trạng thái enum, revision gốc, timeout, nguồn model | Kết quả đúng job/version; cancel không áp output muộn; fixture khác model thật |
| Tài liệu/nguồn | ID, owner, MIME/size, trang, trạng thái OCR, nguồn được phép | File quá lớn/hỏng bị từ chối; không dùng text OCR như dữ kiện đã được duyệt |
| Bản xuất | đề/version, chế độ học sinh/giáo viên, owner, định dạng | Bản học sinh không chứa đáp án; quyền download kiểm phía server |

Mỗi field trong schema thật cần tên, kiểu, bắt buộc/null, đơn vị hoặc format, giới hạn, ví dụ hợp lệ/lỗi. Đặc biệt điểm dùng biểu diễn chính xác theo ADR; thời lượng ghi đơn vị; timestamp thống nhất múi giờ/format; enum job dùng cùng một tập giá trị giữa UI/API/DB.

## Mẫu hợp đồng cho từng hàm hoặc route

```text
Tên/phiên bản:
Người sở hữu + người dùng hợp đồng:
Input (field/type/unit/required/limits):
Output thành công:
Lỗi có thể trả + status/code:
Quy tắc quyền/revision/idempotency:
Ví dụ input → output:
Ca rỗng / biên / sai quyền / stale:
Fixture và test chứng minh:
```

BE-2/3 cùng UI-1/2/3 và BE-1/4/5 duyệt tên trường trước các PR triển khai song song. Không lấy ví dụ JSON của AI làm hợp đồng thật mà chưa chạy test. Đọc API hiện tại để lập golden fixture; không đổi UUID/revision/richDoc chỉ vì chọn Python.

Phần giữ/defer/bỏ phải có lý do liên quan mục tiêu: giữ công thức/owner/revision vì ảnh hưởng kết quả; defer đồng biên tập vì ngoài MVP; bỏ dữ liệu cá nhân không cần thiết khỏi fixture. Đây là áp dụng abstraction, không phải che kiểm quyền hoặc lỗi khỏi người dùng.
