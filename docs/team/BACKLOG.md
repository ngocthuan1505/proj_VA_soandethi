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
| [UI-2-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/18) | UI-2 / chờ username | Nghiệm thu editor đa môn và đối chiếu bản in | UI-2-002, BE-3-002, BE-4-002, BE-2-002 |
| [UI-3-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/19) | UI-3 / chờ username | Nghiệm thu chat/sửa vùng với lỗi và kết quả cũ | UI-3-002, BE-1-002, BE-5-002 |
| [BE-1-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/20) | BE-1 / @ngocthuan1505 | Thuận nghiệm thu AI Python thật và diễn tập GreenNode | BE-1-002, BE-2-002, BE-3-002, BE-4-002, BE-5-002 |
| [BE-2-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/21) | BE-2 / chờ username | Nghiệm thu auth/API và rà soát ranh giới truy cập | BE-2-002, BE-3-002, BE-4-002 |
| [BE-3-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/22) | BE-3 / chờ username | Diễn tập khôi phục dữ liệu và kiểm migration release | BE-3-002, BE-2-002 |
| [BE-4-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/23) | BE-4 / chờ username | Nghiệm thu tài liệu và bản xuất đa môn | BE-4-002, UI-2-002, BE-2-002, BE-3-002 |
| [BE-5-003](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/24) | BE-5 / chờ username | Nghiệm thu candidate Python và báo cáo đồ án | BE-5-002, UI-1-003, UI-2-003, UI-3-003, BE-2-003, BE-3-003, BE-4-003, BE-1-003 |

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
<!-- mach-task-detail:UI-1-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Chạy được demo local, đọc D01/D12/D13/D15 và proposal; chưa cần API Python hoặc server.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Đi một vòng tạo/mở/đổi tên/tìm/lưu/xuất trên dữ liệu tự tạo; ghi màn hình và source kế thừa.
- [ ] **W02** — Vẽ luồng guest/member/admin, đăng nhập/hết phiên và kho rỗng/đang tải/lỗi; ghi nút quay lại và bản nháp.
- [ ] **W03** — Đối chiếu mỗi thao tác với API/data cần nhận; ghi field dùng thật thay vì tự đoán DTO.
- [ ] **W04** — Đặc tả desktop/mobile, thứ tự Tab/focus và thông báo lưu/xung đột; chỉ ra chỗ cần phối hợp UI-2/3.
- [ ] **W05** — Review wireframe với BE-2/UI-2/UI-3; ghi quyết định và câu hỏi còn mở vào issue.

Mã bước/ca luôn đi cùng task, ví dụ UI-1-001/W01 và UI-1-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Dùng fixture tạo đề rồi quay kho và mở lại. | Sơ đồ có đủ điểm vào/ra và dữ liệu hiển thị đúng đề. |
| T02 | Lỗi/từ chối | Phiên hết hạn khi có bản nháp chưa lưu. | Thiết kế nêu cách thông báo/khôi phục, không gửi nội dung sang tài khoản khác. |
| T03 | Biên/đồng thời | Kho rỗng trên viewport hẹp và điều khiển bằng Tab. | Có CTA tạo đề, focus thấy được, nút chính truy cập được. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Sơ đồ màn hình/luồng, bảng trạng thái và UI→API, ảnh baseline có commit; đường dẫn đề xuất docs/design/luong-man-hinh.md.

**Bên nhận bàn giao:** BE-2, UI-2, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R6, R7; UC-01, UC-03, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-1-001 -->

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
<!-- mach-task-detail:UI-2-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có demo editor và fixture baseline; đọc mô hình QuestionVersion/richDoc và phân biệt ID với vị trí câu.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chọn mẫu chữ Việt/công thức/bảng/hình ở Toán, Hóa và một môn văn bản; lưu bản trước và sau thao tác.
- [ ] **W02** — Đặc tả cấu trúc editor, vị trí công thức, vùng chọn và undo/redo; chỉ rõ hành vi đang kế thừa.
- [ ] **W03** — Lập bộ golden fixture round-trip richDoc→lưu→mở→Word/PDF với ID/version và ghi chú định dạng.
- [ ] **W04** — Chốt DTO lưu/patch và cách hiển thị revision conflict cùng BE-3/BE-2; không làm phẳng richDoc thành text.
- [ ] **W05** — Ghi các trường hợp chưa hỗ trợ, ảnh so sánh và quyết định review cho UI-3/BE-4.

Mã bước/ca luôn đi cùng task, ví dụ UI-2-001/W01 và UI-2-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Phân số, bảng và hình qua lưu/mở lại/undo. | Kỳ vọng giữ nội dung, UUID, cấu trúc và vị trí công thức được ghi để tái chạy. |
| T02 | Lỗi/từ chối | Chọn vùng cắt ngang cấu trúc bảng không thể bảo toàn. | Đặc tả từ chối rõ và giữ nguyên đề, không ngầm sửa cả bảng. |
| T03 | Biên/đồng thời | Hai công thức giống nhau và đoạn có nhiều dấu tiếng Việt. | Xác định đúng node/vùng, không chọn theo text trùng. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Đặc tả editor/richDoc, ma trận golden fixture và ảnh đối chiếu; đề xuất docs/design/editor-va-richdoc.md.

**Bên nhận bàn giao:** BE-3, BE-4, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R6, R7, R8; UC-05, UC-06, UC-08, UC-09, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-2-001 -->

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
<!-- mach-task-detail:UI-3-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có demo chat, selection/workbench fixture và input/output AI do BE-1/BE-2 đang review.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Vẽ state machine idle/clarify/preview/running/cancel/error/retry và phân biệt hỏi với sửa.
- [ ] **W02** — Ghi payload UI cần cho scope, version, jobId và proposal; thống nhất event và lỗi với BE-1/2/5.
- [ ] **W03** — Lập mock thành công, thiếu nguồn, quá vùng, stale và stream đứt; đánh dấu dữ liệu fixture rõ ràng.
- [ ] **W04** — Thiết kế vị trí ngữ cảnh, diff và nút xác nhận/hủy; giữ prompt và vùng đọc tin cũ khi có lỗi/tin mới.
- [ ] **W05** — Review keyboard/mobile và kịch bản PoC sửa một vùng; gửi quyết định cho bên backend.

