# Đọc repo Soạn đề thi trong 5 phút

Bản tóm tắt 06/11/2026 cho người mới. **Chỉ cần đọc file này trước**, mở demo rồi chọn việc; chưa cần đọc hết backlog/hồ sơ. Đây là bản đồ repo, không phải tuyên bố mọi tính năng đã nghiệm thu.

## 1. Nhóm đang xây cái gì?

Soạn đề thi là trợ lý soạn đề cho giáo viên: tạo/mở đề, soạn trực tiếp, chèn công thức không cần nhớ LaTeX, dùng nguồn tài liệu, hỏi/sửa bằng AI có xem trước và xác nhận, lưu và xuất Word/PDF bản học sinh/giáo viên.

**Đã có demo JS/Node khá đầy đủ để kế thừa.** Đồ án yêu cầu Python là ngôn ngữ chính nên nhóm đang chuẩn bị chuyển core/backend sang FastAPI theo từng phần, giữ JavaScript cho editor/trình duyệt. `backend/` hiện mới có health/readiness, chưa có toàn bộ nghiệp vụ. Không phải xây lại UI từ số 0 và cũng chưa được coi là đã chuyển Python xong.

## 2. Hiện có gì, còn thiếu gì?

| Phần | Demo kế thừa đã có | Việc nhóm cần làm tiếp |
|---|---|---|
| Soạn đề | Editor, rich text, công thức trực quan, bảng/hình, undo/reload, kho đề | Rà UX, giữ định dạng/ID/version khi nối Python |
| Đa môn | 485 mục trong 19 nhóm môn, lọc lớp gợi ý 1–12; mẫu Văn/Anh/Sinh… | Rà chuyên môn/giới hạn; không coi thư viện là đủ mọi bộ sách |
| Trợ lý | Làm rõ yêu cầu, sinh từng bài, chat, chọn vùng, diff/confirm, hủy/retry | Port orchestration/validation/job Python, kiểm scope/stale/lỗi và đánh giá AI thật |
| Dữ liệu/tài khoản | SQLite, revision conflict, kho riêng, session, share/revoke | Chốt schema/repository/auth/API Python, migration/restore không mất dữ liệu |
| Tài liệu | DOCX/PDF/PPTX/ảnh, OCR, nguồn theo trang, Word OMML/PDF/HTML | Port document service, kiểm file/quyền/trích dẫn và bản in thực |
| Hồ sơ môn | Proposal/baseline, Decomposition–Pattern và Abstraction đã có; task/gates/test plan đã chuẩn bị | Kế thừa thiết kế, bổ sung khảo sát/PoC/thuật toán/đánh giá có bằng chứng |

Baseline ngày 05/11: 98 test Node, 80 bước UI fixture trong 7 bộ và 2 pytest nền đạt. Kế hoạch nhóm có 14 test. Đó **không phải** bằng chứng model thật đúng mọi môn, hosting 24/7 hoặc sản phẩm Python hoàn chỉnh. [Chi tiết chức năng/giới hạn](docs/product/DEMO_DA_CO.md).

## 3. Mở app để hiểu trước khi đọc code

Cần quyền repo Private, Git, Node.js 24+ kèm npm, Chrome/Edge:

```sh
git clone https://github.com/ngocthuan1505/proj_VA_soandethi.git
cd proj_VA_soandethi
npm ci
npm start
```

Mở **http://127.0.0.1:4173/**. Thử tạo đề → sửa chữ → chèn phân số/hệ → undo → reload → xuất file. Giữ Terminal chạy, Ctrl+C để dừng. Editor và thư viện mẫu không cần key AI/GreenNode; clone không kèm dữ liệu/tài khoản của Thuận. AI thật cần kết nối được phép.

Muốn xem nền Python, mở Terminal khác từ root repo:

```sh
cd backend
uv sync --frozen --python 3.12
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8080 --reload
```

Cần Python 3.12+ và uv. Mở **http://127.0.0.1:8080/docs**; health 200, readiness 503 là đúng foundation. **8080 là ví dụ cổng thay thế; 8000 cũng hợp lệ nếu máy cho bind.** Hai cổng không phải hai phiên bản app. Demo 4173 hiện chưa tự nối sang nền Python này. [Khi cổng 8000 bị lỗi](docs/team/LOI_CONG_API.md).

## 4. Bản đồ source: tìm đúng phần cần đọc

