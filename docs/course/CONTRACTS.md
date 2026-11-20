# Mô hình và hợp đồng cần chốt

Trạng thái: **đã có mô hình Abstraction, UML, Schema, ADT và Interface của nhóm** trong [Docs bài chính](https://docs.google.com/document/d/1aPbp3jybeoFp9i9B5i2bilZhTqHkqRgkJvQZ8MZ_hkU/edit?tab=t.u9x5d9udf8y9). Dùng lại sáu đối tượng và SessionContext, bảng QuestionVersion 7 trường, changes/keep, ProposeReplaceQuestion/ConfirmProposal và ISourceReader như [bản đối chiếu](HO_SO_DA_CO.md). Phần còn lại là ánh xạ sang DTO/OpenAPI/DB Python có review và test, chưa phải bắt đầu thiết kế từ trang trắng. Nguồn phương pháp: Topic 3 trang 18; Topic 4 trang 22–24, 30–34. BE-3 giữ [đề xuất dữ liệu](../architecture/DATA_PLAN.md); BE-2 giữ OpenAPI của FastAPI.

| Khái niệm | Thông tin cần thống nhất | Bất biến cần kiểm |
|---|---|---|
| Đề/phiên bản | UUID, owner, revision, nội dung richDoc, môn/lớp, điểm | ID và công thức không đổi khi round-trip; quyền theo tài khoản; quy tắc tăng revision rõ |
| Phạm vi sửa | ID câu/khối, revision gốc, đoạn chọn và giới hạn | Không diễn giải mơ hồ “câu này”; không sửa ngoài danh sách cho phép |
| Job AI | ID, owner, trạng thái enum, revision gốc, timeout, nguồn model | Kết quả đúng job/version; cancel không áp output muộn; fixture khác model thật |
| Tài liệu/nguồn | ID, owner, MIME/size, trang, trạng thái OCR, nguồn được phép | File quá lớn/hỏng bị từ chối; không dùng text OCR như dữ kiện đã được duyệt |
| Bản xuất | đề/version, chế độ học sinh/giáo viên, owner, định dạng | Bản học sinh không chứa đáp án; quyền download kiểm phía server |

Mỗi field trong schema thật cần tên, kiểu, bắt buộc/null, đơn vị hoặc format, giới hạn, ví dụ hợp lệ/lỗi. Đặc biệt điểm dùng biểu diễn chính xác theo ADR; thời lượng ghi đơn vị; timestamp thống nhất múi giờ/format; enum job dùng cùng một tập giá trị giữa UI/API/DB.

## Đối chiếu QuestionVersion với nhánh tích hợp FastAPI

| Trường trong Abstraction | Trường trên bàn soạn và API | Kiểu và bất biến |
|---|---|---|
| `questionId` | Câu lưu `id`, job sửa nhận `targets[].questionId` | UUID, giữ khi sửa cùng câu. Thứ tự hiển thị có thể đổi. |
| `versionId` | Câu lưu `v`, job sửa nhận `questionVersion` | Số nguyên ≥ 1. `baseRevision` là phiên bản cả đề. Hai số đều phải khớp snapshot khi áp sửa. |
| `content` | `stem`, `options`, `answer`, `explanation`, `rubric` và tài liệu richDoc nếu có | Cấu trúc và kiểu đáp án phụ thuộc dạng câu. Điểm truyền ở ma trận/sinh đề là `pointsQ4` nguyên, 1 đơn vị bằng 0,25 điểm. |
| `questionType` | `type` | `mcq`, `truefalse`, `short` hoặc `essay`. Tool check giữ dạng tương ứng với ô ma trận. |
| `evidence` | `Evidence` trong kết quả | Mỗi mục có `sourceId` UUID, `sourceVersion` nguyên ≥ 1, `locator` và `quote`. Danh sách có thể rỗng khi yêu cầu cho phép làm không kèm nguồn. |
| `verificationStatus` | Trạng thái kiểm trên câu | Khi nội dung thay đổi, Python đưa về `unverified`. Kết quả lượt kiểm được ghi ở báo cáo theo job. |
| `approvalStatus` | Trạng thái duyệt trên câu | Khi nội dung thay đổi, Python đưa về `draft`. Trạng thái của cả đề nằm ở `draftStatus`. |

Các DTO định nghĩa phiên bản, vùng, căn cứ và các giới hạn trường trong [ai_contract.py](../../backend/src/mach_backend/ai_contract.py) và [ai_questions.py](../../backend/src/mach_backend/ai_questions.py). Bàn soạn hiện giữ đề trong SQLite KV và lưu đề xuất/biên nhận ở `matrix_pending`, nhật ký ở `matrix_trace`. Xem [workspace_store.py](../../backend/src/mach_backend/workspace_store.py). ERD 15 bảng là schema đích của bộ migration, có từ điển riêng. [Từ điển dữ liệu và migration](../contracts/du-lieu.md)

### Ba đường kiểm của CT-03

| Ca | Đầu vào → kết quả mong đợi | Kiểm thử trên nhánh tích hợp |
|---|---|---|
| T01 · Phiên bản và đề xuất | Sinh từ revision 1, kết quả qua kiểm ở trạng thái `complete`. Sau khi giáo viên xác nhận bằng `{"baseRevision":1,"teacherConfirmation":true}`, SQLite ghi revision 2, biên nhận và lịch sử. Đọc lại sau khi mở app giữ kết quả đã lưu. | `test_agent_preview_survives_app_restart` trong [test_local_workspace.py](../../backend/tests/test_local_workspace.py) và [hợp đồng confirm](../contracts/ai.md#xác-nhận-lưu-đề-mới) |
| T02 · Phiên bản cũ hoặc nguồn thiếu vị trí | Job hết hiệu lực khi đề/nguồn đổi. Xác nhận lại có thể trả `409 stale_snapshot`. Nguồn cần locator có loại `page`, `passage` hoặc `region` và chỉ số từ 1. Thiếu locator bị lỗi cấu trúc. | `test_http_submit_refuses_invalid_scope_source_or_consent` trong [test_patch_confirmation.py](../../backend/tests/test_patch_confirmation.py) và [kiểm nguồn](../../backend/src/mach_backend/ai_sources.py) |
| T03 · Cấu trúc editor | Câu có nhiều nút công thức hoặc vùng chọn trong bảng. Giữ ID công thức khi thay đúng thứ tự, chặn ghép qua hai ô khác nhau và báo vùng không rõ nếu công thức đổi chỗ. | `test_formula_ids_survive_multiple_updates_but_reordering_is_ambiguous` và `test_editor_change_cannot_merge_distinct_table_cells` trong [test_poc_scoped_patch.py](../../backend/tests/test_poc_scoped_patch.py) |

Hồ sơ giữ ID, phiên bản, nội dung có cấu trúc và căn cứ vì chúng quyết định có được áp sửa. Đồng biên tập thời gian thực vẫn ngoài phạm vi. Fixture dùng mã và nguồn tự viết để tái lập kiểm thử. Còn cần BE-2, BE-3 và phía dùng hợp đồng review cách ánh xạ với slide và quyết định thời điểm chuyển schema đích.

### Bộ tài liệu hợp đồng chi tiết & kiểm chứng ở `8d37a0f` (`codex/ban-thu-13`)

| Phạm vi / Mã bàn giao | Tài liệu chi tiết đã đối chiếu mã nguồn | Bằng chứng kiểm thử bổ sung ở `8d37a0f` (`[Hiện có / Đã chạy bằng Python]`) | Phần còn mở (`[Chờ review nhóm / Thành viên xác nhận]`) |
|---|---|---|---|
| `C01` Auth / Ownership / HTTP / CSRF | [Hợp đồng HTTP](../contracts/http.md) · [Luồng màn hình](../design/luong-man-hinh.md) | `test_team_permission_matrix_session_expiry_logout_csrf_and_context` ([test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py)) kiểm `guest`/`member`/`admin`, `SESSION_SECONDS`, `X-Workspace-Context` `409`, `Origin` `403`. | Chốt bắt buộc header `If-Match` cho `PUT /api/kv?key=state` và thống nhất một envelope lỗi JSON chung. |
| `C02` Dữ liệu / ERD / Di trú KV → SQL | [Hợp đồng dữ liệu](../contracts/du-lieu.md) · [Editor & richDoc](../design/editor-va-richdoc.md) | `test_workspace_store_migrates_preserving_uuids_richdoc_files_idempotent_and_rollback` ([test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py)) kiểm di trú từ `WorkspaceStore` sang schema quan hệ giữ UUID, `richDoc`, `formulas`, `blockIds`, hash file nguồn, idempotency và rollback. | BE-2/BE-3/UI-2 chốt thời điểm nối repository 15 bảng thay thế `key="state"`. |
| `C03` & `C06` Tài liệu / OCR / Xuất HS-GV | [Hợp đồng tài liệu](../contracts/tai-lieu.md) | `test_disguised_files_cleanup_multipage_pdf_and_student_zero_leakage` ([test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py)) kiểm giả đuôi `.docx`/`.pdf` hỏng/quá `15 MiB` không tạo rác kho, đọc PDF 2 trang, và tách sạch đáp án/barem/chat khi xuất HTML & Word; gói `ung-vien-48` xuất 4 tệp Word/PDF thật không cần Node. | Thống nhất trần `15 MiB` (BE-4) với `20 MiB` di trú cũ (BE-3) và đối chiếu trực quan Word/PDF trên máy thành viên khác. |
| `C04` Job / SSE `patch` / Ngưỡng | [Hợp đồng Job & SSE](../contracts/job-va-sse.md) · [Trợ lý và Job](../design/tro-ly-va-job.md) | `test_sse_last_event_id_dedupe_and_near_commit_cancel` và `test_job_runner_timeout_emits_single_monotonic_terminal_state` ([test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py)) kiểm `Last-Event-ID`, `429 job_limit`, `cancel` sát `publish` và timeout monotonic (`sequence=2`). | Chuyển `matrix-synthesis.js` từ polling `1000ms` sang SSE `GET .../events`, chốt giữ hay bỏ `"cancelling"` trên wire, bảo toàn phần `W01` của `PhuQuang0307`. |
| `C05` & `C07` AI Sinh / Sửa / Kiểm mù | [Hợp đồng AI](../contracts/ai.md) | `test_prompt_injection_and_missing_consent_or_provider` ([test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py)), [test_sample_exam_8b.py](../../backend/tests/test_sample_exam_8b.py) (`1/1`), [test_check_routes.py](../../backend/tests/test_check_routes.py) (`40 passed, 1 skipped` chạy riêng). | Hợp nhất 2 nhánh route (`local_workspace` / `poc_scoped_patch` với `ai_routes` / `patch_routes`) và review trần timeout chung. |

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