Mã bước/ca luôn đi cùng task, ví dụ UI-3-001/W01 và UI-3-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Chỉ hỏi rồi yêu cầu đề xuất sửa. | Hai luồng tách bạch, tài liệu chỉ đổi sau xác nhận proposal. |
| T02 | Lỗi/từ chối | Mock trả kết quả của version cũ. | Có trạng thái stale và hành động tạo lại; không xem là thành công. |
| T03 | Biên/đồng thời | Hủy ngay trước event cuối và gửi lại prompt. | Thiết kế không áp kết quả muộn hoặc nhân đôi nội dung. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Sơ đồ trạng thái trợ lý, ví dụ payload/event/lỗi và mock có thể chạy; đề xuất docs/design/tro-ly-va-job.md.

**Bên nhận bàn giao:** BE-1, BE-2, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R4, R5, R6, R7; UC-04, UC-06, UC-07, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-3-001 -->

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
<!-- mach-task-detail:BE-1-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Đọc adapter/validator cũ và nguồn thiết kế; có fixture được phép. Thiếu server/model thật không chặn thiết kế.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Lập routing Sinh/Sửa/Kiểm: quy tắc cục bộ, truy xuất nguồn hay model; chỉ rõ khi cần hỏi lại.
- [ ] **W02** — Chốt input/output AI Python với questionId/version/scope/source locator và schema lỗi.
- [ ] **W03** — Đặc tả chọn/đối chiếu nguồn, yêu cầu evidence và cách báo thiếu căn cứ; tài liệu nguồn không có quyền ra lệnh.
- [ ] **W04** — Tạo adapter fixture valid/invalid/rate-limit/timeout/cancel; thống nhất retry và giới hạn với BE-5.
- [ ] **W05** — Chuẩn bị runbook cấu hình/test model chỉ cho Thuận; ghi phương án khi chưa có AI và không fallback trả phí.

Mã bước/ca luôn đi cùng task, ví dụ BE-1-001/W01 và BE-1-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Cùng request Sinh/Sửa/Kiểm tới adapter fixture. | Mỗi loại có schema và route rõ, check không được đọc đáp án cũ như đáp án chuẩn. |
| T02 | Lỗi/từ chối | Nguồn chứa câu yêu cầu bỏ qua quyền hoặc gửi khóa. | Nội dung được coi là dữ liệu, không đổi policy/route hoặc lộ khóa. |
| T03 | Biên/đồng thời | Chưa có provider hoặc thiếu consent gửi nguồn. | Trả lý do/cách tiếp tục, không gọi nhà cung cấp khác ngầm. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Hợp đồng AI/routing/evidence, fixture request-response và runbook; đề xuất docs/contracts/ai.md.

**Bên nhận bàn giao:** BE-2, BE-4, BE-5, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R4, R5, R7; UC-03, UC-04, UC-06, UC-07, UC-09. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-1-001 -->

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
<!-- mach-task-detail:BE-2-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Đọc route Node/auth/ownership và mô hình miền; có bản draft schema từ BE-3.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Inventory route/account/workspace/source/job/proposal/export/share và caller UI; phân nhóm port.
- [ ] **W02** — Chốt OpenAPI DTO, validation, định dạng lỗi và mã HTTP với consumer; endpoint mới chỉ là đề xuất cho tới khi review.
- [ ] **W03** — Lập ma trận guest/member/admin × tài nguyên × thao tác, kể cả download/share/config AI.
- [ ] **W04** — Chốt session/cookie/logout/expiry, Origin/CSRF theo transport và chính sách file không tin cậy.
- [ ] **W05** — Tạo fixture contract có owner/ID/version khác nhau; review với UI-1/3 và BE-1/3/4/5.

Mã bước/ca luôn đi cùng task, ví dụ BE-2-001/W01 và BE-2-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | UI gọi luồng đọc/lưu đề bằng fixture theo OpenAPI. | Input/output và lỗi có ví dụ khớp schema đã review. |
| T02 | Lỗi/từ chối | Member đổi ID để đọc file/export của user khác. | Contract quy định từ chối phía server, không chỉ ẩn nút. |
| T03 | Biên/đồng thời | Cookie hết hạn, Origin lạ hoặc revision không đúng. | Phân biệt auth/CSRF/conflict; không mất bản nháp vì lỗi chung chung. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** OpenAPI review được, bảng quyền/lỗi và fixture hợp đồng; đề xuất docs/contracts/http.md.

**Bên nhận bàn giao:** UI-1, UI-3, BE-3, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R5, R6, R7; UC-01, UC-02, UC-03, UC-04, UC-06, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-2-001 -->

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
<!-- mach-task-detail:BE-3-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có bản xuất fixture richDoc/SQLite cũ và Abstraction của nhóm; chỉ dùng dữ liệu tự tạo.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Inventory key/prefix/owner/file/version của store cũ và các consumer; ghi record count/ID/shape fixture.
- [ ] **W02** — Đối chiếu ERD/data dictionary với sáu entity miền, SessionContext và tài nguyên kỹ thuật session/job/export.
- [ ] **W03** — Chốt ADR DB/transaction/index/concurrency/serialization cùng BE-2; lựa chọn chưa được review vẫn là đề xuất.
- [ ] **W04** — Đặc tả migration idempotent và backup/restore/rollback trên bản sao, bao gồm file reference và richDoc.
- [ ] **W05** — Tạo fixture before/after/expected và checklist review cho UI-2/BE-4/5.

