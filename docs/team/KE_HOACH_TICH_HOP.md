# Cách nhận task, bàn giao và qua từng mốc

Cập nhật 05/11/2026. 24 task kỹ thuật + 6 hồ sơ môn giữ ID/issue hiện có; **150 bước Wxx và 90 ca Txx là kế hoạch**, không phải 150 issue mới hoặc test đã đạt. [Task kỹ thuật](BACKLOG.md), [task hồ sơ](../course/BACKLOG_CT.md), [11 use case](../product/USE_CASES.md), [test tích hợp](../testing/KIEM_THU_TICH_HOP.md).

## Cá nhân hoặc nhóm bắt đầu như thế nào?

Chọn sau nghiên cứu theo [menu định hướng](CHON_VIEC.md), không gán chuyên môn theo thứ tự danh sách. Có thể nhiều người cùng nhận, chia Wxx/PR và chọn đầu mối bàn giao.

1. Đọc hướng dẫn demo và task theo mảng tự chọn, xem phần đã có để kế thừa. Chọn một Wxx nhỏ, ghi vào comment nhận việc; giữ một việc đang làm mỗi người.
2. Kiểm `Điều kiện bắt đầu`, dependency và contract. Có thể làm mock/fixture khi implementation chưa sẵn sàng, nhưng phải ghi chưa tích hợp. Không dùng mock để đóng nghiệm thu E2E.
3. Hẹn người giữ file dùng chung trong issue. Bước hơn khoảng một ngày thì tạo issue con ghi cha/Wxx, người/nhóm tự đăng ký, đầu ra, dependency và expected test; thêm lên Project. Không chia sẵn hàng trăm thẻ rỗng.
4. PR nhỏ theo bước, dẫn `task/Wxx` và `task/Txx`, giải thích phần kế thừa/phần mới, chạy kiểm phù hợp. Đường dẫn artifact “đề xuất” là đầu ra sẽ tạo trong PR, không phải tài liệu đã tồn tại.
5. Bên nhận bàn giao xác nhận dùng được contract/fixture; reviewer kiểm acceptance và bằng chứng. Chờ duyệt khác Hoàn thành. [Cách báo cáo](BAO_CAO.md).

## Các hợp đồng phải ghép khớp

Tên Cxx là mã bàn giao, **không phải API/schema đã implement**. Owner đề xuất đường dẫn/version ở task 001, consumer review; không tự thêm framework để chia quyền sở hữu.

| Mã | Artifact phải chốt | Owner / consumer | Tối thiểu phải có |
|---|---|---|---|
| C01 | HTTP/auth/permission/error | BE-2 → UI-1/3, BE-1/3/4/5 | Route/DTO, role/owner/session, lỗi, Origin/CSRF theo transport, ví dụ valid/invalid |
| C02 | Exam/richDoc/version/repository | BE-3 + BE-2 → UI-2/3, BE-1/4/5 | UUID khác thứ tự, revision/transaction, node/formula/figure, migration/rollback; ba trạng thái kiểm/duyệt/đề |
| C03 | SourceDocument/retrieval/evidence | BE-4 + BE-1 + BE-3 → UI-2/3, BE-2 | Owner/version/trang/locator, nội dung không chắc, query/selection, link về đoạn nguồn; file là dữ liệu, không chỉ dẫn |
| C04 | Job/SSE/cancel/retry/recovery | BE-5 + BE-1 → UI-3, BE-2/3 | JobId/owner/baseVersion, event order/dedupe, terminal state, timeout/concurrency đã chốt, không commit muộn |
| C05 | Proposal/confirm/scope/undo | BE-2 + BE-1 + BE-3 → UI-2/3, BE-5 | Base version/scope/edits/evidence, preview khác commit, atomic apply, invalidation và confirm lặp |
| C06 | Import/export/share/file lifecycle | BE-4 + BE-2 → UI-1/2, BE-3/5 | Định dạng/giới hạn, teacher/student, auth download, snapshot/revoke, cleanup và kiểm bản in |
| C07 | Preference/dataset/quote liên kết | BE-3 + BE-2 + BE-1 → UI-1/2/3 | Xác nhận preference, stable IDs/unit/nguồn, phần phụ thuộc, version ngữ liệu và tác động khi sửa |

Hợp đồng chưa chốt ghi rõ `Đề xuất`; khi đổi phải báo consumer, version/fixture và cách tương thích. Không sửa UI/backend/slide theo ba định nghĩa khác nhau của cùng field.

## Gates theo bằng chứng, chưa có deadline thật

### M1 — Sẵn sàng ghép các phần

