# Thuật toán kiểm và áp dụng đề xuất sửa — thiết kế cần review

Nguồn: Topic 5 trang 8, 18–23, 26–35, 43. BE-2 + BE-5 điều phối, BE-1/3 review. Giả mã dưới ghi thiết kế ban đầu. Mục đối chiếu cuối trang dẫn các nhánh đã chạy trên FastAPI.

Nhóm đã có giả mã `ISourceReader` và pre/postconditions/invariants của `ProposeReplaceQuestion`/`ConfirmProposal` trong Abstraction. Kế thừa chúng theo [hồ sơ đã có](HO_SO_DA_CO.md), rồi bổ sung thuật toán nghiệp vụ, trace và test vào Python. Không ghi nhận giả mã Interface là đã nghiệm thu toàn bộ CT-05.

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

## Đối chiếu triển khai Python trên ứng viên 16

Commit `8eba276` có hai đường sửa. [Sửa vùng trong bàn soạn](../../backend/src/mach_backend/poc_scoped_patch.py) kiểm đồng ý dùng AI, revision đề và ID, phiên bản, vị trí UTF-16 của vùng. Sau khi kiểm đề xuất và rà lời giải, server kiểm lại snapshot và tạo bản xem trước. Một giao dịch SQLite khi xác nhận kiểm hash snapshot rồi ghi câu, phiên bản, lịch sử hoàn tác và biên nhận. Gửi lại cùng mã xác nhận trả cùng biên nhận. [Luồng lời giải có Job/SSE](../../backend/src/mach_backend/patch_confirmation.py) còn kiểm lại owner và phiên bản nguồn cùng hợp đồng trạng thái job.

| Nhánh | Điều kiện trước | Kết quả quan sát | Ca kiểm |
| --- | --- | --- | --- |
| Xem trước rồi xác nhận | Đề và phạm vi trùng bản đã đọc | Xem trước giữ đề nguyên. Xác nhận lần hai dùng cùng biên nhận. | `test_edit_is_preview_only_and_review_is_blind`, `test_scoped_confirmation_is_transactional_and_replay_safe` |
| Đề đổi sau xem trước | Bản đang lưu khác hash trong đề xuất | Từ chối, giữ bản hiện tại. | `test_scoped_confirmation_rejects_change_without_version_bump` |
| Chạm câu hoặc chữ ngoài vùng | Chỉ một vùng được phép sửa | Từ chối trước khi ghi. | `test_blocks_unselected_question_and_partial_text_escape` |
| Đóng kết nối khi model đang đợi | Lượt sửa giữ khóa xử lý | Hủy chờ, nhả khóa, giữ đề nguyên. | `test_disconnecting_patch_cancels_the_model_and_releases_workspace` |
| Ghi biên nhận lỗi | Giao dịch đang cập nhật câu và lịch sử | Rollback. | `test_scoped_confirmation_is_transactional_and_replay_safe` |

Chạy từ `backend/` bằng `uv run pytest tests/test_poc_scoped_patch.py tests/test_patch_confirmation.py`. Trên ứng viên 16 có 64 ca đạt và hai ca yêu cầu model thật được bỏ qua trong lượt kiểm fixture.

Với `q` câu và `k` vùng chọn, bước dò danh sách câu hiện cần tối đa O(k·q) lượt so ID. Mỗi lần tạo hash snapshot đọc O(n) byte đầu vào đã tuần tự hóa. Ghép richDoc và suy luận có chi phí riêng. Lượt này chưa đo hiệu năng trên bộ đề dài. Nếu vùng trộn chữ và công thức yêu cầu thay nhiều công thức hoặc xóa công thức, bàn soạn có thể dùng bộ ghép trình duyệt. Luồng model có giới hạn thời gian và số lượt gọi. Trường hợp nhiều lượt rà đồng ý vẫn cần người rà nội dung chuyên môn.
