# Thành viên tự mở và kiểm thử demo

Mục tiêu: xem **chức năng đã có** trước khi nhận task; mọi người dùng máy và dữ liệu riêng. Không cần Codex, tài khoản AI hoặc GreenNode để dùng editor/thư viện và chạy test fixture. Xem [bảng kế thừa](../product/DEMO_DA_CO.md), [kết quả test](../testing/BASELINE_2026_11_05.md).

## 1. Chuẩn bị lần đầu

- Có quyền vào repo Private, Git, Node.js 24+ (kèm npm) và Chrome hoặc Edge. Kiểm tra `git --version`, `node --version`, `npm --version`. Nếu vừa cài, mở Terminal mới.
- Backend đích cần thêm Python 3.12+ và uv; **không cần chạy FastAPI để xem demo Node hiện tại**.
- Từ Terminal tại thư mục muốn lưu đồ án, chạy:

```sh
git clone https://github.com/ngocthuan1505/proj_VA_soandethi.git
cd proj_VA_soandethi
npm ci
npm start
```

Đăng nhập GitHub bằng luồng trình duyệt/credential manager nếu được hỏi; không nhập password/token vào issue. Repo không kèm `node_modules` nên `npm ci` là bắt buộc ở máy mới; có tải phụ thuộc, cần Internet. Asset editor/công thức/OCR đã có trong repo, không cần chạy setup model hay setup assets cho lần mở thông thường.

Mở **http://127.0.0.1:4173/**. Terminal phải báo app đang chạy và không có lỗi. Chỉ mở URL không tự khởi động server. Đây là địa chỉ trên máy của người mở, không phải link gửi bạn khác truy cập app của mình.

## 2. Những lần sau và cách dừng

Trong thư mục repo: chạy `npm start`, mở URL trên; dùng **Ctrl+C tại Terminal chạy `npm start`** để dừng. Đóng tab trình duyệt chỉ đóng màn hình, không dừng server.

Sau `npm ci`, Windows cũng có `START-DEMO.cmd` để mở thuận tiện. Launcher dùng tiến trình nền; nếu cần biết chắc lúc nào app dừng, dùng cách Terminal `npm start` ở trên. Không cần shortcut riêng của máy Thuận. Đừng bật hai server cùng cổng.

Trước khi lấy source mới, chạy `git status`; nếu có thay đổi cá nhân thì commit theo task hoặc phối hợp review. Khi sạch mới `git pull --ff-only`, rồi `npm ci` nếu lockfile thay đổi. Không dùng reset/clean hoặc xóa `.data` để xử lý lỗi.

## 3. Đi một vòng không cần AI — khoảng 15 phút

Các đề mẫu là dữ liệu minh họa, không phải kết quả sinh AI live. Đặt tên rõ `TEST-<vai trò>-<nội dung>` để tránh nhầm với tài liệu thật.

1. Mở đề mẫu ban đầu hoặc **Tạo đề mới**, chọn môn, thử đề trống và đề mẫu. Vào kho đề mở lại đúng đề vừa tạo; sửa tiêu đề rồi tải lại trang, nội dung vẫn còn.
2. Bấm vào câu để sửa đề bài, thử đậm/nghiêng, bảng và một công thức. Dùng **Thư viện theo môn/Chèn nội dung theo môn**, chọn Toán → phân số/căn/hệ; điền ô → Lưu. Thử thêm một mẫu của môn khác. Tải lại và kiểm vẫn giữ công thức/nội dung.
3. Sửa một đoạn nhỏ rồi undo/redo. Kiểm chữ, định dạng và công thức ngoài đoạn giữ nguyên. Chuyển **Đề/Đáp án** và thử zoom/Tập trung.
4. Mở trợ lý, nhập câu nhiều dòng với **Shift+Enter**, thử mở rộng/thu gọn và cuộn đọc tin cũ. Chưa có AI thì không kỳ vọng nút gửi sinh được đáp án; dùng test fixture ở phần 4 để kiểm luồng hỏi/sửa/sinh thật trong UI.
5. Nhập một DOCX/PDF/PPTX hoặc ảnh **tự tạo, không nhạy cảm** qua menu Tệp. So nội dung, công thức, trang nguồn và chỗ OCR chưa chắc; ghi lỗi nếu khác. Không lấy file giáo viên thật đưa vào bộ test chung.
6. Xuất **bản học sinh** Word/PDF và **bản giáo viên**. Bản học sinh không có đáp án/giải thích/chat; mở Word kiểm công thức sửa được và so với trang đề. PDF cần Chrome/Edge cài trên máy.
7. Quay lại kho, đóng/mở trang và kiểm dữ liệu còn. Nếu test tài khoản, tạo hai tài khoản cục bộ giả trên hai browser context; kho phải tách biệt. Dùng bộ online fixture để kiểm session/ownership đầy đủ, không public app cá nhân.

