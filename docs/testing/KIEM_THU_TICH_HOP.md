# Kế hoạch nghiệm thu xuyên module

Đây là **test cần làm cho candidate Python**, không phải kết quả đã chạy. Baseline demo 05/11 ở [báo cáo riêng](BASELINE_2026_11_05.md); không chuyển nhãn PASS Node sang Python. BE-5 điều phối; từng owner cung cấp fixture/expected và một reviewer khác kiểm.

## Dữ liệu và cách ghi kết quả

- Tạo ít nhất hai owner và một guest, đề richDoc nhiều version, câu trùng text nhưng khác UUID, công thức/bảng/hình và ngữ liệu nhiều dòng.
- Nguồn synthetic có trang/slide/locator, bản sửa version, file hỏng/quá giới hạn và đoạn chứa lệnh giả. Có expected extraction, ID/checksum và quyền sử dụng.
- AI/job fixture hỗ trợ valid/invalid/schema/refusal/rate-limit/timeout/stale/quá vùng/cancel/duplicate/out-of-order/disconnect; kết nối chỉ loopback trong CI.
- Ghi mỗi ca: `ID / commit / môi trường / config / fixture / bước tái hiện / expected / actual / đạt-không đạt-chưa chạy / log hoặc ảnh / bug / reviewer / lần retest`.
- Giới hạn concurrency/size/timeout do nhóm chốt ở M1 và ghi đơn vị/config trước đo. Không tự lấy số minh họa làm SLA; server/model thật chỉ owner chạy riêng bằng dữ liệu được phép.

## 11 kịch bản bắt buộc xem xét

| Ca / UC | Fixture và hành trình | Kết quả phải chứng minh, gồm ca lỗi | Owner phối hợp / task nghiệm thu |
|---|---|---|---|
| IT-01 / UC-01 | Hai tài khoản, tạo/mở/tìm/đổi tên; guest và session hết hạn | Kho tách biệt; server từ chối đổi ID; nháp của A không sang B | UI-1/BE-2/3; UI-1-003, BE-2-003 |
| IT-02 / UC-02 | Upload nguồn hai trang/slide và file hỏng/giả đuôi/quá lớn | Nội dung/locator/version khớp expected; quyền/giới hạn đúng; cleanup lỗi | BE-4/2/3; BE-4-003, BE-2-003 |
| IT-03 / UC-03 | Cấu trúc/điểm/ma trận, preference nháp/đã xác nhận và yêu cầu mơ hồ | Đếm/điểm/routing minh bạch; chỉ preference đã duyệt được áp; hỏi lại không phá bản đề | UI-1/3, BE-1/2/3; UI-1-003, UI-3-003 |
| IT-04 / UC-04 | Tạo request→job→SSE→đề từ nguồn; thiếu consent/provider và output hỏng | Kết quả schema/nguồn/owner đúng hoặc báo thiếu; không trả thành công giả/fallback trả phí | BE-1/5/2, UI-3; BE-1-003, UI-3-003 |
| IT-05 / UC-05 | Chèn/sửa công thức, bảng/hình/ngữ liệu→lưu Python→reload→undo | RichDoc/UUID/định dạng giữ, IME và node trùng đúng; conflict không last-write-wins ngầm | UI-2/BE-3/2; UI-2-003, BE-3-003 |
| IT-06 / UC-06 | Hỏi→proposal→diff→confirm; version đổi giữa chừng, sửa quá vùng, confirm lặp | Hỏi không ghi; chỉ transaction đúng scope/version được lưu một lần; undo khôi phục cả cụm | UI-3/2, BE-1/2/3/5; UI-3-003, BE-2-003 |
| IT-07 / UC-07 | Giải/check độc lập rồi duyệt; đổi nội dung sau duyệt hoặc đáp án AI bất đồng | Tách ba trạng thái; invalidation đúng version; thiếu evidence không tự gắn đúng | BE-1/2/3, UI-3; BE-1-003, BE-2-003 |
| IT-08 / UC-08 | Đổi dữ kiện có bảng/hình/câu phụ thuộc, gây lỗi giữa transaction rồi undo | Chỉ phần liên quan cập nhật, unit/ID đúng; rollback không để nửa cũ nửa mới | BE-3/2/1, UI-2; BE-3-003, UI-2-003 |
| IT-09 / UC-09 | So sánh/chọn ngữ liệu version A/B, sửa câu, thay nguồn gốc | Giữ đoạn đã chọn/nguồn do người dùng nhập; locator lỗi hoặc version đổi phải yêu cầu xem lại | BE-3/1/4, UI-2; BE-4-003, UI-2-003 |
| IT-10 / UC-10 | Xuất teacher/student Word/PDF/HTML→mở thật→share→revoke | Không lộ answer/chat/key trong student; công thức sửa được khi hỗ trợ; owner khác/link thu hồi không đọc được | BE-4/2/3, UI-1/2; BE-4-003, BE-2-003 |
| IT-11 / UC-11 | Cancel sát commit, retry/trùng event, disconnect/offline; backup→restore bản sao | Một terminal state, không ghi muộn/lặp; snapshot/ID/checksum còn; thiếu file/rollback lỗi được phát hiện | BE-5/3/1/2, UI-3; BE-3-003, BE-5-003 |

