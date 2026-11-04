# Phân công 8 thành viên

**Core/API/database/AI/job/import-export chuyển sang Python/FastAPI. File Node trong bảng là nguồn tham chiếu; code backend mới đặt trong `backend/src/mach_backend/` và pytest trong `backend/tests/`.**

Đã xác nhận: Thuận thuộc 5 người backend. Các mã còn lại sẽ thay bằng username khi có đủ danh sách.

| Vai trò | Thành viên | Trách nhiệm và file chủ yếu | Đầu ra đầu tiên |
|---|---|---|---|
| UI-1 | Chưa có username | Shell, điều hướng, kho đề, tài khoản; `design.*`, `app.js` (phần shell), `assets/online-login.*` | Bản đồ màn hình + empty/loading/error states |
| UI-2 | Chưa có username | Editor, vùng chọn, công thức/bảng/hình; `editor*`, `composer*`, `pages.js`, catalog, CSS editor | Hồi quy lưu/undo/công thức trên fixture |
| UI-3 | Chưa có username | Chat, ngữ cảnh, diff, streaming; `workbench.js/css`, `studio.js/css`, `assets/usability.*` | Luồng chat/sửa với mock và hủy tác vụ |
| BE-1 | Thuận — `@ngocthuan1505` | AI orchestration, GreenNode, cấu hình provider; `ai.mjs`, `cloud-ai.mjs`, `greennode.mjs`, `server-kit/`, `ops/greennode/` | Hợp đồng AI và runbook; **người duy nhất thao tác server** |
| BE-2 | Chưa có username | HTTP/API, auth, phân quyền, validation; `mvp-server.mjs`, `accounts.mjs`, `deployment.mjs` | Danh mục API + test cách ly tài khoản |
| BE-3 | Chưa có username | Data model, repository, version, migration/backup; `backend-store.mjs`, `storage.js`, thiết kế schema | ERD/ADR dữ liệu và fixture migration không mất dữ liệu |
| BE-4 | Chưa có username | Import/OCR/Word/PDF và file ownership; `importers.mjs`, `word-import.mjs`, `exports.mjs`, `math-word.mjs` | Bộ tài liệu mẫu hợp lệ/hỏng và ma trận hỗ trợ |
| BE-5 | Chưa có username | CI, tích hợp job/SSE, giới hạn tài nguyên, QA backend; `tests/`, workflow, phần job trong `workbench-server.mjs` | Baseline CI, checklist release và integration tests |

Đích Python: BE-1 giữ AI service/validation, BE-5 giữ job/SSE/cancel; BE-3 giữ repository, BE-4 giữ document service.

BE-1 và BE-5 cùng đọc `workbench-server.mjs`: BE-1 giữ prompt/provider/validation AI, BE-5 giữ transport job/cancel/SSE. Không cùng sửa file trong hai PR chưa phối hợp. BE-2 là người điều phối router FastAPI và hợp đồng HTTP; `mvp-server.mjs` chỉ tham chiếu; các nhóm khác đóng góp helper/test trước.

UI-1/UI-2/UI-3 phối hợp layout chung; không ghi đè toàn bộ stylesheet của nhau. Schema/API thay đổi phải ghi trong issue và được người dùng module review.

**Task mở đầu:** mỗi người nhận issue có mã `<vai-trò>-001`. Các task `002/003` có phụ thuộc trong [BACKLOG](BACKLOG.md), không cần chờ GreenNode để làm UI/API/database/QA.

**Đầu ra môn chung:** UI-1 điều phối CT-01 (Problem Brief), BE-5 CT-02 (WBS), BE-3 CT-03 (model/contracts), Thuận BE-1 CT-04 (PoC), BE-2 CT-05 (thuật toán), BE-5 CT-06 (đánh giá/báo cáo). Các vai trò khác đóng góp bằng chứng theo module, không giao cả báo cáo cho một người viết thay. Xem [yêu cầu, nguồn và link issue CT](../course/README.md).