| Nơi đọc | Chứa gì / đọc khi nào |
|---|---|
| `app.js`, `design.js/css`, `assets/usability.*` | Shell, kho đề, điều hướng, trải nghiệm chat; tìm màn hình trước |
| `editor*.js`, `composer.js`, `rich-document.js`, `geometry.js`, `pages.js` | Editor, công thức/thư viện, cấu trúc richDoc, hình và trang |
| `core.js`, `blocks.js` | Mô hình/hành vi demo, ID/version, kiểm phạm vi, patch/undo; đọc cùng test |
| `workbench.js/css`, `studio.js/css` | Luồng trợ lý, ngữ cảnh, diff/stream và tích hợp editor |
| `server.mjs` → `mvp-server.mjs`, `workbench-server.mjs` | Entry và API/job Node **legacy**, tham chiếu để port; không phải backend đích |
| `accounts.mjs`, `backend-store.mjs`, `storage.js` | Auth, SQLite/revision và lưu phía browser trong demo |
| `ai.mjs`, `cloud-ai.mjs`, `greennode.mjs`, `ai-providers.js` | Routing/adapter/validation AI; code hỗ trợ provider không chứng minh có quota/model thật |
| `importers.mjs`, `word-import.mjs`, `exports.mjs`, `math-word.mjs` | Nhập/OCR/nguồn và xuất tài liệu/công thức |
| `backend/src/mach_backend/`, `backend/tests/` | Nơi triển khai backend/core Python mới và pytest; hiện mới foundation |
| `tests/` | Unit/backend/contract/browser fixture; mở test của hành vi trước khi sửa |
| `assets/`, `package*.json` | Asset browser và phụ thuộc khóa; không cần đọc bundle minify để hiểu app |
| `docs/product`, `docs/architecture` | Mục tiêu/use case, hiện trạng và kế hoạch Python/dữ liệu |
| `docs/team`, `docs/testing` | Chọn việc, backlog/gates/báo cáo, cách chạy và kết quả/kế hoạch test |
| `docs/course`, `docs/reports`, `docs/context` | Yêu cầu môn/hồ sơ đã có, báo cáo, bản bàn giao lý thuyết–thực hành |
| `server-kit/`, `ops/greennode/`, `deploy/` | Worker/runbook/triển khai tham khảo; **chỉ Thuận thao tác GreenNode** |

Luồng để hình dung: **giáo viên → UI/editor → API Node demo → kho dữ liệu / AI job / import-export**. Đích nhóm sẽ chuyển là **UI/editor → FastAPI → nghiệp vụ/repository/jobs/tài liệu Python**. Không dùng proxy Python gọi Node để giả hoàn thành core Python.

## 5. Mỗi người bắt đầu từ đâu?

Chỉ chốt nhóm 3 UI/5 backend, **chưa gán cứng người vào chuyên môn**. Cả ba UI có thể cùng nghiên cứu một luồng; backend cũng làm chung. UI-1/BE-2… là mã mảng, không phải người.

1. Mở [menu tự chọn việc](docs/team/CHON_VIEC.md): có mục tiêu từng mảng, thứ nên thử, đầu ra và link issue.
2. Chọn một luồng/Wxx, comment đăng ký cá nhân/nhóm và ai code/test/review. Bắt đầu nghiên cứu/fixture trước, chốt phương án với consumer rồi mới làm.
3. Task 001 chốt baseline/contract; 002 triển khai/tích hợp; 003 nghiệm thu. Wxx là bước làm, Txx là ca kiểm có expected; chưa tick không có nghĩa demo cũ chưa có.
4. PR nhỏ, commit tiếng Việt, ghi phần kế thừa/phần mới, test đã/chưa chạy và cách quay lui. Có người khác review; không reset/ghi đè việc nhau.

[Bảng task](https://github.com/users/ngocthuan1505/projects/1/views/1) · [Nhật ký #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32) · [Báo tiến độ/vướng/nghiệm thu](docs/team/BAO_CAO.md).

**Chỉ đọc tiếp khi cần:** [chạy/test đầy đủ](docs/team/CHAY_VA_TEST_DEMO.md), [task kỹ thuật](docs/team/BACKLOG.md), [hồ sơ môn đã có](docs/course/HO_SO_DA_CO.md), [kế hoạch Python](docs/architecture/PYTHON_MIGRATION.md). Không cần đọc 30 issue hoặc mọi slide ngay buổi đầu.

## 6. Nếu muốn nhờ AI giải thích repo

Giữ repo Private, nhận lời mời đúng account. Nếu công cụ AI của bạn có tích hợp GitHub riêng tư, chỉ kết nối theo quyền bạn có; không phải công cụ nào cũng đọc được link Private. Cách đơn giản: đưa **chính file tóm tắt này** và file source/test cụ thể cần hỏi vào AI, không cần mở public toàn repo.

Prompt gợi ý: “Đọc bản tóm tắt này, giải thích phần demo đang có và phần Python còn phải làm; hỏi tôi muốn nghiên cứu mảng nào. Khi tôi chọn, chỉ đọc source/test liên quan, phân biệt thiết kế với code đã chạy, đề xuất một bước nhỏ và test để bắt đầu.”

Không tải `.env`, `.data`, `.runtime`, khóa API, tài liệu giáo viên, model hoặc toàn lịch sử chat lên công cụ ngoài. Không suy repo có key thật chỉ từ việc có adapter AI; repo vẫn phải giữ Private theo quy định nhóm.