Mã bước/ca luôn đi cùng task, ví dụ BE-3-001/W01 và BE-3-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Đối chiếu cùng đề fixture ở schema cũ và đích. | UUID, version, owner, công thức/bảng/hình và nguồn có đường ánh xạ rõ. |
| T02 | Lỗi/từ chối | Payload/file reference hỏng hoặc field bắt buộc thiếu. | Có cách từ chối/cách ly và rollback; không âm thầm bỏ nội dung. |
| T03 | Biên/đồng thời | Migration chạy lại và hai phiên ghi cùng revision. | Thiết kế idempotency/conflict cụ thể, không tạo bản sao hoặc last-write-wins ngầm. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** ERD/data dictionary/ADR, contract repository và fixture migration có checksum; đề xuất docs/contracts/du-lieu.md.

**Bên nhận bàn giao:** BE-2, UI-2, BE-4, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R3, R6, R7; UC-01, UC-02, UC-03, UC-06, UC-08, UC-09, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-3-001 -->

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
<!-- mach-task-detail:BE-4-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Đọc import/export cũ và tài nguyên nguồn đã thiết kế; tự tạo file không nhạy cảm.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Tạo DOCX/PDF/PPTX/text/ảnh chữ Việt có công thức/bảng/hình và các file hỏng/quá giới hạn.
- [ ] **W02** — Lập expected extraction theo trang/slide/locator, ghi phần giữ được/mất/cần giáo viên xem.
- [ ] **W03** — Chọn thử thư viện Python/công cụ hỗ trợ theo fixture, license, kích thước và tái lập; chưa mua OCR/API.
- [ ] **W04** — Chốt SourceDocument/evidence và file ownership/retention với BE-2/3/1; nguồn không tự thành prompt.
- [ ] **W05** — Chốt bản học sinh/giáo viên, công thức OMML, PDF và ma trận kiểm trực quan cùng UI-2.

Mã bước/ca luôn đi cùng task, ví dụ BE-4-001/W01 và BE-4-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Đọc file nguồn hợp lệ hai trang/slide có tiếng Việt. | Expected giữ nội dung và vị trí nguồn để truy vết lại. |
| T02 | Lỗi/từ chối | File giả đuôi, hỏng hoặc quá giới hạn cấu hình. | Hợp đồng từ chối an toàn và không tạo tài nguyên mồ côi. |
| T03 | Biên/đồng thời | Ảnh mờ, công thức OCR hoặc chart/shape không giữ được. | Báo độ không chắc/giới hạn, không tự xác nhận nội dung đúng. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Bộ file synthetic + expected/manifest, ma trận hỗ trợ định dạng và ADR công cụ; đề xuất docs/contracts/tai-lieu.md.

**Bên nhận bàn giao:** BE-1, BE-2, BE-3, UI-2. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R6, R7, R8; UC-02, UC-05, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-4-001 -->

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
<!-- mach-task-detail:BE-5-001 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có baseline 05/11 và CI đang có; dùng fixture, không runner server thật.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Tái lập môi trường Node/Python, phân loại unit/contract/integration/browser/model thật và lưu baseline theo commit.
- [ ] **W02** — Chốt event/state job cùng BE-1/2/UI-3: jobId, thứ tự, terminal state và cancellation.
- [ ] **W03** — Lập ma trận luồng tích hợp, lỗi mất mạng/quá hạn/quá tải và cách phục hồi không mất dữ liệu.
- [ ] **W04** — Chốt ngưỡng timeout/concurrency/size test cùng owner trước đo; cấu hình/đơn vị phải được ghi, không bịa SLA.
- [ ] **W05** — Review gates M1/M2/M3, quy trình bug/report/CI và trách nhiệm bàn giao từng nhóm.

Mã bước/ca luôn đi cùng task, ví dụ BE-5-001/W01 và BE-5-001/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Clone sạch rồi chạy bộ kiểm đã công bố. | Tái lập được hoặc có lỗi môi trường cụ thể; không chỉ dẫn ảnh CI cũ. |
| T02 | Lỗi/từ chối | Một job timeout hoặc test thất bại. | Log phân loại lỗi và giữ artifact sạch; CI không deploy hoặc lộ secret. |
| T03 | Biên/đồng thời | Hai event kết thúc trùng hoặc đến không đúng thứ tự. | Contract nêu một terminal state, dedupe và consumer xử lý được. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Baseline log/manifest theo commit, contract job, kế hoạch tích hợp và cấu hình ngưỡng chờ chốt; đề xuất docs/contracts/jobs.md.

**Bên nhận bàn giao:** BE-1, BE-2, UI-3, BE-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R5, R6, R7, R8; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-5-001 -->

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
<!-- mach-task-detail:UI-1-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** UI-1-001/BE-2-001 có hợp đồng review được; có thể làm mock trước nhưng chỉ gọi tích hợp khi API Python tương ứng sẵn sàng.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Giữ shell/kho cũ, nối DTO để tạo/mở/đổi tên/tìm/nhân bản và trạng thái lưu theo từng PR.
- [ ] **W02** — Nối login/logout/expiry và member/admin; không gửi bản nháp của phiên cũ cho account mới.
- [ ] **W03** — Thêm màn hình chọn/xác nhận tùy chọn giáo viên; chỉ preference đã xác nhận được áp vào đề mới.
- [ ] **W04** — Xử lý empty/loading/error/conflict/offline và điều hướng focus/mobile theo đặc tả.
- [ ] **W05** — Tích hợp một lát thật với FastAPI, chạy E2E cùng BE-2/3 và ghi rõ màn hình còn mock.

