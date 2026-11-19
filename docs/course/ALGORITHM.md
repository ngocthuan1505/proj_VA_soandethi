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

## Vòng tự sửa câu khi sinh theo ma trận

Phần này mô tả đường sinh đề hỗn hợp qua Ollama trên FastAPI. Đầu vào gồm ô ma trận theo thứ tự, nguồn được phép dùng, revision gốc và ngân sách lượt gọi. Đầu ra là bản xem trước đã qua bộ kiểm hoặc trạng thái dừng. Mỗi báo cáo dùng `ordinal` đếm từ 0. Ví dụ, `ordinal: 1` là câu thứ hai. [Vòng công cụ](../../backend/src/mach_backend/matrix_agent.py) · [Bộ nối Ollama](../../backend/src/mach_backend/workspace_agent.py)

```text
Gọi model với ma trận và nguồn đã duyệt
Lặp trong ngân sách
  Nếu lượt trước định vị được lỗi ở một phần bộ câu
    Gửi các vị trí cần sửa, nội dung cần tránh lặp và báo cáo lỗi
    Kèm tối đa bốn lỗi đã thấy gần đây ở chính những vị trí đó
    Nhận đúng số câu thay thế theo thứ tự vị trí
    Ghép vào bản nháp trước theo vị trí
  Nếu chưa có bản nháp hoặc lỗi chưa khoanh được theo câu
    Yêu cầu model nộp đủ bộ
  Kiểm lại toàn bộ bản đã ghép
  Nếu đạt và model gọi finish_exam
    Trả bản xem trước để giáo viên quyết định
  Nếu không đạt
    Gửi báo cáo lỗi cho lượt kế tiếp
Dừng khi hết thời gian, hết lượt gọi hoặc bị hủy
```

**Bất biến.** Thứ tự, chủ đề, mức yêu cầu và điểm lấy từ ma trận đã duyệt. Ở lượt sửa theo vị trí, Python giữ nội dung mọi câu ngoài phạm vi và kiểm lại cả bộ sau khi ghép. Bộ rà nhận câu hỏi và nguồn mà không thấy đáp án hoặc nhãn mức của bản sinh. Bản đang lưu chỉ thay đổi ở bước xác nhận riêng có kiểm revision.

### Dry run từ câu trùng đã quan sát

Mẫu Toán lớp 5 dùng ngữ liệu tự viết, gồm năm câu thuộc bốn dạng. Ở lượt Qwen3 trên commit `1fadef7`, vòng sửa nộp hai câu rồi nộp một câu. Câu số 2 sau khi thay hỏi lại số sách truyện giống câu thứ nhất. Lỗi cấu trúc chặn bản nháp trước khi gọi bộ giải.

| Bước | Đầu vào | Kết quả đã kiểm |
| --- | --- | --- |
| Model nộp phần sửa | Vị trí `[1]`, một câu thay thế | Python ghép đủ năm câu và giữ bốn câu ngoài phạm vi. |
| Kiểm cấu trúc | Hai thân câu giống nhau sau chuẩn hóa | Bộ kiểm báo `duplicate_question`. Log của `1fadef7` chỉ mô tả số câu trong lời nhắn. |
| Phát lại trên ứng viên 39 | Chính bản nháp có câu trùng ở bước trước | Commit `6ea407e` trả thêm `ordinal: 1`. Yêu cầu sửa tiếp chỉ chứa vị trí `[1]`. |
| Kết thúc lượt Qwen3 gốc | Hết thời gian khi đang rà lần nộp thứ năm | Revision giữ ở 1. Số câu ghi vào đề bằng 0. |

Với `n` câu, `e` phát hiện và `k` vị trí cần sửa, bước chọn vị trí và ghép bản nháp cần O(e + k log k + n) thao tác trên danh sách. Chi phí sao chép hoặc tuần tự hóa dữ liệu tỷ lệ theo kích thước nội dung. Bước so trùng thân câu hiện duyệt các câu trước đó nên có thể tốn O(n²) phép so sánh. Công đoạn rà cả đề và thời gian model được tính riêng. Chính sách mặc định đặt tối đa 24 lượt gọi model và 900 giây. [Ngân sách chạy](../../backend/src/mach_backend/poc_policy.py)

Tái hiện các bất biến bằng phản hồi mẫu trong `backend/`.

```powershell
uv run pytest -q tests/test_mixed_questions.py tests/test_workspace_agent.py tests/test_poc_trace.py
```

Đối chiếu log tải từ app bằng hướng dẫn [theo dõi và kiểm log PoC](../testing/THEO_DOI_LOG_POC.md). Bộ đọc log ghép lại bản đầy đủ trước khi so sánh, vì một phản hồi ngắn hơn có thể chứa nguyên câu cũ. Kết quả phát lại mới chỉ chứng minh khả năng định vị lỗi. Chất lượng đề cuối cần một lượt model thật đi qua toàn bộ bộ kiểm và một lượt rà sư phạm độc lập.
