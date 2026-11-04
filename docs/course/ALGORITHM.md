# Thuật toán kiểm và áp dụng đề xuất sửa — thiết kế cần review

Nguồn: Topic 5 trang 8, 18–23, 26–35, 43. BE-2 + BE-5 điều phối, BE-1/3 review. Pseudocode dưới là **thiết kế**, chưa phải chức năng đã migrate trong FastAPI.

## Hợp đồng đề xuất

Input: user đã xác thực, đề hiện tại, job có owner/revision gốc, phạm vi câu/khối cho phép, đề xuất có giới hạn kích thước. Output: preview hợp lệ, hoặc lỗi có mã rõ; chỉ ghi khi người dùng xác nhận, có kiểm lại revision và transaction. DTO/tên lỗi thật chốt trong [CONTRACTS](CONTRACTS.md).

```text
KIEM_DE_XUAT(user, exam, job, proposal, limits)
  nếu không có quyền đọc/sửa exam hoặc job không thuộc user: từ chối
  nếu job bị hủy/hết hạn hoặc proposal không khớp job: từ chối
  nếu revision hiện tại khác revision gốc: trả xung đột, không ghi
  nếu proposal quá giới hạn hoặc sai schema: trả lỗi, không ghi
  kiểm tất cả ID đích tồn tại và nằm trong phạm vi cho phép
  áp thử vào bản sao; kiểm richDoc/công thức/tổng điểm theo contract
  so sánh phần ngoài phạm vi với bản gốc
  nếu có thay đổi ngoài phạm vi: từ chối
  trả preview cùng revision gốc, chưa ghi exam

XAC_NHAN(user, preview)
  mở transaction; đọc lại quyền và revision hiện tại
  nếu không còn hợp lệ hoặc job đã hủy: rollback và trả lỗi
  ghi phiên bản mới và thông tin nguồn theo hợp đồng; commit
```

AI sinh proposal là bước có thể sai và timeout; không để model quyết định quyền ghi. Tất cả vòng lặp chỉ duyệt input đã giới hạn; retry model có số lần/timeout hữu hạn trong contract. Không dùng lặp vô hạn “đến khi kết quả đúng”.

## Dry run thiết kế — chưa phải log test chạy

| Ca | Input khác biệt | Nhánh dự kiến | DB được đổi? |
|---|---|---|---|
| A | Revision 4, sửa Q2, owner đúng | Preview → consent → kiểm lại revision 4 | Chỉ sau consent; Q1/Q3 giữ nguyên |
| B | Đề lên revision 5 trong lúc chờ | Xung đột version | Không |
| C | Proposal sửa cả Q3 dù chỉ cho Q2 | Ngoài phạm vi | Không |
| D | Cancel trước kết quả tới | Job bị hủy | Không |
| E | Hai lần xác nhận cùng preview | Theo idempotency/revision đã chốt | Không tạo hai phiên bản ngoài ý muốn |

BE-5 chuyển các dòng thành pytest và contract/UI test; ghi kết quả thật vào [bằng chứng](../reports/README.md). Không gọi bảng dự kiến này là test đã pass.

## Phân tích và tối ưu cần chứng minh

Nếu dựng map ID một lần và duyệt nội dung một lần, phần kiểm định hướng O(n + m) với n là kích thước đề và m là proposal; độ phức tạp chính xác còn tùy biểu diễn richDoc và phép so sánh. Giữ/so sánh bản sao có chi phí bộ nhớ theo n. Đây là phân tích thiết kế, chưa có benchmark. Đo trên fixture đề ngắn/dài; ghi giới hạn input và thời gian/memory thật trước tối ưu. Không bỏ validation hay transaction để đổi lấy tốc độ.

Flowchart thực tế và trace theo implementation là đầu ra CT-05; PR phải chỉ được nhánh lỗi nào đã kiểm và khác pseudocode ở đâu.