Mã bước/ca luôn đi cùng task, ví dụ UI-1-002/W01 và UI-1-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Đăng nhập, tạo/đổi tên/tìm đề rồi reload. | Kho lấy dữ liệu đúng owner từ Python và giữ thay đổi đã lưu. |
| T02 | Lỗi/từ chối | Hết phiên giữa lúc soạn hoặc API trả lỗi. | Thông báo có hành động, giữ nháp riêng an toàn, không báo đã lưu sai. |
| T03 | Biên/đồng thời | Hai account và một preference mới chưa xác nhận. | Kho không lẫn; preference nháp không tự áp cho đề tiếp theo. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** PR UI nhỏ, bảng caller đã chuyển/chưa chuyển, fixture và ảnh/E2E tới Python.

**Bên nhận bàn giao:** BE-2, BE-3, UI-2. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R5, R6, R7; UC-01, UC-03, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-1-002 -->

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
<!-- mach-task-detail:UI-2-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Baseline UI-2-001 và schema BE-3-001 đã review; cần API lưu/version thật trước nghiệm thu tích hợp.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Giữ TipTap/MathLive và mẫu đa môn; sửa helper chung cho lỗi đã tái hiện thay vì viết lại editor.
- [ ] **W02** — Nối load/save richDoc với schema Python, giữ UUID/node/math/table/figure và đánh dấu trạng thái lưu.
- [ ] **W03** — Bảo toàn vùng ngoài thay đổi, undo/redo cả transaction và selection khi modal/chat mở/đóng.
- [ ] **W04** — Hiển thị conflict/stale và lựa chọn đọc lại/giữ nháp theo contract; không ghi đè im lặng.
- [ ] **W05** — Chạy golden đa môn và ảnh Word/PDF cùng BE-3/4; nộp PR theo một luồng có regression.

Mã bước/ca luôn đi cùng task, ví dụ UI-2-002/W01 và UI-2-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Chèn phân số/bảng/hình, lưu Python, reload rồi undo sửa mới. | Nội dung/ID/định dạng ngoài thay đổi giữ đúng. |
| T02 | Lỗi/từ chối | Server báo conflict hoặc trả richDoc không hợp lệ. | Không đè bản đang mở, nêu cách phục hồi và giữ bản gốc. |
| T03 | Biên/đồng thời | Công thức trùng, text nhiều đoạn và một ô bảng. | Chọn đúng node/vùng; phần không hỗ trợ được từ chối rõ. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** PR editor/caller Python, golden round-trip và ảnh chênh lệch trước-sau.

**Bên nhận bàn giao:** BE-3, BE-4, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R6, R7, R8; UC-05, UC-06, UC-08, UC-09, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-2-002 -->

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
<!-- mach-task-detail:UI-3-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Contract UI-3/BE-1/BE-2/BE-5 đã review; dùng mock để làm UI nhưng nghiệm thu phải nối job/proposal Python.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Nối gửi hỏi/làm rõ/sinh/sửa với snapshot, source và scope/version đúng hợp đồng.
- [ ] **W02** — Hiện diff đúng nội dung; xác nhận mới gọi apply, không lấy câu trả lời chat làm đề đã lưu.
- [ ] **W03** — Xử lý event tiến độ, thứ tự/dedupe, hủy/retry/disconnect và kết quả đến muộn.
- [ ] **W04** — Giữ prompt, vị trí cuộn, ngữ cảnh và quyền sửa khi lỗi; gỡ chip phải gỡ phạm vi thật.
- [ ] **W05** — Chạy PoC fixture và E2E với backend Python, gồm stale/quá vùng/undo; tách model thật khỏi mock.

Mã bước/ca luôn đi cùng task, ví dụ UI-3-002/W01 và UI-3-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Hỏi rồi sửa vùng, xem diff và xác nhận một lần. | Hỏi không ghi đề; apply đúng version/phạm vi và undo nguyên transaction. |
| T02 | Lỗi/từ chối | Proposal quá vùng hoặc scope hết hiệu lực. | Không áp nội dung và không ngầm mở rộng phạm vi. |
| T03 | Biên/đồng thời | Nhấn hủy/retry khi stream đứt hoặc response cũ tới. | Không nhân đôi/ghi muộn; prompt và phần đã lưu vẫn còn. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** PR tích hợp trợ lý, fixture event/proposal và log E2E vào Python.

**Bên nhận bàn giao:** BE-1, BE-2, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R4, R5, R6, R7; UC-04, UC-06, UC-07, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-3-002 -->

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
<!-- mach-task-detail:BE-1-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Hợp đồng AI/HTTP/source đã review; có fixture repo/job. Không cần GreenNode để implement/test Python.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Implement một adapter Python được chọn theo contract và routing rule/retrieval/model; mở rộng provider theo test parity.
- [ ] **W02** — Truy xuất nguồn được phép theo owner/version/locator; giữ evidence và báo thiếu căn cứ thay vì bịa trích dẫn.
- [ ] **W03** — Validate schema, toán/cấu trúc hỗ trợ, scope/baseVersion và trạng thái trước khi trả proposal; check không sao chép đáp án cũ.
- [ ] **W04** — Chặn lệnh giả trong nguồn, thiếu consent, timeout/refusal/rate-limit và fallback trả phí ngầm; phối hợp cancel với BE-5.
- [ ] **W05** — Chạy golden fixture so Node, log PoC và giới hạn; chỉ Thuận thử model thật sau khi có cấu hình hợp lệ.