- [ ] Tám task 001 có artifact/consumer review; C01–C07 đủ ví dụ, lỗi và quyết định/giả định còn mở.
- [ ] Baseline demo/source/fixture tái lập; source kế thừa và Python đích được phân biệt.
- [ ] CT-01/02/03 dùng lại proposal/decomposition/abstraction; thiếu khảo sát/đồng bộ slide ghi pending riêng, không bịa để vượt gate.
- [ ] Chọn PoC phần rủi ro, dataset/threshold chốt trước chạy; khóa scope/non-goals và ngưỡng tài nguyên test.
- [ ] Không còn mâu thuẫn contract chặn lát chức năng định triển khai. Chưa đủ thì có thể thử prototype có giới hạn, không gọi toàn M1 đã nghiệm thu.

### M2 — Luồng chính chạy qua Python

- [ ] Auth/ownership → repo/đề/version → source/document → AI/job/proposal → export được nối theo lát có pytest/contract.
- [ ] UI thực gọi Python, giữ richDoc/UUID/revision và hành vi golden. Bảng route còn Node/mock/đã chuyển được công khai trong PR.
- [ ] Scope/stale/confirm trùng/cancel/quyền/file có negative test; source có locator và không trở thành lệnh hệ thống.
- [ ] PoC/thuật toán có kết quả theo commit; model thật pending thì không tính phần đó đã đạt.
- [ ] Integration plan có expected/actual; bug blocker và rollback không bị che bằng CI xanh.

### M3 — Candidate review được và gói nộp tái lập

- [ ] Các task 003 có người khác review; **BE-5-003 chờ BE-1-003** cho bằng chứng AI thật, không lấy fixture thay thế.
- [ ] Chạy các luồng chính khi Node API tắt; clean clone, quyền, restore, Word/PDF, mobile/keyboard có bằng chứng hoặc pending công khai.
- [ ] R1–R8 và CT-01…06 truy vết tới artifact thực; R8 có ít nhất một vòng cải tiến trước/sau.
- [ ] Bug/giới hạn/đóng góp/source/AI hỗ trợ, report/demo/runbook đúng candidate SHA; giảng viên/lịch/format nộp đã xác nhận.
- [ ] Owner review quyết định phát hành riêng. Hoàn tất BE-1-003 là bằng chứng kỹ thuật; **không tự bật web/deploy**. Chỉ Thuận thao tác GreenNode.

## Phụ thuộc được làm rõ trong đợt này

UI-2-003 chờ BE-2-002 để kiểm lưu/conflict bằng API thật. BE-4-003 chờ BE-2-002 và BE-3-002 để kiểm quyền/file/nguồn, ngoài document service/UI đã có. BE-5-003 chờ BE-1-003 cho kết quả model thật. Những thay đổi này chỉ sửa kế hoạch phụ thuộc; **không tự đổi Status/label/assignee hoặc mở lại task người khác đã đóng**. Nếu thực tế nhóm đã có cách chứng minh tương đương, ghi quyết định review rồi cập nhật kế hoạch.

## Quyết định còn cần người thật chốt

| Việc / rủi ro | Vai trò điều phối | Đầu ra cần ghi |
|---|---|---|
| Thêm/đổi thành viên hoặc chưa nhận lời mời repo | Thuận | Danh tính xác nhận, lời mời đúng người; không dùng chung tài khoản |
| Deadline/rubric cập nhật và nhóm 8 người | Thuận + CT-02 | Nguồn xác nhận lớp/giảng viên; không tự đặt ngày hoặc bỏ thành viên |
| DB/schema/tool OCR/provider/model và ngưỡng test | BE-3/4/1/5 + consumer | ADR ngắn, fixture, config/đơn vị và lý do; chưa quyết thì ghi đề xuất |
| Chưa có server/quota/model | Thuận + BE-1 | Fixture vẫn tiếp tục; real-model pending, không tự mua hoặc dùng key cũ |
| Mất data/đổi quá vùng/chéo account | BE-2/3/5 + UI | Blocker, reproduction/rollback và retest; không hạ mức để đóng task |
| Sai trích dẫn/OCR/đáp án hoặc lệnh giả trong nguồn | BE-1/4/2 | Error taxonomy, cần giáo viên duyệt, negative test và giới hạn rõ |
| Thiếu khảo sát/Word/accessibility/bằng chứng cải tiến | CT-01/06 + owner tương ứng | Kết quả thực hoặc pending; không thay bằng số test kỹ thuật |

Mốc chưa có ngày là chủ ý giữ đúng dữ liệu hiện có. Nhóm chốt lịch sau khi xác nhận lớp và năng lực từng người; không coi kế hoạch này là dự báo tiến độ đã đo.