Ghi **đã thử / kết quả / ảnh / lỗi**, không chỉ nói “nhìn ổn”. Lượt đi thủ công của mỗi người phải được báo riêng; checklist này không có nghĩa nhóm đã test với giáo viên.

## 4. Chạy test tự động — không dùng API key thật

Từ thư mục repo, làm theo thứ tự:

```sh
npm test
npm run check:team
node tests/selection-browser.mjs
node tests/usability-browser.mjs
node tests/curriculum-browser.mjs
node tests/authoring-browser.mjs
node tests/studio-browser.mjs
node tests/workbench-browser.mjs
```

`npm test` kiểm logic/backend Node, có xuất PDF/OCR và AI server fixture. Các script `*-browser` trên tự tạo DB tạm, bật app trên cổng test 4193–4198, dùng Chromium headless, rồi đóng tiến trình của chính chúng. Không cần `npm start` trước và không chạy đồng thời hai bản của cùng một script. Kết quả `PASS` chỉ áp dụng fixture/assertion trong script. Không nhập key vào app test.

Chrome/Edge trên Windows được dò ở vị trí chuẩn. Nếu không tìm được, đặt `BROWSER_PATH` tới file trình duyệt thực thi; ví dụ PowerShell:

```powershell
$env:BROWSER_PATH = 'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe'
node tests/selection-browser.mjs
```

Máy Linux/macOS cũng phải đặt `BROWSER_PATH` nếu không nằm trong vị trí mà [runtime](../../runtime.mjs) dò. Đường dẫn phải trỏ tới executable đang tồn tại. Không cần trình duyệt để xem `/api/health` của FastAPI, nhưng các test PDF/browser cần nó.

Test online bổ sung dùng TLS proxy **cục bộ**, không cần hosting/ngrok. Cần Python có `cryptography`, dùng môi trường dev riêng nếu chưa có:

```sh
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install cryptography
$env:QA_PYTHON = (Resolve-Path .\.venv\Scripts\python.exe).Path
node tests/online-browser.mjs
```

Linux/macOS:

```sh
.venv/bin/python -m pip install cryptography
QA_PYTHON="$PWD/.venv/bin/python" node tests/online-browser.mjs
```

Không commit `.venv`/cert test. Chứng chỉ fixture không được cài vào trust store hệ điều hành. Trước khi test, dùng Terminal dev sạch không có biến `APP_PUBLIC_URL`, `APP_AI_CONFIG`, `APP_DATA_DIR` hoặc cấu hình server thật được kế thừa. Test có thể ghi log/ảnh/DOCX vào `.runtime/`, thư mục tạm hoặc **thư mục cha repo**; không `git add` chúng bừa. Đọc source của script khi đổi nơi lưu kết quả.

Sửa `editor-engine.js` thì chạy thêm `npm run build-editor`; sửa tài liệu/hợp đồng thuần túy không cần build lại bundle. Không chạy script setup model chỉ để làm test UI.

## 5. Chạy phần Python đúng mức hiện tại