Mã bước/ca luôn đi cùng task, ví dụ BE-1-002/W01 và BE-1-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Request sửa hợp lệ có nguồn đã chọn. | Python trả proposal có scope/version/evidence hợp lệ, chưa tự ghi đề. |
| T02 | Lỗi/từ chối | Response sai schema/ngoài vùng hoặc locator không tồn tại. | Từ chối/đánh dấu cần xem, không trả trạng thái đã kiểm đúng. |
| T03 | Biên/đồng thời | Provider timeout, nguồn chứa prompt injection hoặc không consent. | Không lộ key, không gọi provider khác ngầm, dữ liệu đề giữ nguyên. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Service/adapter/validator Python và pytest contract, fixture retrieval/evidence, log PoC không có khóa.

**Bên nhận bàn giao:** BE-2, BE-4, BE-5, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R3, R4, R5, R7; UC-03, UC-04, UC-06, UC-07, UC-09. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-1-002 -->

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
<!-- mach-task-detail:BE-2-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** BE-2-001/BE-3-001 đã chốt; repository có interface fixture để làm song song, luồng thật cần repository Python.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Implement session/auth/role dependency và ownership phía server cho từng router FastAPI.
- [ ] **W02** — Implement API đề/nguồn/preference/config/proposal/share/export theo DTO, kiểm input và lỗi nhất quán.
- [ ] **W03** — Confirm proposal trong transaction: đối chiếu owner/baseVersion/scope, chỉ ghi một lần và invalidation trạng thái liên quan.
- [ ] **W04** — Bảo vệ upload/download/config, Origin/CSRF, session expiry/logout và lỗi không lộ secret.
- [ ] **W05** — Chạy pytest dương/âm và contract UI, ghi endpoint đã chuyển/chưa chuyển; không route nghiệp vụ về Node.

Mã bước/ca luôn đi cùng task, ví dụ BE-2-002/W01 và BE-2-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Owner tạo/lưu đề rồi confirm proposal đúng version. | API/Python repository trả dữ liệu đúng contract và ghi một revision hợp lệ. |
| T02 | Lỗi/từ chối | User khác gọi ID đề/file/export/config hoặc Origin không hợp lệ. | Server từ chối theo contract, không lộ tài nguyên/khóa qua error. |
| T03 | Biên/đồng thời | Confirm hai lần, phiên hết hạn hoặc baseVersion cũ. | Không ghi lặp/ghi đè; phản hồi lỗi hoặc kết quả idempotent đã được chốt. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Router/auth/dependencies Python, OpenAPI thực sinh, pytest quyền/version/idempotency và bảng parity route.

**Bên nhận bàn giao:** BE-3, UI-1, UI-3, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R5, R6, R7; UC-01, UC-02, UC-03, UC-04, UC-06, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-2-002 -->

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
<!-- mach-task-detail:BE-3-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** ADR/schema/repository contract đã review; có DB synthetic cũ và expected checksum, không dùng DB thật.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Implement Python repository/transaction/constraint theo ADR, giữ ID/owner/revision và richDoc đầy đủ.
- [ ] **W02** — Lưu source/version/evidence và preference có trạng thái xác nhận; liên kết bảng/hình/ngữ liệu theo ID ổn định.
- [ ] **W03** — Implement optimistic concurrency và apply nhiều field trong một transaction, rollback nếu lỗi giữa chừng.
- [ ] **W04** — Viết migration idempotent cùng backup/restore trên bản sao; kiểm file reference, record count và checksum.
- [ ] **W05** — Nối consumer API/document/job bằng contract tests, nộp cách rollback và bảng dữ liệu trước-sau.

Mã bước/ca luôn đi cùng task, ví dụ BE-3-002/W01 và BE-3-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Port workspace có richDoc, nhiều version, file nguồn và preference. | ID/owner/nội dung/revision khớp expected, không mất công thức hay nguồn. |
| T02 | Lỗi/từ chối | Migration lỗi giữa chừng hoặc một field patch không hợp lệ. | Rollback nguyên transaction, bản trước vẫn đọc được. |
| T03 | Biên/đồng thời | Chạy lại migration và hai writer cùng revision. | Không nhân đôi record; một writer bị conflict thay vì ghi đè. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Repository/migration Python, fixture trước-sau, checksum và script/runbook restore bản sao.

**Bên nhận bàn giao:** BE-2, BE-4, BE-5, UI-2. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R3, R6, R7; UC-01, UC-02, UC-03, UC-06, UC-08, UC-09, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-3-002 -->

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
<!-- mach-task-detail:BE-4-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Contract tài liệu/HTTP/data đã review, fixture định dạng đã có; quyền nguồn/export phải do Python kiểm.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Implement ISourceReader/extraction Python theo kiểu file, giữ trang/slide/locator và metadata nguồn.
- [ ] **W02** — Validate loại/kích thước/nội dung file và ownership, cleanup khi lỗi; không tin đuôi file hay text OCR.
- [ ] **W03** — Implement OCR với trạng thái không chắc; cho preview/xác nhận trước dùng làm nguồn hoặc đề.
- [ ] **W04** — Implement/điều phối xuất Word công thức sửa được, PDF/HTML và bản học sinh/giáo viên, không gọi Node core.
- [ ] **W05** — Golden test round-trip và quyền download, báo rõ chart/shape/công thức OCR chưa giữ; tích hợp UI-2.

Mã bước/ca luôn đi cùng task, ví dụ BE-4-002/W01 và BE-4-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Nhập nguồn hai trang rồi xuất đề có công thức/bảng. | Metadata/locator giữ được, Word/PDF hợp lệ và tách teacher/student. |
| T02 | Lỗi/từ chối | File giả định dạng, quá lớn, hỏng hoặc khác owner. | Không parse vô hạn/ghi file mồ côi, lỗi rõ và không truy cập dữ liệu người khác. |
| T03 | Biên/đồng thời | OCR thiếu ký hiệu/nguồn chứa lệnh giả. | Giữ phần không chắc để duyệt; nội dung không trở thành chỉ dẫn hệ thống. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Document service Python, fixture expected, log extraction/export và ma trận định dạng thực đạt.

