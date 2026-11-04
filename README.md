# Mạch — Trợ lý AI soạn đề thi

**Thành viên bắt đầu tại [hướng dẫn nhóm](docs/team/README.md): [nhật ký tiến độ #32](https://github.com/ngocthuan1505/proj_VA_soandethi/issues/32), [báo tiến độ/vướng mắc/nghiệm thu](docs/team/BAO_CAO.md), [áp dụng slide môn](docs/course/README.md), [khung báo cáo đồ án](docs/reports/BAO_CAO_DO_AN.md).**

**Đổi server GreenNode:** source app/worker và các bước dựng môi trường đã được bảo toàn; xem [hồ sơ khôi phục](ops/greennode/KHOI_PHUC.md). Chưa lấy lại được database, cấu hình riêng hoặc trọng số từ volume cũ; clone repo không khôi phục các phần này.

**Theo quy định môn học, Python là ngôn ngữ chính. Backend đích: FastAPI; xem [backend/README.md](backend/README.md) và [kế hoạch chuyển đổi](docs/architecture/PYTHON_MIGRATION.md). Scaffold Python hiện có health/readiness, chưa có đầy đủ nghiệp vụ; backend Node cũ giữ làm tham chiếu.**

## Bắt đầu backend Python

```sh
cd backend
uv sync --frozen
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

API docs tại `http://127.0.0.1:8000/docs`; chạy `uv run pytest`, `uv run ruff check .`, `uv run ty check src`. Nhóm thực hiện các task để chuyển core/auth/DB/AI/document sang Python; JavaScript vẫn dùng frontend.

**Nhóm đồ án bắt đầu tại [docs/team/README.md](docs/team/README.md): [bảng tiến độ kéo thả](https://github.com/users/ngocthuan1505/projects/1/views/1), [cách cập nhật công việc](docs/team/BOARD.md), [phân công 3 UI + 5 backend](docs/team/ROLES.md), [24 task](docs/team/BACKLOG.md), [kiến trúc](docs/architecture/CURRENT_STATE.md), [checklist release](docs/team/RELEASE.md). Thuận là BE-1 và là người duy nhất vận hành GreenNode.**

Ứng dụng soạn đề tiếng Việt cho giáo viên: biên tập tài liệu, nhập công thức trực quan, hỏi/sửa bằng AI, quản lý kho đề và xuất Word/PDF. Repo chứa frontend, backend, bộ chạy AI GreenNode, tài nguyên trình duyệt, cấu hình Docker và kiểm thử.

## Chạy demo legacy để tham chiếu UI

Cần **Node.js 24 trở lên**, npm và Chrome/Edge. Không cần Codex để chạy app.

```sh
git clone https://github.com/ngocthuan1505/proj_VA_soandethi.git
cd proj_VA_soandethi
npm ci
npm start
```

Mở **http://127.0.0.1:4173/**. Giữ tiến trình chạy trong lúc sử dụng; Ctrl+C để dừng. Trên Windows có thể dùng `START-DEMO.cmd` hoặc `OPEN-MACH.ps1` sau khi đã chạy `npm ci`.

Linux: đặt `BROWSER_PATH` tới Chromium/Chrome để xuất PDF, ví dụ `BROWSER_PATH=/usr/bin/chromium npm start`. Trên macOS cũng đặt biến này tới file thực thi Chrome. Không cần trình duyệt headless để sửa đề hoặc chạy bộ unit test.

Dữ liệu tạo mới nằm trong `.data/`, riêng trên mỗi máy. Clone repo **không kèm tài khoản, đề cá nhân, khóa API, token ngrok, cấu hình server đang thuê hoặc trọng số AI**. Không tự kết nối vào GreenNode của chủ dự án. Bản web triển khai riêng hiện được chủ dự án tạm dừng; clone/push repo không bật lại web.

## Chức năng chính

- Soạn đề và đáp án/barem; định dạng chữ, công thức, bảng và hình học.
- Thư viện nội dung đa môn lớp 1–12, nhập trực quan bằng mẫu/MathLive.
- Bôi đen vùng để hỏi hoặc đề xuất sửa; xem trước thay đổi, xác nhận và hoàn tác.
- Sinh đề theo ma trận/nguồn, hỏi giải thích, giải lại và kiểm tra bằng AI đã cấu hình.
- Nhập DOCX, PDF, PPTX, văn bản và ảnh; OCR Việt/Anh; xuất Word có công thức OMML, PDF và HTML.
- SQLite, kho đề, tài khoản và chia sẻ snapshot; chế độ online có đăng nhập và phân quyền.

Đây là MVP: giáo viên cần duyệt nội dung/đáp án; chưa có đồng biên tập thời gian thực hoặc chứng nhận bao trọn chương trình.

## Kết nối AI

Mở **Kết nối AI**, chọn dịch vụ, nhập địa chỉ/model và khóa nếu cần, kiểm tra rồi phân việc Sinh/Sửa/Kiểm. App hỗ trợ Ollama, GreenNode, API tương thích, Gemini, Claude và GPT. Không cần AI để dùng editor và thư viện mẫu; tác vụ AI cần kết nối đã cấu hình. Không tự fallback sang nhà cung cấp trả phí. Mỗi thành viên dùng thông tin truy cập được chủ tài khoản cho phép; không gửi khóa vào GitHub/chat.

Ollama cục bộ cần cài riêng và tải model phù hợp máy. Các script `setup-local-ai.mjs`/`setup-model.mjs` là tùy chọn cho bộ chạy Windows, có tải tệp lớn; không chạy để khởi động editor thông thường. GreenNode GPU: xem [server-kit/README.md](server-kit/README.md). Chỉ làm việc trong `/network-volume/ProJ_VA` trên server được chủ dự án cho phép.

## Kiểm tra và build

```sh
npm test
npm run build-editor
```

`npm test` chạy bộ kiểm tra Node với dữ liệu/AI fixture. Lệnh build tạo lại bundle TipTap sau khi sửa `editor-engine.js`; tài nguyên trình duyệt đã có sẵn trong repo nên chạy app lần đầu không cần build hoặc tải lại assets.

Kiểm tra UI riêng, cần Chrome/Edge hoặc `BROWSER_PATH`:

```sh
node tests/usability-browser.mjs
node tests/selection-browser.mjs
node tests/workbench-browser.mjs
node tests/curriculum-browser.mjs
```

Các bài trên dùng fixture hoặc xử lý cục bộ, không cần khóa AI thật. Một số test tạo ảnh/báo cáo trong thư mục cha repo; chạy trên máy phát triển. `tests/online-browser.mjs` còn cần Python với thư viện `cryptography` để tạo chứng chỉ TLS fixture, không cần để chạy app thông thường.

## Cấu trúc

| Thành phần | Vị trí |
|---|---|
| Giao diện và editor | `app.js`, `studio.js`, `workbench.js`, `editor.js`, CSS |
| Nội dung/công thức | `core.js`, `curriculum-catalog.js`, `composer.js` |
| Backend và dữ liệu | `server.mjs`, `mvp-server.mjs`, `backend-store.mjs`, `accounts.mjs` |
| AI và nhập/xuất | `ai.mjs`, `cloud-ai.mjs`, `greennode.mjs`, `importers.mjs`, `exports.mjs` |
| Tài nguyên trình duyệt | `assets/` |
| Bộ chạy GPU riêng | `server-kit/` |
| Docker/HTTPS | `Dockerfile`, `deploy/` |
| Kiểm thử | `tests/` |

Đọc [hướng dẫn tính năng](USER_GUIDE.md), [triển khai riêng](deploy/README.md), [cách góp code](CONTRIBUTING.md), [giấy phép thành phần bên thứ ba](THIRD_PARTY.md). Tài liệu thiết kế và cải thiện trải nghiệm nằm trong `docs/`.

Để dùng chung repo riêng tư, chủ repo thêm thành viên tại **Settings → Collaborators**. Mỗi người làm nhánh riêng và tạo pull request; không chia sẻ tài khoản GitHub.