Cổng 8000 là ví dụ, không bắt buộc. Nếu máy chạy được ở 8080, đổi `--port 8080` và mở đúng URL 8080. [Hướng dẫn phân biệt lỗi cổng](LOI_CONG_API.md).

```sh
cd backend
uv sync --frozen --python 3.12
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Mở `http://127.0.0.1:8000/docs`: `/api/health` trả 200, `/api/readiness` **trả 503 và danh sách còn thiếu là đúng hiện trạng**. UI legacy không tự chuyển qua cổng 8000. Xem [kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md); không gọi foundation là app đầy đủ.

Nếu `uv` chọn Python tự tải rồi báo lỗi môi trường, chọn bản 3.12 đã cài bằng `uv sync --frozen --python <đường-dẫn-python-3.12>`. Không sửa `uv.lock` chỉ để chạy qua máy cá nhân. Lệnh sync mặc định của repo vẫn dùng được khi môi trường Python phù hợp.

## 6. AI thật và các lỗi thường gặp

Editor/thư viện không cần AI. Muốn thử AI thật, mở **Kết nối AI**, dùng provider/model và thông tin truy cập được chủ tài khoản cho phép, kiểm tra rồi chọn Sinh/Sửa/Kiểm. Chưa có kết nối thì báo vướng, không coi lỗi thiếu key là lỗi editor. Không mặc định API miễn phí; không tự tải model lớn, mua quota hoặc fallback trả phí. Chỉ Thuận thao tác GreenNode.

| Hiện tượng | Cách xử lý |
|---|---|
| `127.0.0.1 refused to connect` | Mở Terminal đúng repo, chạy `npm start`, đọc lỗi. Reload trình duyệt không thay việc bật server |
| `npm`/`node` không nhận | Cài Node 24+ kèm npm; mở Terminal mới và kiểm version |
| `ERR_MODULE_NOT_FOUND`, thiếu thư viện | Chạy `npm ci` ở thư mục có package.json; không chép node_modules từ máy khác |
| `EADDRINUSE` | Kiểm tra Terminal/launcher đã mở; dừng đúng tiến trình của mình hoặc dùng cổng khác; không kill mọi Node trên máy |
| PDF/browser không mở | Kiểm tra Chrome/Edge và `BROWSER_PATH`; không nhầm với lỗi sinh đề |
| Không thấy đề/tài khoản của Thuận | Đúng: clone không mang `.data`, tài khoản, khóa hay model; mỗi máy là workspace riêng |
| Test lỗi | Ghi đúng command, commit, log cuối, expected/actual và file fixture; không xóa DB thật hoặc đổi assertion để thành PASS |

## 7. Nhận task và báo kết quả

Đọc [menu tự chọn việc](CHON_VIEC.md) và [bảng kế thừa](../product/DEMO_DA_CO.md), rồi đăng ký cá nhân/nhóm ở task phù hợp trong [backlog](BACKLOG.md), đọc phần demo sẵn có trước khi viết code. Dùng [mẫu tiến độ/vướng mắc/nghiệm thu](BAO_CAO.md) và dẫn issue task gốc. Ghi nguồn kế thừa, phần mới của mình, test đã chạy và chưa chạy; mã mảng không phải tên người, không chia sẻ tài khoản GitHub.

Ví dụ một báo cáo hữu ích:

```text
Task: UI-2-001; commit: <sha>; máy: Windows/Node 24/Chrome
Đã kế thừa: D02, D03, D07
Đã thử: chèn hệ 2 PT, reload, undo, xuất Word
Expected/Actual: ...
Lệnh: node tests/selection-browser.mjs; kết quả: ...
Bằng chứng: ảnh/log fixture đã bỏ thông tin riêng
Chưa thử: model thật, Microsoft Word trên macOS
Vướng / việc tiếp theo / cần reviewer: ...
```

Không đánh dấu hoàn thành chỉ vì cài được hoặc xem demo được. Repo/Project Private cần quyền riêng; nếu thiếu quyền thì báo Thuận, không đổi công khai.
