# Backlog nhóm — 24 task

Nguồn duy nhất: [tasks.json](tasks.json); danh sách thành viên: [roster.json](roster.json). Các task là việc cần làm, không phải chức năng đã hoàn thành. Mốc không có deadline cho đến khi nhóm chốt.

**Demo để kế thừa:** [Chức năng và phần còn thiếu](../product/DEMO_DA_CO.md) · [Cách mở app và test](CHAY_VA_TEST_DEMO.md) · [Baseline thực chạy](../testing/BASELINE_2026_11_05.md). Đọc trước khi nhận task; demo Node không thay nghiệm thu Python.

**Bảng công việc:** [Bảng tiến độ kéo thả](https://github.com/users/ngocthuan1505/projects/1/views/1) · [Danh sách công việc](https://github.com/users/ngocthuan1505/projects/1/views/2) · [Hướng dẫn cập nhật và thông báo](BOARD.md) · [Các mốc](https://github.com/ngocthuan1505/proj_VA_soandethi/milestones)

Trạng thái hiện tại xem ở trường Status trên Project riêng tư; mỗi thẻ là issue gốc. Nhãn issue `status:*` không tự đồng bộ với bảng. Chi tiết kế hoạch dưới đây không phải báo cáo việc đã hoàn thành.

## M1 — Chốt hợp đồng và baseline

Chốt API FastAPI, core Python, UX và dữ liệu; tám task 001. Không coi worker Python đơn lẻ đủ yêu cầu môn học.

| Task | Vai trò / thành viên | Đầu ra | Phụ thuộc |
|---|---|---|---|
| [UI-1-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/1) | UI-1 / chờ username | Chốt sơ đồ màn hình và luồng kho đề/tài khoản | Bắt đầu ngay |
| [UI-2-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/2) | UI-2 / chờ username | Đặc tả editor và baseline công thức/undo/lưu | Bắt đầu ngay |
| [UI-3-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/3) | UI-3 / chờ username | Chốt UX trợ lý, trạng thái streaming và hợp đồng mock | Bắt đầu ngay |
| [BE-1-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/4) | BE-1 / @ngocthuan1505 | Thuận chốt hợp đồng AI Python và quy trình GreenNode riêng | Bắt đầu ngay |
| [BE-2-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/5) | BE-2 / chờ username | Chốt API FastAPI/OpenAPI và ma trận quyền tài khoản | Bắt đầu ngay |
| [BE-3-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/6) | BE-3 / chờ username | Thiết kế ERD, Python repository và kế hoạch migration | Bắt đầu ngay |
| [BE-4-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/7) | BE-4 / chờ username | Chốt bộ mẫu và kế hoạch import/export bằng Python | Bắt đầu ngay |
| [BE-5-001](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/8) | BE-5 / chờ username | Xác nhận CI Python + UI baseline và kế hoạch tích hợp | Bắt đầu ngay |

## M2 — Hoàn thiện luồng chính

Chuyển backend/core sang Python theo slice có pytest, UI dùng fixture rồi tích hợp FastAPI; chưa triển khai server tự động.

| Task | Vai trò / thành viên | Đầu ra | Phụ thuộc |
|---|---|---|---|
| [UI-1-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/9) | UI-1 / chờ username | Hoàn thiện shell, kho đề và tài khoản theo hợp đồng | UI-1-001, BE-2-001 |
| [UI-2-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/10) | UI-2 / chờ username | Hoàn thiện editor, công thức trực quan và xung đột lưu | UI-2-001, BE-3-001 |
| [UI-3-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/11) | UI-3 / chờ username | Tích hợp trợ lý thật với preview, hủy và retry an toàn | UI-3-001, BE-1-001, BE-2-001 |
| [BE-1-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/12) | BE-1 / @ngocthuan1505 | Thuận triển khai AI orchestration/validation bằng Python | BE-1-001, BE-2-001 |
| [BE-2-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/13) | BE-2 / chờ username | Triển khai API/auth/ownership và validation FastAPI | BE-2-001, BE-3-001 |
| [BE-3-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/14) | BE-3 / chờ username | Triển khai Python persistence/version và migration theo ADR | BE-3-001, BE-2-001 |
| [BE-4-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/15) | BE-4 / chờ username | Triển khai import/OCR/export do Python xử lý | BE-4-001, BE-2-001, BE-3-001 |
| [BE-5-002](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/16) | BE-5 / chờ username | Triển khai job/SSE/cancel và kiểm thử tích hợp Python | BE-5-001, BE-1-001, BE-2-001, BE-3-001 |

## M3 — Nghiệm thu và phát hành thử

Nghiệm thu E2E vào Python không chạy Node API; diễn tập dữ liệu/AI/export. Chỉ Thuận vận hành GreenNode.

| Task | Vai trò / thành viên | Đầu ra | Phụ thuộc |
|---|---|---|---|
| [UI-1-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/17) | UI-1 / chờ username | Nghiệm thu kho đề/tài khoản và accessibility | UI-1-002, BE-2-002 |
| [UI-2-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/18) | UI-2 / chờ username | Nghiệm thu editor đa môn và đối chiếu bản in | UI-2-002, BE-3-002, BE-4-002 |
| [UI-3-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/19) | UI-3 / chờ username | Nghiệm thu chat/sửa vùng với lỗi và kết quả cũ | UI-3-002, BE-1-002, BE-5-002 |
| [BE-1-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/20) | BE-1 / @ngocthuan1505 | Thuận nghiệm thu AI Python thật và diễn tập GreenNode | BE-1-002, BE-2-002, BE-3-002, BE-4-002, BE-5-002 |
| [BE-2-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/21) | BE-2 / chờ username | Nghiệm thu auth/API và rà soát ranh giới truy cập | BE-2-002, BE-3-002, BE-4-002 |
| [BE-3-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/22) | BE-3 / chờ username | Diễn tập khôi phục dữ liệu và kiểm migration release | BE-3-002, BE-2-002 |
| [BE-4-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/23) | BE-4 / chờ username | Nghiệm thu tài liệu và bản xuất đa môn | BE-4-002, UI-2-002 |
| [BE-5-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/24) | BE-5 / chờ username | Nghiệm thu candidate Python và báo cáo đồ án | BE-5-002, UI-1-003, UI-2-003, UI-3-003, BE-2-003, BE-3-003, BE-4-003 |

## Chi tiết nghiệm thu

### UI-1-001 — Chốt sơ đồ màn hình và luồng kho đề/tài khoản

## Phân công

- Vai trò: **UI-1**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `design.js`
- `design.css`
- `app.js`
- `assets/online-login.html`

## Tiêu chí nghiệm thu

- [ ] Có sơ đồ tạo → mở → sửa → lưu → xuất đề và màn hình lỗi/rỗng/đang tải.
- [ ] Đề xuất riêng desktop/mobile, không sao chép nguyên giao diện tham khảo.
- [ ] UI-2/UI-3 và BE-2 review luồng trước triển khai.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy npm test; đính kèm wireframe/ảnh và checklist phím Tab.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-1-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Dùng lại proposal/baseline và cây Decomposition đã có trong docs/course/HO_SO_DA_CO.md; chỉ bổ sung user flow/ghi chép người dùng còn thiếu.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Luồng CRUD, trạng thái giao diện và nghiên cứu người dùng

### Các bước nhỏ

- [ ] 1. Vẽ hành trình tạo/mở/sửa/lưu/xuất và liệt kê loading/empty/error theo màn hình.
- [ ] 2. Chuẩn bị 5 câu hỏi phỏng vấn, điều phối ít nhất 3 giáo viên ẩn danh và ghi baseline chưa biết.
- [ ] 3. Review wireframe với UI-2/3 và BE-2; chốt input/output màn hình, ghi quyết định trong PR.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, UI-3, BE-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-01, CT-02, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-1-001 -->

### UI-2-001 — Đặc tả editor và baseline công thức/undo/lưu

## Phân công

- Vai trò: **UI-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `editor.js`
- `composer.js`
- `pages.js`
- `tests/selection-browser.mjs`

## Tiêu chí nghiệm thu

- [ ] Liệt kê thao tác vùng chọn, công thức, bảng, hình và lỗi tái hiện được.
- [ ] Dùng fixture đề dài để kiểm phân trang, reload và undo giữ định dạng.
- [ ] Chốt với BE-3 snapshot/version cần bảo toàn, chưa đổi schema trực tiếp.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

npm test; node tests/selection-browser.mjs và ảnh fixture.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-2-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Dùng model Question/QuestionVersion và invariants trong hồ sơ Abstraction đã có; lập fixture richDoc/công thức để nối thiết kế với code.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Editor có cấu trúc, round-trip và optimistic concurrency

### Các bước nhỏ

- [ ] 1. Tạo bộ đề fixture ngắn/dài với phân số/hệ, bảng và hình; ghi ID/revision/richDoc mong đợi.
- [ ] 2. Tái hiện selection/undo/reload/công thức và ghi lỗi nhỏ độc lập, không đổi schema lúc lập baseline.
- [ ] 3. Chốt contract snapshot/selection với BE-3 và bản xuất với BE-4, kèm ảnh trạng thái editor.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-4, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-2-001 -->

### UI-3-001 — Chốt UX trợ lý, trạng thái streaming và hợp đồng mock

## Phân công

- Vai trò: **UI-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `workbench.js`
- `studio.js`
- `assets/usability.js`
- `tests/usability-browser.mjs`

## Tiêu chí nghiệm thu

- [ ] Có luồng hỏi/sửa, chip ngữ cảnh, diff, hủy và retry lỗi.
- [ ] Có fixture AI dùng chung BE-1/BE-5, không cần server thật.
- [ ] Ô chat và lịch sử không che nhau trên mobile/cửa sổ thấp.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

node tests/usability-browser.mjs; ghi danh sách state/event.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-3-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Kế thừa ExamRequest target/changes/keep, SessionContext và bước đề xuất/xác nhận của hồ sơ Abstraction; không viết lại khái niệm từ đầu.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine hội thoại, proposal/consent và xử lý tác vụ bất đồng bộ

### Các bước nhỏ

- [ ] 1. Vẽ trạng thái hỏi/sửa/preview/apply/hủy/retry; quy định câu hỏi mơ hồ cần làm rõ.
- [ ] 2. Chốt event fixture success/malformed/stale/cancel với BE-1/5 và chip vùng chọn với UI-2.
- [ ] 3. Kiểm màn hình thấp/mobile, chụp lịch sử và composer không che nhau; review trước triển khai.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-5, UI-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-3-001 -->

### BE-1-001 — Thuận chốt hợp đồng AI Python và quy trình GreenNode riêng

## Phân công

- Vai trò: **BE-1**
- Thành viên: @ngocthuan1505
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `ai.mjs`
- `greennode.mjs`
- `server-kit/`
- `ops/greennode/`

## Tiêu chí nghiệm thu

- [ ] Chốt request/result/job ID/version/timeout/cancel với UI-3 và BE-5.
- [ ] Ghi rõ dữ liệu nào rời máy, nguồn/model/provenance và điều kiện consent.
- [ ] Chỉ Thuận giữ URL/token; nhóm có fixture; chưa chạy lệnh lên server trong task tổ chức repo.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

node --test tests/greennode.test.mjs tests/cloud-ai.test.mjs; không dùng key thật.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-1-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Kế thừa kế hoạch PoC trong proposal, pattern truy xuất/kiểm chứng và ProposeReplaceQuestion của hồ sơ nhóm; chốt ứng viên thử và hợp đồng Python.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Adapter provider, schema validation và kiểm rủi ro AI bằng PoC

### Các bước nhỏ

- [ ] 1. Mô tả contract request/result với job/owner/revision/timeout/cancel và fixture không có key.
- [ ] 2. Lập kế hoạch PoC sửa đúng vùng trong docs/course/POC.md, chốt mẫu/ngưỡng với UI-3/BE-5.
- [ ] 3. Ghi data flow/consent/chi phí/model và runbook cài server mới; chưa vận hành khi chưa có server.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, BE-5, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-1-001 -->

### BE-2-001 — Chốt API FastAPI/OpenAPI và ma trận quyền tài khoản

## Phân công

- Vai trò: **BE-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `mvp-server.mjs`
- `workbench-server.mjs`
- `accounts.mjs`
- `docs/architecture/`

## Tiêu chí nghiệm thu

- [ ] Tài liệu method/request/response/lỗi của route thực tế, phân biệt hiện có và dự kiến.
- [ ] Ma trận guest/member/admin cho đề, file, export, cấu hình AI và snapshot.
- [ ] Chốt DTO và ETag/revision với BE-3, UI-1/2/3; ghi kế hoạch email/recovery trước public rộng.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

npm test; thêm fixture response và negative auth cases còn thiếu.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-2-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc ExamRequest, ADT, ISourceReader và các trạng thái trong hồ sơ Abstraction trước khi chốt DTO/OpenAPI Python.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Contract-first API, kiểm quyền và validation dữ liệu

### Các bước nhỏ

- [ ] 1. Lập danh mục route cũ: method, input/output, status và ma trận guest/member/admin bằng fixture.
- [ ] 2. Chốt DTO đề/version/job/file và OpenAPI dự kiến với BE-3/UI; ghi hiện có khác đích Python.
- [ ] 3. Viết contract/dry run kiểm patch trong docs/course/ALGORITHM.md và negative cases trước triển khai.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-1, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-2-001 -->

### BE-3-001 — Thiết kế ERD, Python repository và kế hoạch migration

## Phân công

- Vai trò: **BE-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `backend-store.mjs`
- `storage.js`
- `docs/architecture/DATA_PLAN.md`

## Tiêu chí nghiệm thu

- [ ] ERD cho user/session/exam/version/document/job/export/share, phân biệt KV hiện có và schema đích.
- [ ] ADR so sánh SQLite local và PostgreSQL về concurrency, vận hành, backup và chi phí; nhóm chốt trước thêm driver.
- [ ] Kế hoạch migrate/rollback trên bản sao, bảo toàn ID/revision/formula/richDoc; không chạy DB thật.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Tạo fixture migration kiểm đếm, FK/ownership dự kiến và golden snapshot.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-3-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Kế thừa sáu đối tượng miền, SessionContext, QuestionVersion và tham chiếu phiên bản trong Abstraction; phần mới là ánh xạ ERD/DB Python và migration.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Repository, transaction/version, migration và backup/restore

### Các bước nhỏ

- [ ] 1. Vẽ ERD và data dictionary có field/type/unit/nullability, đối chiếu KV hiện tại.
- [ ] 2. Viết ADR SQLite/PostgreSQL về concurrency/chi phí/backup; thống nhất lựa chọn trước thêm driver.
- [ ] 3. Thiết kế fixture migration giữ UUID/revision/richDoc và kế hoạch rollback/restore trên bản sao.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, UI-2, BE-5; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-3-001 -->

### BE-4-001 — Chốt bộ mẫu và kế hoạch import/export bằng Python

## Phân công

- Vai trò: **BE-4**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `importers.mjs`
- `word-import.mjs`
- `exports.mjs`
- `math-word.mjs`

## Tiêu chí nghiệm thu

- [ ] Mẫu tự tạo DOCX/PDF/PPTX/ảnh có chữ Việt/công thức/bảng, có ca hỏng/quá lớn.
- [ ] Ma trận định dạng được giữ, có thể mất và cần giáo viên kiểm.
- [ ] Thống nhất DTO tài liệu/trang/nguồn với BE-2/3 và UI-2.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

npm test; dùng fixture không bản quyền/không dữ liệu cá nhân.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-4-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Kế thừa SourceDocument và ISourceReader Success/Failure trong hồ sơ Abstraction; bổ sung DTO/fixture và phương án thư viện Python.

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Pipeline tài liệu, adapter định dạng và kiểm round-trip

### Các bước nhỏ

- [ ] 1. Tạo mẫu DOCX/PDF/PPTX/ảnh tự viết có chữ Việt/công thức/bảng và mẫu lỗi/quá lớn.
- [ ] 2. Đánh giá thư viện Python/công cụ hỗ trợ, license và giới hạn giữ định dạng; không mua API.
- [ ] 3. Chốt DTO nguồn/trang/tài liệu với BE-2/3/UI-2 và kỳ vọng bản học sinh/giáo viên.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, BE-2, BE-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-4-001 -->

### BE-5-001 — Xác nhận CI Python + UI baseline và kế hoạch tích hợp

## Phân công

- Vai trò: **BE-5**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M1; ưu tiên: P0
- Phụ thuộc: Không — có thể bắt đầu ngay.

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `.github/workflows/ci.yml`
- `tests/`
- `docs/team/`

## Tiêu chí nghiệm thu

- [ ] CI uv sync --frozen, pytest/Ruff/ty cho Python; npm ci/test giữ baseline legacy/UI.
- [ ] Phân loại unit/integration/UI/model thật; CI không có secret hoặc GreenNode runner.
- [ ] Ghi checklist merge, giới hạn thời gian job và lỗi baseline; không mua thêm Actions phút.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

CI thật xanh và một bộ UI fixture chạy local.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-5-001 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; chạy baseline local/fixture, đánh dấu điều chưa biết trước khi thiết kế

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine job, tích hợp theo contract và kiểm thử có truy vết

### Các bước nhỏ

- [ ] 1. Chạy baseline CI Python/legacy UI trên fixture; phân biệt unit/integration/browser/model thật.
- [ ] 2. Chốt ma trận tích hợp/timeout/concurrency và sự kiện job với BE-1/2/UI-3.
- [ ] 3. Điều phối WBS/nhịp báo cáo, test log và checklist bằng chứng; không cài runner/deploy GreenNode.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-2, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-02, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-5-001 -->

### UI-1-002 — Hoàn thiện shell, kho đề và tài khoản theo hợp đồng

## Phân công

- Vai trò: **UI-1**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #1, #5

## Phạm vi source

- `design.js`
- `design.css`
- `app.js`
- `assets/online-login.js`

## Tiêu chí nghiệm thu

- [ ] Tạo/mở/đổi tên/tìm đề và trạng thái lưu phản ánh dữ liệu thật.
- [ ] Login/logout/phiên hết hạn có thông báo, giữ bản nháp phù hợp.
- [ ] Responsive desktop/mobile và điều hướng bằng bàn phím; không lộ chức năng admin cho member.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

UI fixture + kiểm thử tài khoản cùng BE-2; không dùng tài khoản thật trong CI.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-1-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-1-001, BE-2-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Luồng CRUD, trạng thái giao diện và nghiên cứu người dùng

### Các bước nhỏ

- [ ] 1. Làm kho đề theo DTO đã chốt bằng fixture: tạo/mở/đổi tên/tìm và trạng thái lưu.
- [ ] 2. Tích hợp login/logout/hết phiên vào Python API khi slice sẵn sàng; giữ draft và thông báo lỗi.
- [ ] 3. Kiểm responsive/bàn phím, gắn ảnh fixture và PR nhỏ; báo riêng phần còn dùng mock.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, UI-3, BE-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-01, CT-02, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-1-002 -->

### UI-2-002 — Hoàn thiện editor, công thức trực quan và xung đột lưu

## Phân công

- Vai trò: **UI-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #2, #6

## Phạm vi source

- `editor.js`
- `composer.js`
- `pages.js`
- `storage.js`

## Tiêu chí nghiệm thu

- [ ] Chèn/sửa công thức đa môn bằng mẫu và bàn phím, không bắt nhớ LaTeX.
- [ ] Undo/reload bảo toàn rich text, công thức, bảng và hình.
- [ ] Xung đột revision không ghi đè im lặng; chỉ chọn/lưu đúng phạm vi.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

selection/authoring/curriculum browser fixtures; npm test.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-2-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-2-001, BE-3-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Editor có cấu trúc, round-trip và optimistic concurrency

### Các bước nhỏ

- [ ] 1. Hoàn thiện một luồng chèn/sửa công thức bằng mẫu; kiểm bàn phím mà không gõ LaTeX.
- [ ] 2. Kiểm round-trip undo/lưu/reload giữ ID/công thức/bảng; sửa lỗi ở helper chung thay vì vá từng caller.
- [ ] 3. Tích hợp revision conflict từ Python API, cho xem lựa chọn xử lý thay ghi đè; nộp từng PR theo luồng.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-4, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-2-002 -->

### UI-3-002 — Tích hợp trợ lý thật với preview, hủy và retry an toàn

## Phân công

- Vai trò: **UI-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #3, #4, #5

## Phạm vi source

- `workbench.js`
- `studio.js`
- `assets/usability.js`

## Tiêu chí nghiệm thu

- [ ] Hỏi không sửa đề; sửa hiển thị diff đúng vùng và version.
- [ ] Stream/hủy/retry không nhân đôi nội dung hoặc áp kết quả đã cũ.
- [ ] Lỗi/timeout giữ lời người dùng đã gõ và trả quyền chỉnh sửa.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

workbench/selection/studio fixtures; tích hợp job với BE-5.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-3-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-3-001, BE-1-001, BE-2-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine hội thoại, proposal/consent và xử lý tác vụ bất đồng bộ

### Các bước nhỏ

- [ ] 1. Tích hợp hỏi và sửa thành hai luồng rõ, preview đúng vùng/revision và chỉ apply sau xác nhận.
- [ ] 2. Xử lý stream/hủy/retry/disconnect từ contract, giữ nội dung đã gõ và không lặp tin nhắn.
- [ ] 3. Chạy PoC fixture cùng BE-1/5, chặn stale/ngoài vùng và kiểm undo; ghi mock/model thật tách biệt.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-5, UI-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-3-002 -->

### BE-1-002 — Thuận triển khai AI orchestration/validation bằng Python

## Phân công

- Vai trò: **BE-1**
- Thành viên: @ngocthuan1505
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #4, #5

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `ai.mjs`
- `cloud-ai.mjs`
- `greennode.mjs`
- `server-kit/worker.py`

## Tiêu chí nghiệm thu

- [ ] Provider output được kiểm tra schema/công thức/nguồn trước áp dụng.
- [ ] Không lộ key trong lỗi, không fallback trả phí; timeout/job ID sai được chặn.
- [ ] Chuẩn bị release worker và checklist để chính Thuận cập nhật GreenNode; không cho CI đăng nhập server.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Fixture success/malformed/timeout/wrong-id/duplicate, model thật chỉ Thuận chạy khi sẵn sàng.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-1-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-1-001, BE-2-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Adapter provider, schema validation và kiểm rủi ro AI bằng PoC

### Các bước nhỏ

- [ ] 1. Triển khai Python adapter cho một provider đã chọn và test fixture thành công/lỗi, không fallback trả phí.
- [ ] 2. Thêm kiểm schema/job/version/phạm vi vào proposal trước preview và golden test so với hành vi cũ.
- [ ] 3. Chạy PoC fixture, chuẩn bị release worker/runbook cho Thuận tự thực hiện; phần model thật ghi chờ nếu thiếu server.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, BE-5, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-1-002 -->

### BE-2-002 — Triển khai API/auth/ownership và validation FastAPI

## Phân công

- Vai trò: **BE-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #5, #6

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `mvp-server.mjs`
- `accounts.mjs`
- `deployment.mjs`

## Tiêu chí nghiệm thu

- [ ] Hai user không truy cập chéo đề/file/export; admin config được kiểm phía server.
- [ ] Input/schema/type/size và status lỗi nhất quán, không rò bí mật.
- [ ] Session/logout/brute-force/email recovery được xử lý hoặc giới hạn invite-only được ghi rõ trước public.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Chuyển validation core đề, scope/patch/version và chuẩn lỗi server sang Python; kiểm quyền không chỉ dựa client.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Negative integration tests cho guest/member/admin, XSS/origin/host và ID không thuộc tài khoản.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-2-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-2-001, BE-3-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Contract-first API, kiểm quyền và validation dữ liệu

### Các bước nhỏ

- [ ] 1. Triển khai một slice auth/session/logout Python có pytest, sau đó slice đề/ownership theo contract.
- [ ] 2. Đưa core validation scope/patch/revision vào server Python, phối hợp transaction với BE-3.
- [ ] 3. Kiểm input sai/quá lớn/origin/host và lỗi không lộ key; giao UI fixture và từng PR nhỏ theo slice.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-1, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-2-002 -->

### BE-3-002 — Triển khai Python persistence/version và migration theo ADR

## Phân công

- Vai trò: **BE-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #6, #5

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `backend-store.mjs`
- `storage.js`
- `tests/deployment.test.mjs`

## Tiêu chí nghiệm thu

- [ ] Adapter/schema theo ADR, giữ caller hiện có hoặc có migration API tương ứng.
- [ ] Write đồng thời có transaction/version conflict; có test rollback và không mất dữ liệu cũ.
- [ ] Migration idempotent, backup/restore trên fixture, chưa đụng kho thật trên GreenNode.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Migration twice, rollback failure, two-user isolation và golden richDoc/formula.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-3-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-3-001, BE-2-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Repository, transaction/version, migration và backup/restore

### Các bước nhỏ

- [ ] 1. Triển khai Python repository/schema đã duyệt cho một luồng lưu/đọc đề với fixture.
- [ ] 2. Thêm transaction/version-conflict và test hai writer, lỗi giữa chừng không mất dữ liệu.
- [ ] 3. Chạy migration hai lần và restore fixture, so ID/count/ownership/công thức; cập nhật API caller qua PR phối hợp.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, UI-2, BE-5; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-3-002 -->

### BE-4-002 — Triển khai import/OCR/export do Python xử lý

## Phân công

- Vai trò: **BE-4**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #7, #5, #6

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `importers.mjs`
- `word-import.mjs`
- `exports.mjs`
- `math-word.mjs`

## Tiêu chí nghiệm thu

- [ ] File hỏng/quá lớn/bất hợp lệ trả lỗi có kiểm soát; nguồn OCR được xem lại.
- [ ] Word giữ công thức OMML; PDF chữ Việt/bảng/hình đọc được.
- [ ] Bản học sinh không chứa đáp án/barem; file theo ownership và có dọn file tạm.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Đưa giải pháp thư viện Python/công cụ hỗ trợ vào ADR, kiểm hợp lệ tệp và license; không bắt Python gọi Node để làm toàn bộ export.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Fixtures hợp lệ/hỏng; kiểm nội dung và render Word/PDF mẫu khi có công cụ.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-4-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-4-001, BE-2-001, BE-3-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Pipeline tài liệu, adapter định dạng và kiểm round-trip

### Các bước nhỏ

- [ ] 1. Triển khai một luồng import Python có MIME/size/ownership/cleanup, hiển thị OCR cần duyệt.
- [ ] 2. Triển khai xuất Word công thức/PDF theo ADR đã chọn; test nội dung và quyền tải.
- [ ] 3. Kiểm bản học sinh không lộ đáp án, file hỏng trả lỗi; so bản in với UI-2, chia PR theo định dạng.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, BE-2, BE-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-4-002 -->

### BE-5-002 — Triển khai job/SSE/cancel và kiểm thử tích hợp Python

## Phân công

- Vai trò: **BE-5**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M2; ưu tiên: P0
- Phụ thuộc: #8, #4, #5, #6

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `workbench-server.mjs`
- `tests/workbench.test.mjs`
- `tests/studio.test.mjs`

## Tiêu chí nghiệm thu

- [ ] Job ràng buộc owner/version, idempotency; disconnect/cancel không áp output muộn.
- [ ] Đặt và kiểm concurrency/timeout/size/cleanup phù hợp, không giả định GPU vô hạn.
- [ ] Test tích hợp UI/API/DB bằng fixture, log có job ID nhưng không ghi prompt/tokens thật.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Stream ngắt giữa chừng, hai user, lặp submit, timeout và process restart với fixture.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-5-002 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-5-001, BE-1-001, BE-2-001, BE-3-001

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine job, tích hợp theo contract và kiểm thử có truy vết

### Các bước nhỏ

- [ ] 1. Triển khai Python job/SSE với owner/version và giới hạn đã chốt bằng contract test.
- [ ] 2. Kiểm cancel/disconnect/duplicate/stale/restart, không để output muộn áp vào đề.
- [ ] 3. Chạy luồng UI→FastAPI→repository bằng fixture cùng các vai trò; ghi log an toàn và PR nhỏ.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-2, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-02, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-5-002 -->

### UI-1-003 — Nghiệm thu kho đề/tài khoản và accessibility

## Phân công

- Vai trò: **UI-1**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #9, #13

## Phạm vi source

- `tests/usability-browser.mjs`
- `design.css`
- `assets/online-login.css`

## Tiêu chí nghiệm thu

- [ ] Hoàn thành hành trình giáo viên mới và quay lại với kho đề thật trên staging/fixture.
- [ ] Tab/focus/label/contrast/mobile và thông báo lỗi được rà soát.
- [ ] Đính kèm bằng chứng, ghi rõ hạn chế còn lại, không tự tuyên bố chứng nhận WCAG.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Checklist UX cùng UI-2/3 và test phiên hết hạn.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-1-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-1-002, BE-2-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Luồng CRUD, trạng thái giao diện và nghiên cứu người dùng

### Các bước nhỏ

- [ ] 1. Cho người thử thực hiện hành trình mới/quay lại, ghi thời gian/lỗi/trợ giúp đã xin phép.
- [ ] 2. Rà Tab/focus/label/contrast và phiên hết hạn, tạo issue cho lỗi có bằng chứng.
- [ ] 3. Kiểm lại sau sửa, viết giữ/sửa/bỏ và giới hạn vào báo cáo nghiệm thu, xin review độc lập.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, UI-3, BE-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-01, CT-02, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-1-003 -->

### UI-2-003 — Nghiệm thu editor đa môn và đối chiếu bản in

## Phân công

- Vai trò: **UI-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #10, #14, #15

## Phạm vi source

- `tests/curriculum-browser.mjs`
- `tests/authoring-browser.mjs`
- `tests/selection-browser.mjs`

## Tiêu chí nghiệm thu

- [ ] Bộ mẫu Toán/Lý/Hóa/Sinh/Văn/Anh và mẫu lớp nhỏ giữ được nội dung khi lưu/xuất.
- [ ] Trang dài/bảng dài/công thức dài không làm mất thao tác hoặc nội dung.
- [ ] Đối chiếu editor với Word/PDF cùng BE-4, ghi lỗi chuyển đổi chưa hỗ trợ.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Golden mẫu tự tạo, reload/undo/export và kiểm bằng mắt.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-2-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-2-002, BE-3-002, BE-4-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Editor có cấu trúc, round-trip và optimistic concurrency

### Các bước nhỏ

- [ ] 1. Chạy bộ mẫu tự tạo Toán/Lý/Hóa/Sinh/Văn/Anh và lớp nhỏ, ghi rõ mẫu nào thực sự đã thử.
- [ ] 2. Đối chiếu editor với Word/PDF cùng BE-4, gồm trang/bảng/công thức dài.
- [ ] 3. Quan sát tác vụ công thức với người dùng, kiểm lại regression và tổng hợp giới hạn hỗ trợ.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-4, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-2-003 -->

### UI-3-003 — Nghiệm thu chat/sửa vùng với lỗi và kết quả cũ

## Phân công

- Vai trò: **UI-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #11, #12, #16

## Phạm vi source

- `tests/selection-browser.mjs`
- `tests/workbench-browser.mjs`
- `tests/studio-browser.mjs`

## Tiêu chí nghiệm thu

- [ ] Bôi đen/hủy/retry/undo và hội thoại dài kiểm desktop/mobile.
- [ ] Đề đã đổi giữa lúc AI chạy không bị ghi đè; sửa phạm vi không lan câu khác.
- [ ] Thông báo mô hình/nguồn/cần giáo viên duyệt rõ; có bằng chứng fixture.
- [ ] UI JavaScript là lớp hỗ trợ; tích hợp hợp đồng FastAPI bằng mock/fixture trước, nghiệm thu cuối vào Python API.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Các luồng malformed/timeout/stale/version/conflict với BE-5.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:UI-3-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ UI-3-002, BE-1-002, BE-5-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine hội thoại, proposal/consent và xử lý tác vụ bất đồng bộ

### Các bước nhỏ

- [ ] 1. Thử chuỗi bôi đen/hỏi/sửa/hủy/retry/undo với hội thoại dài trên hai kích thước màn hình.
- [ ] 2. Tạo tình huống đề đổi giữa lúc chờ, malformed/timeout/duplicate; ghi bằng chứng không ghi đề ngoài ý muốn.
- [ ] 3. Thu phản hồi về ý nghĩa preview/nguồn/model, sửa và kiểm lại rồi bàn giao kết quả có giới hạn.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-5, UI-2; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:UI-3-003 -->

### BE-1-003 — Thuận nghiệm thu AI Python thật và diễn tập GreenNode

## Phân công

- Vai trò: **BE-1**
- Thành viên: @ngocthuan1505
- Milestone: M3; ưu tiên: P0
- Phụ thuộc: #12, #13, #14, #15, #16

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `server-kit/`
- `ops/greennode/`
- `docs/team/RELEASE.md`

## Tiêu chí nghiệm thu

- [ ] Chính Thuận kiểm auth Jupyter/quyền thư mục trước thử server; không dùng link bí mật thay xác thực.
- [ ] Đánh giá sinh/sửa/giải lại trên bộ mẫu đã duyệt và lưu kết quả không có dữ liệu nhạy cảm.
- [ ] Backup/rollback/bật-tắt thử được ghi nhận; chỉ mở công khai khi Thuận quyết định, không nhận lời hứa uptime.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Smoke model thật có timeout/cancel + release checklist; không lấy danh sách model làm bằng chứng suy luận.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-1-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-1-002, BE-2-002, BE-3-002, BE-4-002, BE-5-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Adapter provider, schema validation và kiểm rủi ro AI bằng PoC

### Các bước nhỏ

- [ ] 1. Đọc release candidate, xác nhận backup và bảo vệ Jupyter khi Thuận có server mới và quyết định test.
- [ ] 2. Thuận chạy bộ mẫu model thật theo PoC, ghi model/params/thời gian và đánh giá đúng kiến thức có người duyệt.
- [ ] 3. Thuận ghi kết quả smoke/rollback/bật-tắt nếu đã thử; công bố giới hạn, không tự đánh dấu phần chưa chạy là đạt.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, BE-5, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-1-003 -->

### BE-2-003 — Nghiệm thu auth/API và rà soát ranh giới truy cập

## Phân công

- Vai trò: **BE-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P0
- Phụ thuộc: #13, #14, #15

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `tests/deployment.test.mjs`
- `accounts.mjs`
- `deployment.mjs`

## Tiêu chí nghiệm thu

- [ ] Test E2E guest/member/admin và các ID/token giả/hết hạn/thu hồi.
- [ ] Endpoint lỗi không lộ secret và API spec đồng bộ với implementation.
- [ ] Danh sách rủi ro trước public cùng cách xử lý; chưa mở đăng ký rộng khi recovery/auth chưa sẵn sàng.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Negative auth matrix, upload/export/share ownership, origin/host và logout.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-2-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-2-002, BE-3-002, BE-4-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Contract-first API, kiểm quyền và validation dữ liệu

### Các bước nhỏ

- [ ] 1. Chạy ma trận guest/member/admin và ca token/ID hết hạn/sai owner trên FastAPI không có Node API.
- [ ] 2. Đối chiếu OpenAPI với implementation và upload/export/share với BE-4; ghi lỗi/rủi ro còn mở.
- [ ] 3. Kiểm lại sau sửa và bàn giao bằng chứng test, điều kiện invite-only/recovery trước public cho Thuận.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-3, BE-1, UI-1; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-2-003 -->

### BE-3-003 — Diễn tập khôi phục dữ liệu và kiểm migration release

## Phân công

- Vai trò: **BE-3**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P0
- Phụ thuộc: #14, #13

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `backend-store.mjs`
- `docs/architecture/DATA_PLAN.md`
- `docs/team/RELEASE.md`

## Tiêu chí nghiệm thu

- [ ] Backup/restore trên DB bản sao khôi phục được tài khoản/đề/file/version theo thiết kế.
- [ ] Migration lỗi quay lui được, ghi checksum/count/integrity và thời gian mất dịch vụ đo thực tế.
- [ ] Bàn giao lệnh đã review cho Thuận; không tự đọc/đổi DB server thật.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Restore drill fixture, replay revision conflicts và diễn tập nâng/hạ version.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-3-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-3-002, BE-2-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Repository, transaction/version, migration và backup/restore

### Các bước nhỏ

- [ ] 1. Tạo backup nhất quán từ DB fixture và restore vào đích mới, giữ bản gốc.
- [ ] 2. Diễn tập lỗi migration/rollback, ghi checksum/count/integrity và thời gian thật.
- [ ] 3. Viết lệnh/runbook đã review cho Thuận dùng khi có volume; ghi rõ dữ liệu server cũ chưa khôi phục.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-2, UI-2, BE-5; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-3-003 -->

### BE-4-003 — Nghiệm thu tài liệu và bản xuất đa môn

## Phân công

- Vai trò: **BE-4**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #15, #10

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `tests/mvp-backend.test.mjs`
- `tests/studio.test.mjs`
- `exports.mjs`

## Tiêu chí nghiệm thu

- [ ] Đối chiếu mẫu chữ Việt/công thức/bảng/hình/điểm bằng mắt và tự động.
- [ ] Kiểm bản giáo viên/học sinh, quyền file và tài liệu OCR không tự gán nguồn.
- [ ] Công bố giới hạn shape/chart/OCR công thức và bộ mẫu regression được phép chia sẻ.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Golden DOCX/PDF + fixture import hỏng và giới hạn dung lượng.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-4-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-4-002, UI-2-002

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** Pipeline tài liệu, adapter định dạng và kiểm round-trip

### Các bước nhỏ

- [ ] 1. Chạy golden import/export đa môn trên FastAPI, gồm tệp hỏng/quá lớn/sai quyền.
- [ ] 2. Xem Word/PDF cùng UI-2 để bắt lỗi bảng/công thức/chữ Việt mà test text không thấy.
- [ ] 3. Công bố giới hạn OCR/shape/chart và bộ mẫu regression hợp pháp; ghi bằng chứng từng định dạng.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** UI-2, BE-2, BE-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-03, CT-04, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-4-003 -->

### BE-5-003 — Nghiệm thu candidate Python và báo cáo đồ án

## Phân công

- Vai trò: **BE-5**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P0
- Phụ thuộc: #16, #17, #18, #19, #21, #22, #23

## Phạm vi source

- `backend/src/mach_backend/`
- `backend/tests/`
- `.github/workflows/ci.yml`
- `tests/`
- `docs/team/RELEASE.md`

## Tiêu chí nghiệm thu

- [ ] CI xanh đúng commit/tag dự kiến; test UI và giới hạn tải có số liệu, không bịa khả năng chịu tải.
- [ ] Tổng hợp bug còn lại, hướng dẫn chạy sạch, báo cáo đồ án và rollback.
- [ ] Bàn giao candidate cho Thuận duyệt BE-1-003; không tự deploy hoặc nâng gói trả phí.
- [ ] Python là backend/core chính. Source Node chỉ tham chiếu hành vi; không dùng facade Python gọi Node để làm nghiệp vụ.
- [ ] Có bằng chứng CT liên quan và đầu ra từng bước; báo cáo progress/blocker/nghiệm thu theo docs/team/BAO_CAO.md, chưa tick thay cho kiểm thử/review.

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Full suite + manual checklist và kiểm source không có secret/runtime.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

<!-- mach-course-execution:BE-5-003 -->
## Bắt tay thực hiện và bằng chứng môn

**Đầu vào:** Đọc file tham chiếu và acceptance bên trên; nhận output/contract đã review từ BE-5-002, UI-1-003, UI-2-003, UI-3-003, BE-2-003, BE-3-003, BE-4-003

**Đầu ra:** PR nhỏ hoặc tài liệu review được, fixture/test log/ảnh phù hợp acceptance; ghi rõ phần chưa chạy và liên kết báo cáo vào issue gốc.

**Pattern/công cụ:** State machine job, tích hợp theo contract và kiểm thử có truy vết

### Các bước nhỏ

- [ ] 1. Chạy full suite và tác vụ người dùng của candidate đúng commit, ghi chỉ số thật và bug còn lại.
- [ ] 2. Tổng hợp CT-01…06, phần đóng góp từng người, nguồn tái sử dụng/AI, trade-off và demo script.
- [ ] 3. Review báo cáo với nhóm, bàn giao candidate/release checklist cho Thuận; không tự phát hành.

Đây là gói việc; nếu một bước hơn khoảng một ngày, tách issue con và liên kết cha/phụ thuộc. Không coi checklist là test đã chạy.

**Reviewer theo vai trò:** BE-1, BE-2, UI-3; chờ username thực, không tự gán người chưa biết.

**Hồ sơ môn liên quan:** CT-02, CT-04, CT-05, CT-06 — [yêu cầu và nguồn slide](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/course/README.md).

[Báo tiến độ / vướng mắc / đề nghị nghiệm thu](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/BAO_CAO.md). Đề nghị xong → Chờ duyệt; reviewer chấp nhận mới Hoàn thành.
<!-- /mach-course-execution:BE-5-003 -->