**Bên nhận bàn giao:** BE-1, BE-2, BE-3, UI-2. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R5, R6, R7; UC-02, UC-05, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-4-002 -->

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
<!-- mach-task-detail:BE-5-002 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Job/event contract và repo/API/AI interface đã review; cần service Python thật cho test tích hợp cuối.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Implement job state machine và giới hạn tài nguyên theo cấu hình đã chốt; persist owner/jobId/baseVersion.
- [ ] **W02** — Implement SSE/thứ tự/dedupe, status/reconnect và một terminal state; phối hợp UI-3/BE-1.
- [ ] **W03** — Implement cancellation/timeout/retry/idempotency, dọn tài nguyên và chặn commit kết quả muộn.
- [ ] **W04** — Test nhiều job theo giới hạn cấu hình, disconnect/duplicate/stale và startup recovery; đo trên fixture.
- [ ] **W05** — Nối pytest/contract/E2E vào CI không secret, ghi config và artifact sạch; không auto-deploy GreenNode.

Mã bước/ca luôn đi cùng task, ví dụ BE-5-002/W01 và BE-5-002/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Job chạy và UI reconnect nhận kết quả. | Cùng jobId/owner, thứ tự rõ, terminal state và revision khớp. |
| T02 | Lỗi/từ chối | Hủy/timeout rồi worker trả muộn. | Không commit đề; giải phóng tài nguyên, trạng thái nhất quán. |
| T03 | Biên/đồng thời | Vượt giới hạn cấu hình hoặc gửi retry/event trùng. | Từ chối/xếp hàng theo contract, không tạo side effect lặp hoặc hứa SLA chưa đo. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Job/SSE/cancel Python, test tích hợp/đồng thời và log giới hạn đo được, CI fixture.

**Bên nhận bàn giao:** BE-1, BE-2, BE-3, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R5, R6, R7, R8; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-5-002 -->

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
<!-- mach-task-detail:UI-1-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** UI/API Python lát tương ứng đã nối; có account fixture và candidate SHA, không dùng production data.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Tái chạy luồng kho/tài khoản/preference bằng Python API với Node API tắt.
- [ ] **W02** — Kiểm guest/member/admin, hết phiên, offline/conflict và kho rỗng/lỗi trên candidate.
- [ ] **W03** — Kiểm viewport hẹp, keyboard/focus/label và đường quay lại; nhờ người khác làm tác vụ từ hướng dẫn.
- [ ] **W04** — Ghi lỗi theo severity và sửa/retest từng issue; không dùng ảnh đẹp thay xác nhận dữ liệu.
- [ ] **W05** — Nộp ảnh/log/checklist và giới hạn cho BE-2/5 review; user study đi cùng CT-01/06 có consent.

Mã bước/ca luôn đi cùng task, ví dụ UI-1-003/W01 và UI-1-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Máy/context mới tạo→tìm→mở→đổi tên→reload đề. | Luồng thật vào Python, không dữ liệu fixture hardcode. |
| T02 | Lỗi/từ chối | Account B truy cập đường dẫn của A và session hết hạn khi soạn. | Không lộ kho/nháp; có cách đăng nhập lại an toàn. |
| T03 | Biên/đồng thời | Mobile và chỉ Tab trong kho rỗng/modal. | Không mất focus/CTA hoặc buộc dùng chuột cho thao tác chính. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Biên bản nghiệm thu UI kho/tài khoản theo SHA, ảnh/keyboard log và bug đã retest.

**Bên nhận bàn giao:** BE-2, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R6, R7, R8; UC-01, UC-03, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-1-003 -->

### UI-2-003 — Nghiệm thu editor đa môn và đối chiếu bản in

## Phân công

- Vai trò: **UI-2**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #10, #14, #15, #13

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
<!-- mach-task-detail:UI-2-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Editor nối lưu Python và import/export thật; baseline golden/ảnh trước có sẵn, candidate đã chốt SHA.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chạy ma trận Toán/Hóa/môn văn bản với phân số/hệ/ma trận/bảng/hình/ngữ liệu nhiều dòng.
- [ ] **W02** — Kiểm chọn/sửa/undo/reload, hai phiên conflict và tách bản học sinh/giáo viên.
- [ ] **W03** — Đối chiếu bằng mắt Word/PDF, thử sửa công thức trong Word; chưa có môi trường thì ghi pending và không tick.
- [ ] **W04** — Kiểm mobile/IME/keyboard, câu rất dài/bảng qua trang và ghi giới hạn paginate.
- [ ] **W05** — Retest bug, nộp fixture + ảnh expected/actual + consumer API đã kiểm cho reviewer.

Mã bước/ca luôn đi cùng task, ví dụ UI-2-003/W01 và UI-2-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Lưu/mở lại đề đa môn rồi xuất teacher/student. | RichDoc và bản in giữ nội dung, đáp án chỉ ở bản phù hợp. |
| T02 | Lỗi/từ chối | Lưu đồng thời hoặc chọn vùng không bảo toàn được. | Không mất bản trước, thông báo xử lý rõ. |
| T03 | Biên/đồng thời | Hai công thức trùng, bảng dài và IME tiếng Việt. | Đúng node/vùng; lệch in hoặc giới hạn được ghi bằng chứng, không che lỗi. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Ma trận editor/print đã đánh kết quả theo SHA, file synthetic đối chiếu và danh sách pending/bug.