## Kiểm bổ sung trước đề nghị phát hành

1. Tắt Node API, chạy các hành trình trên với Python thật; ghi request/route đã chuyển, không chỉ ảnh UI hoặc mock.
2. Kiểm bàn phím/focus/IME và mobile/desktop trên luồng chính; ghi viewport, trình duyệt và lỗi thực. Chưa có screen reader/usability với giáo viên thì vẫn ghi chưa kiểm.
3. Chạy trong giới hạn tài nguyên đã chốt; khi quá ngưỡng phải từ chối/hàng đợi/timeout theo contract, không treo vô hạn hoặc mất draft. Log đo là dữ liệu, chưa là SLA.
4. Chạy source chứa lệnh giả, tài nguyên sai owner và download/export qua đường dẫn trực tiếp; server vẫn enforce quyền và không lộ secret. Test red-team bằng fixture, không tấn công server thật.
5. Người khác chạy từ clone sạch bằng hướng dẫn; mở bản xuất thực và so artifact. Sai số/giới hạn Word/OCR phải ghi rõ.

## Kiểm lại IT-08 trên FastAPI

Ngày 19/11/2026, với mã bàn soạn tại `5a48a76`, Chrome desktop đã đổi dữ kiện khu vực B trong đề Địa lí mẫu từ 240 lên 300 người. Màn hình xem trước giữ kho cũ. Sau xác nhận, bảng, biểu đồ và bản HTML cùng hiện 300 người. Các câu liên quan giữ ID, tăng phiên bản và bỏ duyệt cũ. Câu ngoài phạm vi giữ nguyên. Sau tải lại, Hoàn tác khôi phục dữ kiện và câu. Một phiên khác ghi trước làm lượt xác nhận bị từ chối bằng HTTP 409 và dữ liệu mới hơn được giữ.

Trong một ca riêng, pytest gây lỗi SQLite ngay sau câu lệnh cập nhật kho. FastAPI trả HTTP 500, rồi lần đọc tiếp theo xác nhận dữ kiện, câu và revision vẫn là bản cũ. Sau khi bỏ lỗi giả lập, gửi lại cùng revision lưu thành công một lần.

Đây là kiểm trên fixture có kho riêng. Phép tính xem trước diễn ra trong trình duyệt, còn FastAPI lưu snapshot theo giao dịch và phiên bản. Chưa có người khác nghiệm thu bản cài. [Script kiểm Chrome](../../scripts/kiem-ui-du-kien.mjs) · [Kiểm rollback FastAPI](../../backend/tests/test_workspace_connection.py)

## Kết luận và mức độ lỗi

Lỗi mất dữ liệu, đọc/sửa chéo tài khoản, lộ đáp án/key, áp sai scope/version hoặc không thể tái lập luồng chính là **blocker trong phạm vi candidate**. Các lỗi khác xếp ảnh hưởng/tần suất/cách tránh trong issue, owner + reviewer chốt mức; không tự hạ severity để đóng task.

Một ca chưa chạy là chưa chạy; không đổi thành đạt vì task phụ thuộc đóng hoặc CI xanh. Nhóm ghi vòng trước/sau cho ít nhất một cải tiến sản phẩm theo CT-06 và [đề bài R8](../course/DE_BAI_GOC.md). Kết quả model thật, khảo sát và đánh giá giáo viên phải tách khỏi fixture kỹ thuật.
