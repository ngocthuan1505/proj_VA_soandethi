# Quyết định: Python là ngôn ngữ chính

Nguồn yêu cầu: ảnh trao đổi quy định môn học do Thuận cung cấp ngày 02/11/2026: Python là ngôn ngữ chính, ngôn ngữ khác hỗ trợ, framework được chọn. Cần đối chiếu rubric chi tiết với giảng viên; không suy diễn một tỉ lệ phần trăm dòng code.

## Phần đã chuyển trên nhánh tích hợp và điều kiện nghiệm thu

| Phần | Bản tích hợp trên PR #46 | Phạm vi còn cần nghiệm thu |
|---|---|---|
| Frontend/editor | Trình soạn JavaScript, TipTap/MathLive/KaTeX, gọi FastAPI | Người dùng thử thao tác bàn phím, IME, công thức và bản in trên máy của nhóm |
| API/auth | `local_workspace.py`, `team_workspace.py` và `team_accounts.py` phục vụ API, phiên và kho theo tài khoản | Review quyền và cấu hình khi chuyển từ chế độ chạy cục bộ sang triển khai thật |
| Database | `workspace_store.py` lưu SQLite. Kiểm phiên bản, biên nhận và khôi phục trên kho thử | So khớp ADR BE-3 và diễn tập chuyển kho đã được phép trên bản sao |
| Đề, đề xuất sửa, phiên bản | FastAPI kiểm revision, phạm vi và áp đề xuất trong giao dịch. Trình soạn dựng preview, hỗ trợ cấu trúc richDoc ngoài lớp ghép của Python | Đối chiếu thêm các loại richDoc và dữ liệu nhóm đang dùng |
| AI, job, SSE | Python điều phối model, gọi bộ kiểm, phát trạng thái và xử lý hủy/hết giờ. Giáo viên xác nhận trước khi ghi đề | Kết quả model thật trên candidate cuối, giới hạn vận hành và review |
| Nhập, OCR, xuất | Python đọc/kiểm tệp và dựng Word, điều phối OCR, HTML và PDF. Trình duyệt hỗ trợ dựng công thức và PDF | Đo chất lượng OCR bằng mẫu được phép và kiểm bản in theo môn |

Lệnh chạy bàn soạn dùng `mach_backend.local_workspace:app`. Bản có tài khoản dùng `mach_backend.team_workspace:app`. Hai entrypoint chạy bằng Uvicorn và dùng nghiệp vụ Python trong cùng tiến trình. Backend Node tại gốc phục vụ đối chiếu và kiểm hồi quy legacy. [Cách đo GitHub Languages, lệnh chạy và bằng chứng API Python](../testing/DOI_CHIEU_PYTHON.md)

PR #46 là nhánh tích hợp đang chờ review. Số đo GitHub Languages của `main` theo bản đo đã ghi thuộc nhánh mặc định. Các mục nghiệm thu bên dưới vẫn cần bằng chứng của ứng viên cuối. [PR tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46) · [Kịch bản nghiệm thu](../testing/KIEM_THU_TICH_HOP.md)

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