**Bên nhận bàn giao:** BE-3, BE-4, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R6, R7, R8; UC-05, UC-06, UC-08, UC-09, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-2-003 -->

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
<!-- mach-task-detail:UI-3-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Chat/proposal/job Python đã tích hợp; fixture failure và candidate SHA thống nhất với BE-1/5.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chạy hỏi→đề xuất→diff→confirm→undo vào Python, đo vùng ngoài không thay đổi.
- [ ] **W02** — Chạy thiếu source/scope, response sai schema, stale version và source bị đổi giữa lúc job chạy.
- [ ] **W03** — Chạy cancel/retry/reconnect/trả muộn và prompt tiếp nối, kiểm không nhân đôi side effect.
- [ ] **W04** — Kiểm chat mobile/IME/cuộn/focus và lời người dùng khi error; reviewer dùng hướng dẫn để tái hiện.
- [ ] **W05** — Nộp log job/version sạch, ảnh diff và bảng fixture/model thật riêng cho BE-1/5.

Mã bước/ca luôn đi cùng task, ví dụ UI-3-003/W01 và UI-3-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Hỏi rồi sửa đúng bước barem và undo. | Hỏi không ghi đề; chỉ phần được duyệt đổi, undo khôi phục đúng cụm. |
| T02 | Lỗi/từ chối | Đề đổi khi đang chờ AI hoặc proposal chạm câu khác. | Apply bị chặn, bản mới của người dùng giữ nguyên. |
| T03 | Biên/đồng thời | Hủy sát event cuối rồi retry sau mất mạng. | Không áp kết quả muộn/lặp; không kẹt editor hoặc mất prompt. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Biên bản E2E trợ lý và error matrix, log scope/version/job, bug retest theo SHA.

**Bên nhận bàn giao:** BE-1, BE-5, BE-2. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R4, R5, R6, R7, R8; UC-04, UC-06, UC-07, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:UI-3-003 -->

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
<!-- mach-task-detail:BE-1-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** AI/Python/API/DB/document/job đã tích hợp; chỉ Thuận có quyền/cấu hình server. Fixture có thể hoàn tất trước, model thật còn thiếu phải ghi pending.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chốt provider/model/task/dataset/commit và ngưỡng đánh giá trước smoke; không dùng key cũ trong chat.
- [ ] **W02** — Chạy model thật trên mẫu được phép cho Sinh/Sửa/Kiểm, ghi chất lượng/evidence/lỗi và giới hạn.
- [ ] **W03** — Đối chiếu routing/consent/timeout/cancel/version và không fallback trả phí; phân biệt provider hoạt động với đáp án đúng.
- [ ] **W04** — Review runbook khôi phục/cấu hình/model/license/rollback; chỉ Thuận thực hiện thao tác hạ tầng khi quyết định sẵn sàng.
- [ ] **W05** — Bàn giao kết quả kỹ thuật cho BE-5; quyết định mở/đóng web là phê duyệt riêng của owner, không tự từ CI.

Mã bước/ca luôn đi cùng task, ví dụ BE-1-003/W01 và BE-1-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Model thật xử lý bộ mẫu đã chốt. | Lưu model/config không bí mật, input được phép, output và đánh giá; không suy độ đúng từ HTTP 200. |
| T02 | Lỗi/từ chối | Quota/timeout/refusal hoặc trích nguồn sai. | Không fallback ngầm/đánh dấu đúng; có lý do, dữ liệu gốc và đường khôi phục. |
| T03 | Biên/đồng thời | Không có GreenNode hoặc quyền provider. | Ghi bị chặn cho phần real-model; không lấy fixture làm bằng chứng hoàn tất. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Báo cáo model thật theo task/commit, error taxonomy và runbook owner; pending rõ nếu chưa có server/quota.

**Bên nhận bàn giao:** BE-5, BE-2, UI-3. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R4, R5, R7, R8; UC-03, UC-04, UC-06, UC-07, UC-09. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-1-003 -->

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
<!-- mach-task-detail:BE-2-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** API/auth/repository/document Python thật đã có, candidate và ma trận quyền đã chốt.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chạy ma trận guest/member/admin cho đề/nguồn/job/proposal/config/export/share và các ID khác owner.
- [ ] **W02** — Kiểm session cookie, logout/expiry, Origin/CSRF, input/file validation và lỗi không lộ thông tin.
- [ ] **W03** — Kiểm replay/confirm trùng/stale/đổi owner và transaction khi lỗi một phần.
- [ ] **W04** — Thử nguồn chứa lệnh giả và các thao tác bỏ qua UI; server vẫn enforce quyền/version/consent.
- [ ] **W05** — Review OpenAPI parity, bug/severity/giới hạn; chỉ đề nghị mở đăng ký trong phạm vi auth đã nghiệm thu.

Mã bước/ca luôn đi cùng task, ví dụ BE-2-003/W01 và BE-2-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Owner dùng full luồng và member dùng phần được phép. | API đúng contract và UI không cần bypass kiểm quyền. |
| T02 | Lỗi/từ chối | Đổi ID tài nguyên, dùng phiên đã logout hoặc payload không hợp lệ. | Từ chối phía Python, không trả data/file/secret của người khác. |
| T03 | Biên/đồng thời | Replay confirm, share bị thu hồi hoặc hết hạn nếu hỗ trợ. | Không ghi lặp/ghi cũ; link thu hồi mất quyền xem theo contract. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Ma trận quyền và negative tests theo SHA, OpenAPI khớp thực chạy, bug và quyết định phạm vi đăng ký.

**Bên nhận bàn giao:** BE-3, BE-5, UI-1. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R5, R6, R7, R8; UC-01, UC-02, UC-03, UC-04, UC-06, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-2-003 -->

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
<!-- mach-task-detail:BE-3-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Migration/repository Python đã có, fixture multi-owner/richDoc/file và runbook bản sao; không thao tác DB production.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Tạo backup nhất quán của DB fixture cùng manifest file/version/config schema không có secret.
- [ ] **W02** — Restore vào thư mục/DB mới, chạy integrity/record count/checksum và consumer smoke.
- [ ] **W03** — Diễn tập lỗi giữa migration, rollback và chạy lại; giữ bản cũ và ID/owner/revision.
- [ ] **W04** — Kiểm concurrent writes, source đổi version, xóa đề/file và liên kết snapshot theo quy tắc đã chốt.
- [ ] **W05** — Bàn giao lệnh/dataset/log và điều kiện rollback cho BE-5/Thuận; chưa diễn tập thật thì không tick production restore.

