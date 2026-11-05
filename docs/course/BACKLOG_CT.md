# Chi tiết sáu task hồ sơ môn

Dùng lại [hồ sơ đã có](HO_SO_DA_CO.md). Đây là bước cần làm tiếp, không đặt lại tiến độ/assignee hoặc coi hồ sơ đã làm là chưa có. Nguồn: deliverables.json; sinh bằng node scripts/check-team.mjs --write.

## CT-01 — Kiểm chứng vấn đề với 3 người dùng và chốt Problem Brief/baseline

[Issue #26](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/26) · Mảng điều phối gợi ý (nhóm tự chọn người): UI-1; phối hợp theo contract: UI-2, UI-3, BE-2. Phụ thuộc hồ sơ: Không.

[Hồ sơ làm việc](PROBLEM_BRIEF.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] Có ghi chép được phép từ ít nhất 3 người dùng thật, ẩn danh; không bịa số liệu.
- [ ] Problem Brief một trang đủ stakeholder, nguyên nhân, input/output/constraints, MoSCoW và metrics/ngày cần xác nhận.
- [ ] Đối chiếu 2–3 công cụ bằng cùng tác vụ, ghi khoảng trống và nguồn/ngày kiểm.
- [ ] Nhóm review và ghi điều chưa xác minh; chưa coi bản nháp hiện tại là kết quả phỏng vấn.

<!-- mach-task-detail:CT-01 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Đọc proposal/baseline đã có; cần người dùng được phép tham gia, không bắt đầu lại nội dung đã viết.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Đánh dấu phần proposal đã có và các giả định chưa kiểm; dùng 11 use case để chọn tác vụ khảo sát.
- [ ] **W02** — Chuẩn bị câu hỏi và consent, ghi chép ẩn danh ít nhất ba người dùng thật; không tải bản ghi riêng lên repo.
- [ ] **W03** — Làm cùng tác vụ trên 2–3 công cụ theo quyền sử dụng, ghi cách đo/nguồn/ngày và giới hạn so sánh.
- [ ] **W04** — Hoàn thiện Problem Brief/MoSCoW/non-goals/metrics; phân biệt mục tiêu với số đo đã có.
- [ ] **W05** — Review với nhóm, ghi thay đổi do bằng chứng và lịch/thông báo lớp còn cần Thuận xác nhận.

Mã bước/ca luôn đi cùng task, ví dụ CT-01/W01 và CT-01/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Có bằng chứng ba người dùng và một tác vụ đại diện. | Claim vấn đề/tiêu chí truy được nguồn và dữ liệu thực. |
| T02 | Lỗi/từ chối | Chưa có phỏng vấn hoặc không được phép lưu nội dung. | Giữ pending/ẩn danh phù hợp; không bịa transcript hoặc số đo. |
| T03 | Biên/đồng thời | Ý kiến người dùng mâu thuẫn hoặc benchmark thiếu chức năng. | Ghi phân nhóm/giới hạn và quyết định scope, không chọn số thuận lợi. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Problem Brief đã review, ghi chép ẩn danh/consent summary và bảng baseline cùng tác vụ.

**Mảng cần bàn giao:** BE-5, BE-3, UI-3. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R8; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-01 -->

## CT-02 — Chốt cây phân rã 3 cấp, pattern và kế hoạch làm việc

[Issue #27](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/27) · Mảng điều phối gợi ý (nhóm tự chọn người): BE-5; phối hợp theo contract: UI-1, BE-2, BE-3. Phụ thuộc hồ sơ: CT-01.

[Hồ sơ làm việc](WBS.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] Cây vấn đề→chức năng→lá có owner, pattern, công cụ và done-when; chỉ ra lá rủi ro nhất.
- [ ] Liên kết 24 gói task với lá, tách bước quá khoảng một ngày thành issue nhỏ có tiêu chí nghiệm thu.
- [ ] Phụ thuộc không trùng việc, đầu ra ghép được; Kanban cập nhật thật.
- [ ] Thuận xác nhận lịch môn trước đặt deadline; có kế hoạch tương đối/WBS chờ chốt ngày.

<!-- mach-task-detail:CT-02 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có cây Decomposition–Pattern 23 slide; dùng kết quả CT-01 hiện có và ghi giả định nếu khảo sát còn pending.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Đối chiếu cây ba cấp/bảy module/bốn pattern đã có với source demo, không vẽ lại tùy ý.
- [ ] **W02** — Gắn từng lá vào task/vai trò, input/output và tiêu chí kiểm được; ghi phụ thuộc cứng với hợp đồng mềm.
- [ ] **W03** — Dùng Wxx để chia PR; bước quá khoảng một ngày thì tạo issue con có cha/đầu ra/test và thêm bảng.
- [ ] **W04** — Chọn lá rủi ro nhất cho CT-04, ghi lý do/trade-off và phương án dự phòng.
- [ ] **W05** — Review gates M1/M2/M3, lượng việc mỗi người, ngày nộp do lớp xác nhận và quyết định chưa chốt.

Mã bước/ca luôn đi cùng task, ví dụ CT-02/W01 và CT-02/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Theo một lá từ nhu cầu tới task, output và test. | Không có lá chính vô chủ hoặc output không có consumer. |
| T02 | Lỗi/từ chối | Hai nhóm cùng sửa file/API hoặc phụ thuộc thành vòng. | Nêu owner/contract, tách scope và sửa kế hoạch trước triển khai. |
| T03 | Biên/đồng thời | Một bước lớn hoặc server chưa có. | Tách issue con; công việc fixture/thiết kế vẫn có đường tiến, không giả deadline. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** WBS/pattern giữ nguồn cũ, mapping task/lá/owner/phụ thuộc, quyết định PoC và lịch chờ chốt.

**Mảng cần bàn giao:** UI-1, BE-2, BE-3. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R2, R5, R6; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-02 -->

## CT-03 — Chốt mô hình dữ liệu và hợp đồng để các phần ghép được

[Issue #28](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/28) · Mảng điều phối gợi ý (nhóm tự chọn người): BE-3; phối hợp theo contract: BE-2, BE-1, BE-4, UI-2. Phụ thuộc hồ sơ: CT-02.

[Hồ sơ làm việc](CONTRACTS.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] ERD/data dictionary đủ field/type/unit/nullability/ID/version; phân biệt schema cũ và đề xuất.
- [ ] Contract input/output/rules/examples/errors cho API và job có fixture dùng chung.
- [ ] Quyết định giữ/defer/bỏ có lý do theo mục tiêu, nêu giả định AI/API.
- [ ] BE-2/3 và người dùng contract review; chưa coi ví dụ DTO là code đã chạy.

<!-- mach-task-detail:CT-03 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Đã có UML/Schema/ADT/Interface; cần các owner dữ liệu/API/source/job review phần mở rộng cho code.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Kế thừa sáu entity/SessionContext, kiểm field/type/unit/ID/version/status và chỗ draftStatus chưa đồng bộ.
- [ ] **W02** — Đối chiếu schema văn bản với richDoc/file/evidence thực của demo; ghi giữ/defer/bỏ có lý do.
- [ ] **W03** — Chốt contract input/output/pre/postcondition/invariant/errors/examples và ownership với consumer.
- [ ] **W04** — Tạo ví dụ valid/invalid/stale/ngoài vùng và nối tới pytest/golden fixture cần implement.
- [ ] **W05** — Review model↔OpenAPI↔repository↔slide, ghi version và chỗ chưa nghiệm thu, không sửa slide ngầm.

Mã bước/ca luôn đi cùng task, ví dụ CT-03/W01 và CT-03/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Trace QuestionVersion/proposal từ model tới contract. | ID/revision/status/evidence cùng nghĩa và có ví dụ kiểm được. |
| T02 | Lỗi/từ chối | Một nguồn không có locator hoặc patch sai baseVersion. | Precondition/error rõ; không confirm thành công giả. |
| T03 | Biên/đồng thời | RichDoc có node mà schema văn bản không biểu diễn. | Bổ sung/giới hạn được nêu, không làm phẳng rồi mất công thức/bảng. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Model/data dictionary/ADT/interface đã version, ví dụ DTO/fixture và log review consumer.

**Mảng cần bàn giao:** BE-2, BE-1, BE-4, UI-2. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R3, R5, R7; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-03 -->

## CT-04 — Chạy PoC sửa đúng vùng có bằng chứng và kết luận

[Issue #29](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/29) · Mảng điều phối gợi ý (nhóm tự chọn người): BE-1; phối hợp theo contract: UI-3, BE-5, BE-2, UI-2. Phụ thuộc hồ sơ: CT-02, CT-03.

[Hồ sơ làm việc](POC.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] Chọn một câu hỏi rủi ro và chốt dữ liệu/tool/steps/ngưỡng trước chạy.
- [ ] Có bộ mẫu hợp pháp và kết quả fixture/script chạy lại được gồm ca sai schema/stale/ngoài vùng/cancel.
- [ ] Tách kết quả model thật với fixture; thiếu server ghi chờ phần model thật, không dùng danh sách model làm bằng chứng.
- [ ] Kết luận yes/no/chưa đủ bằng chứng và hướng sửa, có người review độc lập.

<!-- mach-task-detail:CT-04 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Câu hỏi rủi ro và contract đã chốt, dữ liệu synthetic được phép; model thật cần Thuận/cấu hình, không bắt các thành viên vào server.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Viết giả thuyết một câu và ngưỡng pass/fail/chưa đủ trước chạy; chốt input/output và môi trường.
- [ ] **W02** — Chuẩn bị fixture đúng/sai schema/stale/quá vùng/cancel và expected; nguồn có provenance.
- [ ] **W03** — Chạy script lặp lại đúng commit, lưu kết quả từng mẫu và lỗi; tách hoàn toàn model thật khỏi fixture.
- [ ] **W04** — Khi Thuận có model hợp lệ, thử mẫu được phép và đánh giá theo rubric đã chốt; chưa có thì ghi pending.
- [ ] **W05** — Reviewer độc lập kết luận giữ/sửa/bỏ/chưa đủ và tác động tới kiến trúc/task tiếp theo.

Mã bước/ca luôn đi cùng task, ví dụ CT-04/W01 và CT-04/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Người khác chạy lại PoC fixture theo tài liệu. | Cùng kỳ vọng kiểm chứng và log theo mẫu; số đo ghi đúng môi trường. |
| T02 | Lỗi/từ chối | Proposal sai schema/ngoài vùng hoặc worker bị hủy. | Đề giữ nguyên; lỗi được tính vào kết quả thay vì bỏ khỏi mẫu. |
| T03 | Biên/đồng thời | Thiếu model/server hoặc mẫu quá ít. | Kết luận chưa đủ cho claim tương ứng, không suy từ fixture thành real-AI pass. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Hồ sơ PoC giả thuyết/dataset/threshold/command/results/conclusion và phần real-model riêng.

**Mảng cần bàn giao:** UI-3, BE-5, BE-2. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R3, R4, R5, R7, R8; UC-04, UC-06, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-04 -->

## CT-05 — Trình bày thuật toán, flowchart, dry run và phân tích chi phí

[Issue #30](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/30) · Mảng điều phối gợi ý (nhóm tự chọn người): BE-2; phối hợp theo contract: BE-5, BE-1, BE-3. Phụ thuộc hồ sơ: CT-03.

[Hồ sơ làm việc](ALGORITHM.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] Pseudocode và flowchart đủ input/output, điều kiện dừng, nhánh lỗi, quyền/version/consent.
- [ ] Trace ít nhất ca đúng, stale, ngoài vùng và cancel; khớp test Python thật.
- [ ] Phân tích chi phí/bộ nhớ và đo fixture nếu tuyên bố tối ưu; không bịa benchmark.
- [ ] Giải thích phần quy tắc cố định so với AI xác suất, hạn chế và trách nhiệm khi sai.

<!-- mach-task-detail:CT-05 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có ADT/interface và source baseline; chọn thuật toán Python thật cần chứng minh, không chỉ viết lại pseudocode interface.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chọn một luồng minh bạch như validate/apply proposal hoặc đối chiếu ma trận; nêu input/output/invariant.
- [ ] **W02** — Viết pseudocode/flowchart có nhánh quyền/version/consent/lỗi và điều kiện dừng; link implementation Python.
- [ ] **W03** — Dry-run đúng/stale/quá vùng/cancel với state trước-sau và expected; đối chiếu pytest thực.
- [ ] **W04** — Phân tích chi phí theo biến n/k cụ thể, đo nếu tuyên bố tối ưu; phân biệt rule xác định với AI xác suất.
- [ ] **W05** — Review trace/model/code/test, ghi counterexample/giới hạn và trách nhiệm khi AI sai.

Mã bước/ca luôn đi cùng task, ví dụ CT-05/W01 và CT-05/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Trace ca hợp lệ từ input tới state sau. | Pseudocode, Python và expected khớp invariants. |
| T02 | Lỗi/từ chối | Stale hoặc patch chạm câu ngoài scope. | Nhánh từ chối rõ, không đổi state kể cả lỗi giữa transaction. |
| T03 | Biên/đồng thời | Đầu vào rỗng/lớn hoặc hủy sát commit. | Có điều kiện dừng/chi phí và bằng chứng, không tuyên bố O(1) tùy tiện. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Pseudocode/flowchart, bảng dry-run, phân tích chi phí có giả định và pytest theo SHA.

**Mảng cần bàn giao:** BE-1, BE-3, BE-5. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R2, R5, R7, R8; UC-06, UC-07, UC-08. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-05 -->

## CT-06 — Đánh giá prototype/MVP và chuẩn bị báo cáo, demo cuối

[Issue #31](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/31) · Mảng điều phối gợi ý (nhóm tự chọn người): BE-5; phối hợp theo contract: UI-1, UI-2, UI-3, BE-1, BE-2, BE-3, BE-4. Phụ thuộc hồ sơ: CT-01, CT-04, CT-05.

[Hồ sơ làm việc](EVALUATION.md) · [Phần đã có](HO_SO_DA_CO.md)

### Acceptance giữ nguyên

- [ ] Có bằng chứng concept/value, functional, usability và accessibility; ghi cỡ mẫu, commit/môi trường và giới hạn.
- [ ] Feedback log có vấn đề, bằng chứng, mức độ, proposed fix và kết quả kiểm lại.
- [ ] Nêu giữ/sửa/bỏ, trade-off, phương án khác và mục tiêu vòng sau; không còn blocker trong phạm vi demo mới đề nghị xong.
- [ ] Báo cáo/demo có truy vết CT-01…06, đóng góp từng người, source kế thừa/AI và bước chạy lại; lịch/nộp theo xác nhận lớp.

<!-- mach-task-detail:CT-06 -->
## Chỉ dẫn chi tiết và bàn giao

**Điều kiện bắt đầu:** Có baseline kỹ thuật và các hồ sơ thiết kế; cần kết quả người dùng/model/candidate thật để nghiệm thu các claim tương ứng.

### Việc nhỏ có thể nhận và review

- [ ] **W01** — Chốt rubric/metrics/dataset và consent cho functional/value/usability/accessibility; ghi sample size, môi trường và SHA.
- [ ] **W02** — Chạy bộ test/quan sát tác vụ, ghi expected/actual và error taxonomy; không đồng nhất CI xanh với người dùng dùng tốt.
- [ ] **W03** — Chọn ít nhất một vấn đề có bằng chứng, sửa và đo/kiểm lại cùng tác vụ; giữ trước/sau và giới hạn.
- [ ] **W04** — Tổng hợp R1–R8/CT/UC, đóng góp/issue/PR/source kế thừa/AI hỗ trợ và quyết định giữ/sửa/bỏ.
- [ ] **W05** — Review báo cáo/demo/reproduction từ máy khác; chốt mục pending, thông báo lớp và rủi ro chưa xử lý.

Mã bước/ca luôn đi cùng task, ví dụ CT-06/W01 và CT-06/T01. Checklist chưa tick không nói phần demo cũ chưa có; đây là việc cần kiểm/hoàn thiện cho task này. Bước quá khoảng một ngày thì tách issue con, giữ link cha và tiêu chí kiểm.

### Ca kiểm tra và kết quả mong đợi

| Ca | Loại | Thao tác/điều kiện | Kết quả phải chứng minh |
|---|---|---|---|
| T01 | Đúng | Một tác vụ có baseline, cải tiến và lần kiểm lại. | Kết luận dựa dữ liệu cùng cách đo, không chỉ ảnh slide đẹp hơn. |
| T02 | Lỗi/từ chối | Thiếu người dùng/model hoặc còn bug mất dữ liệu. | Claim tương ứng pending/không đạt, không báo hoàn thành toàn bộ. |
| T03 | Biên/đồng thời | Mẫu ít, kết quả trái chiều hoặc cải tiến gây regression. | Ghi giới hạn/trade-off và quyết định giữ/sửa/bỏ có lý do. |

Đây là test **cần chạy**, không phải kết quả đã đạt. Log phải nêu commit/môi trường/fixture và expected/actual; tách review, test tự động, model thật và người dùng thật.

**Đầu ra cụ thể:** Gói đánh giá trước-sau, feedback/error log, báo cáo/demo/đóng góp và bảng truy vết bằng chứng.

**Mảng cần bàn giao:** BE-1, UI-1, BE-2. Nhóm chọn người/nhóm nhận bàn giao và xác nhận contract dùng được; không suy username từ mã mảng. Đường dẫn artifact ghi “đề xuất” là nơi sẽ tạo trong PR, chưa phải file đã có.

**Truy vết:** R1, R2, R3, R4, R5, R6, R7, R8; UC-01, UC-02, UC-03, UC-04, UC-05, UC-06, UC-07, UC-08, UC-09, UC-10, UC-11. [Use case và phạm vi](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/product/USE_CASES.md) · [Test tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/testing/KIEM_THU_TICH_HOP.md) · [Hợp đồng/gates/quyết định](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/KE_HOACH_TICH_HOP.md).

Acceptance gốc và bằng chứng đã có vẫn được giữ. Không tự tick/đóng task, không coi gói kế hoạch này là code đã chạy hoặc phê duyệt triển khai.
<!-- /mach-task-detail:CT-06 -->
