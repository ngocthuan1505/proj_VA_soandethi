# Quyết định: Python là ngôn ngữ chính

Nguồn yêu cầu: ảnh trao đổi quy định môn học do Thuận cung cấp ngày 02/11/2026: Python là ngôn ngữ chính, ngôn ngữ khác hỗ trợ, framework được chọn. Cần đối chiếu rubric chi tiết với giảng viên; không suy diễn một tỉ lệ phần trăm dòng code.

## Phân biệt hiện trạng và đích đến

| Phần | Hiện trạng | Đích nghiệm thu |
|---|---|---|
| Frontend/editor | JavaScript, TipTap/MathLive/KaTeX | Giữ làm UI hỗ trợ, gọi API Python |
| API/auth | Node `mvp-server.mjs`, `accounts.mjs` | Python/FastAPI, kiểm quyền phía server |
| Database | SQLite KV trong Node | Python repository/transaction/migration theo ADR BE-3 |
| Core đề/patch/phiên bản | JS domain + Node orchestration | Server kiểm nghiệp vụ/điểm/phạm vi/version bằng Python; JS có thể preview |
| AI/job/SSE | Node bridge + worker Python | Điều phối/validation/job/cancel bằng Python, worker GreenNode chỉ Thuận vận hành |
| Import/OCR/export | Thư viện Node | Python điều phối và xử lý tài liệu; công cụ trình duyệt phụ trợ được mô tả rõ |

`backend/` hiện là nền FastAPI có test health/readiness, **chưa là migration hoàn chỉnh**. Không phục vụ API cũ bằng proxy Python→Node rồi tuyên bố Python là core. Backend Node cũ còn tại gốc để so sánh, chạy golden fixture và tránh mất demo trong giai đoạn chuyển.

## Cách chuyển mà nhóm vẫn làm song song

1. M1: BE-2 chốt API, BE-3 chốt dữ liệu; BE-1/4/5 ghi hành vi đang có và golden fixture. UI chốt UX/mocks. Các bản DTO dùng chung phải khớp OpenAPI của Python.
2. M2: implement Python theo vertical slice: auth → kho đề/version → tài liệu → AI/job/patch. Mỗi slice có pytest contract, ownership và golden test; UI đổi từng lời gọi khi Python slice đã đạt.
3. M3: chạy E2E vào Python, chứng minh chức năng chính hoạt động khi **không chạy Node API**. Build/static assets vẫn dùng npm được. Chỉ loại bỏ phần legacy khi parity + backup/rollback đã qua review.

Không bắt buộc chuyển frontend sang Python vì trình duyệt vẫn cần JavaScript; nhưng nghiệp vụ kiểm điểm, quyền sửa vùng và quyết định lưu không chỉ nằm trong client. Không chuyển dữ liệu thật/GreenNode khi chưa qua migration trên bản sao.

## Checklist đạt yêu cầu Python

- [ ] API, auth, DB, core đề/version/patch và job AI thực thi trong Python.
- [ ] Import/export được Python triển khai/điều phối, công cụ hỗ trợ giải thích được.
- [ ] Pytest kiểm nghiệp vụ, validation, ownership và lỗi; UI E2E gọi Python.
- [ ] Khởi chạy demo chính không cần Node API hoặc proxy về Node.
- [ ] Báo cáo đồ án phân biệt source kế thừa, phần chuyển Python và giới hạn chưa làm.

Framework chọn: [FastAPI](https://fastapi.tiangolo.com/tutorial/first-steps/); môi trường khóa bằng [uv](https://docs.astral.sh/uv/guides/projects/). Đây là lựa chọn triển khai của nhóm theo quyền dùng framework trong ảnh, không phải xác nhận riêng của giảng viên về stack này.


## Ứng viên local có tài khoản — 16/11/2026

Working tree app-ma-tran-that đã thêm team_workspace.py và team_accounts.py, tái sử dụng cùng local_workspace.create_app theo tài khoản, không sao chép nghiệp vụ hoặc chạy Node API. Tài khoản/phiên/lời mời nằm trong SQLite; mỗi UUID tài khoản có một WorkspaceStore và thư mục nguồn/tệp xuất riêng. Owner trong job/nguồn/feedback là ID tài khoản thật; chế độ PoC cũ giữ owner local. Quản trị cấu hình AI; các thành viên nhận cấu hình trong bộ nhớ, không nhận khóa qua API hoặc file cấu hình riêng.

Đây là lát ứng viên tại máy, một tiến trình Uvicorn; chưa thay quyết định ERD/migration trung tâm của BE-2/BE-3, chưa chuyển dữ liệu thật hoặc thay main.py foundation thành bản production. Bộ app của các thành viên được giữ tới khi tắt tiến trình; cần đánh giá eviction/tài nguyên trước phục vụ nhiều nhóm. Dùng CHAY_NHOM_CO_TAI_KHOAN.cmd; PoC cũ và dữ liệu cũ vẫn chạy theo hướng dẫn trước. Chia sẻ snapshot thu hồi, Internet/TLS, email recovery, migration/restore và nghiệm thu toàn IT vẫn mở; không tự đánh dấu checklist tổng trên đây.