Mã bước/ca luôn đi cùng task, ví dụ BE-3-003/W01 và BE-3-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Restore backup fixture sang DB trống rồi mở/lưu/xuất. | Đúng số record/ID/owner/revision/nội dung và file tham chiếu đọc được. |
| T02 | Lỗi/từ chối | Backup thiếu file hoặc migration dừng nửa chừng. | Phát hiện thiếu/rollback an toàn, không tự nhận restore thành công. |
| T03 | Biên/đồng thời | Chạy restore/migration lại và hai writer ghi cạnh tranh. | Idempotent theo contract, không nhân bản hoặc ghi đè im lặng. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Biên bản backup→restore→verify trên bản sao, manifest/checksum và rollback có kết quả.

**Bên nhận bàn giao:** BE-2, BE-4, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R3, R6, R7, R8; UC-01, UC-02, UC-03, UC-06, UC-08, UC-09, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-3-003 -->

### BE-4-003 — Nghiệm thu tài liệu và bản xuất đa môn

## Phân công

- Vai trò: **BE-4**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P1
- Phụ thuộc: #15, #10, #13, #14

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
<!-- mach-task-detail:BE-4-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Import/export, API ownership và repository Python đã có; có bộ file hợp pháp và candidate SHA.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chạy ma trận định dạng/chữ Việt/công thức/bảng/hình/điểm, gồm hỏng/quá lớn và OCR không chắc.
- [ ] **W02** — Đối chiếu source locator/evidence sau import, sửa nguồn và import lại không làm sai trích dẫn cũ.
- [ ] **W03** — Mở file teacher/student bằng công cụ thực; kiểm OMML sửa được, hình/điểm/phân trang và không lộ ghi chú.
- [ ] **W04** — Kiểm download/auth/owner/share/revoke và cleanup khi lỗi bằng service Python thật.
- [ ] **W05** — Công bố file mẫu/expected/actual, giới hạn chart/shape/OCR và hướng dẫn giáo viên xem lại.

Mã bước/ca luôn đi cùng task, ví dụ BE-4-003/W01 và BE-4-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | DOCX/PDF/PPTX/ảnh hợp lệ qua import và xuất đề đa môn. | Nội dung/nguồn và bản in đạt kỳ vọng đã chốt, không mất dữ liệu ngầm. |
| T02 | Lỗi/từ chối | File sai owner/hỏng/quá lớn và export thất bại. | Từ chối đúng, không lộ file hay bỏ tài nguyên mồ côi. |
| T03 | Biên/đồng thời | Ngữ liệu nhiều dòng, bảng qua trang, OCR công thức sai. | Có kiểm lại/giới hạn rõ, không tự khẳng định nhận dạng chính xác. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Ma trận import/export đã đánh kết quả, file synthetic và ảnh kiểm trực quan, quyền file và bug retest.

**Bên nhận bàn giao:** UI-2, BE-2, BE-5. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R6, R7, R8; UC-02, UC-05, UC-10. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-4-003 -->

### BE-5-003 — Nghiệm thu candidate Python và báo cáo đồ án

## Phân công

- Vai trò: **BE-5**
- Thành viên: Chưa có username; nhận theo vai trò.
- Milestone: M3; ưu tiên: P0
- Phụ thuộc: #16, #17, #18, #19, #21, #22, #23, #20

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
<!-- mach-task-detail:BE-5-003 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Các task nghiệm thu UI/API/DB/document và BE-1-003 đủ bằng chứng; thiếu real-model phải giữ candidate pending, không tuyên bố hoàn tất.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chốt candidate SHA, môi trường/config và danh sách slice Python; tắt Node API khi chạy luồng chính.
- [ ] **W02** — Chạy regression/contract/E2E, quyền/phạm vi/job/restore/export và giới hạn tài nguyên đã chốt; lưu log sạch.
- [ ] **W03** — Đối chiếu R1–R8, 11 use case và CT-01…06; tách fixture/model thật/usability, so baseline và bug còn mở.
- [ ] **W04** — Tổng hợp source kế thừa/đóng góp từng người/AI hỗ trợ, báo cáo và demo từ clone sạch có người khác tái lập.
- [ ] **W05** — Review candidate/rollback và pending với nhóm, bàn giao owner duyệt phát hành riêng; không tự deploy/mua dịch vụ.

Mã bước/ca luôn đi cùng task, ví dụ BE-5-003/W01 và BE-5-003/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Người khác clone sạch, chạy Python và full luồng chính. | Không cần Node API hay key thật trong CI; output và source provenance tái lập được. |
| T02 | Lỗi/từ chối | Còn lỗi mất dữ liệu/quyền hoặc thiếu bằng chứng real-model. | Không release/đóng toàn task; ghi blocker/ngoại lệ cần owner quyết định. |
| T03 | Biên/đồng thời | CI xanh nhưng usability, Word hoặc restore chưa kiểm. | Mục đó vẫn pending, không dùng CI thay mọi tiêu chí nghiệm thu. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Biên bản candidate theo SHA, ma trận R/UC/CT có bằng chứng, known issues, hướng dẫn tái lập và gói báo cáo/demo.

**Bên nhận bàn giao:** BE-1, BE-2, UI-1. Bên nhận xác nhận artifact/contract dùng được; reviewer vẫn theo phân công task, chưa có username thì không tự gán người. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R2, R3, R4, R5, R6, R7, R8; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:BE-5-003 -->
