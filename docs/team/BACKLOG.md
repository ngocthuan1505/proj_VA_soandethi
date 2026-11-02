# Backlog nhóm — 24 task

Nguồn duy nhất: [tasks.json](tasks.json); danh sách thành viên: [roster.json](roster.json). Các task là việc cần làm, không phải chức năng đã hoàn thành. Mốc không có deadline cho đến khi nhóm chốt.

**Bảng công việc:** [Ready](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Aready) · [Doing](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Adoing) · [Review](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Areview) · [Blocked](https://github.com/ngocthuan1505/proj_VA_soandethi/issues?q=is%3Aissue+is%3Aopen+label%3Astatus%3Ablocked) · [Milestones](https://github.com/ngocthuan1505/proj_VA_soandethi/milestones)

Dùng Issues + nhãn trạng thái làm bảng chung, không phụ thuộc Project trả phí. Status/assignee thực tế xem trên GitHub.

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

## Kiểm tra

Chạy npm test; đính kèm wireframe/ảnh và checklist phím Tab.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

npm test; node tests/selection-browser.mjs và ảnh fixture.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

node tests/usability-browser.mjs; ghi danh sách state/event.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

node --test tests/greennode.test.mjs tests/cloud-ai.test.mjs; không dùng key thật.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

npm test; thêm fixture response và negative auth cases còn thiếu.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Tạo fixture migration kiểm đếm, FK/ownership dự kiến và golden snapshot.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

npm test; dùng fixture không bản quyền/không dữ liệu cá nhân.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

CI thật xanh và một bộ UI fixture chạy local.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

UI fixture + kiểm thử tài khoản cùng BE-2; không dùng tài khoản thật trong CI.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

selection/authoring/curriculum browser fixtures; npm test.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

workbench/selection/studio fixtures; tích hợp job với BE-5.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Fixture success/malformed/timeout/wrong-id/duplicate, model thật chỉ Thuận chạy khi sẵn sàng.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Negative integration tests cho guest/member/admin, XSS/origin/host và ID không thuộc tài khoản.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Migration twice, rollback failure, two-user isolation và golden richDoc/formula.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Fixtures hợp lệ/hỏng; kiểm nội dung và render Word/PDF mẫu khi có công cụ.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Pytest cho phần Python mới + đối chiếu golden fixture từ Node cũ. Stream ngắt giữa chừng, hai user, lặp submit, timeout và process restart với fixture.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Checklist UX cùng UI-2/3 và test phiên hết hạn.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Golden mẫu tự tạo, reload/undo/export và kiểm bằng mắt.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Các luồng malformed/timeout/stale/version/conflict với BE-5.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Smoke model thật có timeout/cancel + release checklist; không lấy danh sách model làm bằng chứng suy luận.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Negative auth matrix, upload/export/share ownership, origin/host và logout.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Restore drill fixture, replay revision conflicts và diễn tập nâng/hạ version.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Golden DOCX/PDF + fixture import hỏng và giới hạn dung lượng.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.

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

## Kiểm tra

Chạy E2E với FastAPI và không chạy Node API. Full suite + manual checklist và kiểm source không có secret/runtime.

Đọc [quy trình nhóm](https://github.com/ngocthuan1505/proj_VA_soandethi/blob/main/docs/team/README.md). Chỉ Thuận thao tác GreenNode; nhóm khác dùng fixture, không nhận URL/token. File dùng chung cần hẹn người giữ file trước PR.
