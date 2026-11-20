# Python trong bản tích hợp Soạn đề thi

## Số liệu ngày 19/11/2026

GitHub Languages của nhánh mặc định `main` ở commit `cecfd3d` báo JavaScript 2.642.845 byte (96,72%) và Python 42.188 byte (1,54%). Tỷ lệ tính trên 2.732.482 byte do GitHub trả về, gồm cả các ngôn ngữ khác. Bản tích hợp FastAPI nằm trên PR #46. [Nhánh main](https://github.com/ngocthuan1505/proj_VA_soandethi/tree/cecfd3de362f909feb5f3464f80e2d320b029c80) · [PR tích hợp](https://github.com/ngocthuan1505/proj_VA_soandethi/pull/46)

Bảng dưới đếm kích thước blob Git bằng `git ls-tree -rl <commit>`. Các dòng mô tả tập tệp cụ thể để kiểm lại. Dữ liệu, CSS, HTML và công cụ khác nằm ngoài phép đếm này.

| Phần mã | Cách chọn đường dẫn | `main` `cecfd3d` | Ứng viên `6a998ec` |
| --- | --- | ---: | ---: |
| Backend Python | `*.py` dưới `backend/src/` | 887 | 526.020 |
| Kiểm thử Python | `*.py` dưới `backend/tests/` | 876 | 462.612 |
| JavaScript cho trình duyệt và dựng bản xuất | `*.js` ở gốc và `*.js`, `*.mjs` trong `assets/`, trừ tệp trong các dòng dưới, `editor-engine.js` ở gốc dùng để build và trang đăng nhập cũ | 451.552 | 562.428 |
| Node cũ và công cụ | `*.mjs` ở gốc | 112.847 | 112.949 |
| Bundle editor | `assets/editor-engine.js` | 447.254 | 447.254 |
| JavaScript của thư viện | `*.js`, `*.mjs` trong `assets/katex/` và `assets/mathlive/` | 2.630.140 | 2.630.140 |

Các lượt đo dùng số byte gốc trong Git. Bảng là phép đối chiếu mã theo vai trò, còn GitHub Languages lấy số từ Linguist trên nhánh mặc định. `.gitattributes` của ứng viên chỉ khai báo thư viện bên thứ ba và bundle editor sinh từ build.

Lượt đo lại trên PR #46 ở commit `715dc50` đếm **526.980 byte Python trong `backend/src/`**, so với 887 byte trên `main`. JavaScript ngoài thư viện và bundle vẫn có 566.641 byte trong nhóm giao diện và các tệp JS hỗ trợ, 112.949 byte ở nhóm `.mjs` gốc và 426.393 byte kiểm thử/công cụ dưới `tests/` và `scripts/`. Python kiểm thử và script được tính riêng khi đánh giá runtime. Dữ liệu GitHub Languages vừa kiểm lại vẫn thuộc `main` ở `cecfd3d`.

### Cập nhật đo trực tiếp trên nhánh `codex/ban-thu-13` (commit `8d37a0f`)

Trên GitHub, nhánh mặc định `main` hiện vẫn hiển thị JavaScript **2.642.845 byte (96,72%)** và Python **42.188 byte (1,54%)** vì PR #46 chưa merge vào `main` và `main` chưa có [tệp `.gitattributes`](../../.gitattributes). Tại commit `8d37a0f` (`8d37a0f5f1b4845f4907353706780f31b89180c4`, kế thừa `269cd6a` và gồm thêm Pha 2 `47c40f8` cùng Pha 3 `8d37a0f`), kết quả đo trực tiếp bằng `git ls-tree -rl HEAD` như sau:

| Nhóm tệp theo vai trò | Phạm vi trong `8d37a0f` | Kích thước (byte) | Ghi chú phân loại |
| --- | --- | ---: | --- |
| **Python tổng** | Toàn bộ `*.py` được Git theo dõi | **1.239.067** | **Chưa tính `backend/tests/`: 685.974 B** |
| — Python lõi ứng dụng | `backend/src/**/*.py` | 579.659 | `[Hiện có / Đã chạy bằng Python]` |
| — Python script & vận hành khác | `scripts/*.py`, `ops/greennode/**`, `server-kit/*.py` | 106.315 | Hỗ trợ chạy thử, observer, đóng gói và bootstrap |
| — Python kiểm thử | `backend/tests/**/*.py` | 553.093 | Bộ unit/contract/API/tài liệu pytest |
| **JavaScript tự viết tổng** | Toàn bộ JS/MJS ngoài vendor & bundle | **1.121.180** | **Chưa tính `tests/`: 857.159 B** (không đánh dấu vendor/generated) |
| — JS ở thư mục gốc | `*.js` + legacy `*.mjs` ở gốc | 666.190 | Gồm UI editor/shell và legacy `.mjs` đối chiếu (`112.949 B`) |
| — JS script tiện ích & kiểm UI | `scripts/*.{js,mjs}` | 175.294 | Bộ chạy kiểm tra Chrome/plan |
| — JS hỗ trợ trong `assets/` | `assets/{export-render.mjs,online-login.js,team-login.js,usability.js}` | 15.675 | Không bị đánh dấu generated/vendored |
| — JS kiểm thử Node & browser | `tests/**/*.{js,mjs}` | 264.021 | Hồi quy fixture & UI |
| Thư viện bên thứ ba (`linguist-vendored`) | `assets/katex/**`, `assets/mathlive/**` | 2.630.140 *(JS)* | Nằm trong tổng 4.030.667 B tài nguyên thư viện đã khai báo `.gitattributes` |
| Bundle sinh từ `esbuild` (`linguist-generated`) | `assets/editor-engine.js` | 447.254 | Sinh từ `npm run build-editor`, không viết mã đệm |

Trong phạm vi GitHub Linguist dự kiến sau khi merge PR #46 (loại các mục `linguist-vendored`, `linguist-generated`, `docs/` và `BAN_GIAO_QA/`), Python đạt **48,73% (1.239.067 B)**, đứng #1 vượt JavaScript (**44,09%**, **1.121.180 B**). Như đã nêu trong [kế hoạch chuyển Python](../architecture/PYTHON_MIGRATION.md), đây là số đo cấu trúc mã nguồn trong Git; không thay thế cho bằng chứng nghiệm thu nghiệp vụ và người dùng thật.

Ở luồng sửa qua chat, FastAPI kiểm snapshot, scope và đáp án trước khi trả đề xuất. Với trường thuần văn bản hoặc thay trong một run hay một nút công thức mà Python giữ được cấu trúc, FastAPI chuẩn bị bản sửa và xác nhận bằng một giao dịch SQLite. Giao dịch cập nhật câu, phiên bản và lịch sử hoàn tác cùng biên nhận. Gửi lại cùng mã trả cùng biên nhận. Bỏ đề xuất xóa bản chờ và khôi phục kho làm mất hiệu lực các bản chờ trước đó.

FastAPI cũng ghép được chữ trong nhiều run ở các đoạn văn liền nhau, kể cả trong cùng một ô bảng, mục danh sách hoặc khối trích dẫn. Ca Chrome sửa nhiều đoạn và vùng có chữ lẫn công thức, giữ ID đoạn ngoài vùng, nút công thức và phần in nghiêng. Ca trong ô bảng giữ ID bảng, ID ô và nội dung ô kế bên. Hoàn tác khôi phục bản gốc. Bộ ghép Python từ chối vượt ranh giới ô. Backend có thể chèn công thức mới hoặc sửa một công thức ở vùng có cả chữ, đồng thời ưu tiên offset vùng chọn khi có chữ trùng. Các đề xuất đổi nhiều công thức cùng lúc hoặc chạm cấu trúc chưa hỗ trợ vẫn có thể dùng bộ ghép của trình soạn và ghi snapshot có điều kiện.

## Lệnh chạy chính

`CHAY_THU_NHOM.cmd` và `npm start` đều khởi chạy Uvicorn với `mach_backend.local_workspace:app`. Chế độ có tài khoản dùng `mach_backend.team_workspace:app`. FastAPI thực thi phiên và phân quyền, kho SQLite, phiên bản và áp đề xuất, điều phối AI, nhập tệp và xuất đề. JavaScript vẫn chạy trong bàn soạn và trong Chrome khi dựng công thức, hình hoặc PDF. [Hướng dẫn chạy](../../HUONG_DAN_TEST_NHOM.md) · [Kiểm thử tích hợp](KIEM_THU_TICH_HOP.md) · [Thiết kế màn hình](../design/luong-man-hinh.md) · [Thiết kế trợ lý/job](../design/tro-ly-va-job.md) · [Hợp đồng AI/HTTP/Tài liệu/SSE](../contracts/ai.md) ([HTTP](../contracts/http.md) · [Tài liệu](../contracts/tai-lieu.md) · [Job/SSE](../contracts/job-va-sse.md)) · [Runbook GreenNode (chỉ Thuận vận hành)](../../ops/greennode/README.md)

## Kiểm API với Python riêng

Trên Windows ở commit `6a998ec`, tiến trình kiểm thử dùng PATH chỉ gồm thư mục hệ thống và xác nhận không tìm thấy `node` hoặc `npm`. Bộ kiểm gọi app FastAPI trong tiến trình Python trên SQLite tạm. Kết quả **131 ca đạt** trên các tệp dưới đây. Phạm vi gồm sinh và kiểm bằng phản hồi mẫu, duyệt và đọc lại đề, phiên và phân quyền, chia sẻ, khôi phục, nhập ma trận và cấu trúc bản Word. Lượt này chưa kiểm đóng gói sạch, mở Word/PDF thật hoặc gọi model thật.

### Bằng chứng bổ sung tại `8d37a0f` (`codex/ban-thu-13`)

- **Kiểm toàn bộ Python & chất lượng mã (`[Hiện có / Đã chạy bằng Python]`):** `uv sync --frozen`, `uv run ruff format --check .` (`94` tệp Python), `uv run ruff check .` và `uv run ty check src` đều đạt. `uv run pytest -q` đạt **`710 passed, 5 skipped, 1 warning, 3 subtests passed`** (`110.66s`), bổ sung các bộ test mới ở Pha 3: [test_sample_exam_8b.py](../../backend/tests/test_sample_exam_8b.py) (`1/1`), [test_be3_workspace_bridge.py](../../backend/tests/test_be3_workspace_bridge.py) (`1/1`), [test_security_and_contracts.py](../../backend/tests/test_security_and_contracts.py) (`5/5`); riêng [test_check_routes.py](../../backend/tests/test_check_routes.py) đạt `40 passed, 1 skipped` khi chạy đơn lẻ (khi chạy cùng cụm 5 ca bảo mật không bị tranh chấp GPU đạt `45 passed, 1 skipped`).
- **Kiểm Python khi tắt hoàn toàn Node/npm khỏi `PATH` (`[Hiện có / Đã chạy bằng Python]`):** xác nhận `shutil.which('node') is None` và `shutil.which('npm') is None`, bộ kiểm thử API/kho/chia sẻ/khôi phục/nhập xuất/bảo mật/cầu nối BE-3 chạy đạt **`167 passed`** (`51.99s`).
- **Kiểm hồi quy JS/UI & build (`[Fixture / Mock]`):** `npm test` đạt **`139 passed`** (`0 failed`); `npm run check:team` đạt **`14 passed` + `Team plan OK`**; `npm run build-editor` tạo `assets/editor-engine.js` (`436.8kb`) sạch worktree.
- **Đóng gói ZIP sạch và xuất kiểm thật 4 bản không có Node trong `PATH` (`[Hiện có / Đã chạy bằng Python]`):**
  - Chạy [dong-goi-ban-thu.py](../../scripts/dong-goi-ban-thu.py) với `--ung-vien 48` tạo `outputs/ung-vien-48/SoanDeThi-UngVien-48.zip` gồm **`215` tệp đóng gói** (`216` mục zip kèm `MANIFEST.json`), `SHA-256: 1a28c3c62d77fcc9eec1531e8222284b174bff5844c7e1c4a5813614f4e92f06`.
  - Giải nén ra thư mục tạm sạch ngoài repo, cài `uv sync --frozen --no-dev`, khởi động `uvicorn mach_backend.local_workspace:app --app-dir backend/src` với `PATH` không chứa Node/npm, lưu/đọc lại đề có công thức và xuất kiểm thật 4 tệp:
    - Word Học sinh: **`36.987` byte**, `1` node `m:oMath`, `0` rò đáp án/lời giải/barem/hội thoại chat.
    - Word Giáo viên: **`37.329` byte**, `1` node `m:oMath`, đủ đáp án và barem.
    - PDF Học sinh: **`53.436` byte**, đầu tệp `%PDF-`, `0` rò đáp án/chat.
    - PDF Giáo viên: **`69.026` byte**, đầu tệp `%PDF-`, đủ đáp án và barem.
- **Phần vẫn chờ con người / Thuận (`[Chờ review nhóm / Thành viên xác nhận]`):** review chéo giữa các thành viên, một thành viên khác cài ZIP mới nhất trên máy sạch và mở trực quan bản Word/PDF bằng phần mềm văn phòng thật, khảo sát 3 người dùng `CT-01`, thẩm định sư phạm và vận hành GreenNode do `ngocthuan1505` tự thực hiện theo [runbook GreenNode](../../ops/greennode/README.md).

### Cập nhật đo trực tiếp trên Ứng viên 49 (`0792542`, `codex/ban-thu-13`, 20/11/2026)

- **Phân bố byte trên `0792542` (`git ls-tree -rl HEAD`):** Python tổng đạt **`1.488.000` byte (`53,56%`)** (gồm `backend/src/`: **`737.790` B**, `scripts/` & gốc: `106.315` B, `backend/tests/`: **`643.895` B**; không tính test vẫn `844.105` B), vượt JavaScript tự viết **`1.120.990` B (`40,35%`**; chưa tính test: `857.159` B) và CSS tự viết **`169.091` B (`6,09%`)**. Không ẩn mã JS tự viết, không thêm mã đệm; `.gitattributes` chỉ khai báo thư viện bên thứ ba (`2.630.140` B JS) và `assets/editor-engine.js` (`447.254` B).
- **Kiểm toàn bộ Python & không Node/npm trên `0792542`:** `uv run ruff format --check .` (`102` tệp), `uv run ruff check .`, `uv run ty check src` đạt; `uv run pytest -q` đạt **`751 passed, 5 skipped, 1 warning, 3 subtests passed`** (`122.49s`); lượt chạy khi tước `node` và `npm` khỏi `PATH` qua 16 tệp (12 lõi + 4 mở rộng/tích hợp) đạt **`292 passed, 2 skipped, 1 warning`** (`75.11s`).
- **Đóng gói `SoanDeThi-UngVien-49.zip` (`b7eb24c53180088111d6f94dda3d1757863c9f860ab914eae98da54a4c7a363a`, `219` tệp, 0 tệp cấm):** cài sạch ngoài repo không Node/npm bằng `uv sync --frozen --no-dev`, xuất đạt `docx_student` (`37.089` B, `2 m:oMath`, 0 rò), `docx_teacher` (`37.482` B, `2 m:oMath`), `pdf_student` (`65.366` B, 0 rò), `pdf_teacher` (`81.815` B), và gọi thông suốt 3 nhóm API mở rộng (`/api/curriculum/sources`, `/api/community/*`, `/api/ocr/structure` + `/api/exports/*`). Chi tiết xem [NGHIEM_THU_UNG_VIEN_48.md](NGHIEM_THU_UNG_VIEN_48.md).

### Cập nhật đo trực tiếp trên Ứng viên 50 (`2dc40a1`, `codex/ban-thu-13`, 20/11/2026)

- **Phân bố byte trên `2dc40a1` (`git ls-tree -rl HEAD`):** Python tổng đạt **`1.470.550` byte (`52,45%`)** (`backend/src/`: **`732.664` B**, `scripts/` & gốc: `106.315` B, `backend/tests/`: **`631.571` B**), vượt JavaScript tự viết **`1.162.651` B (`41,47%`**; UI/legacy `708.699` B, `scripts/` `190.121` B, `tests/` `263.831` B) và CSS tự viết **`170.348` B (`6,08%`)**. Gỡ bỏ module trùng `community_library.py` đồng thời nhận `assistant-sources.js`, `lesson-picker.js`, `sketch-board.js` và test UI Codex; `.gitattributes` vẫn chỉ khai báo thư viện bên thứ ba (`assets/katex/**` + `assets/mathlive/**` `4.030.667` B) và `assets/editor-engine.js` (`447.254` B).
- **Kiểm toàn bộ Python & không Node/npm trên `2dc40a1`:** `uv sync --frozen`, `ruff format --check .` (`101` tệp), `ruff check .`, `ty check src` đạt; `uv run pytest -q` **`752 passed, 5 skipped, 1 warning, 3 subtests passed`** (`140.90s`); lượt chạy không `node`/`npm` trên `PATH` qua 16 tệp (12 tệp lõi + 3 tệp mở rộng thống nhất + `test_local_documents.py`) đạt **`307 passed, 2 skipped, 1 warning`** (`66.60s`).
- **Đóng gói `SoanDeThi-UngVien-50.zip` (`527e5c2893fbd08171b49936bc3f47ff4b589e5bdf33a585f3b47c1ffd375f4a`, `222` tệp / `223` mục ZIP, `0` tệp cấm):** cài sạch ngoài repo không Node/npm bằng `uv sync --frozen --no-dev`, chạy `uvicorn mach_backend.local_workspace:app --app-dir backend/src`: kiểm `GET /sketch-board.js` (`5.833` B), xuất `docx_student` (`37.062` B, `4 m:oMath`, `0` rò), `docx_teacher` (`37.142` B, `4 m:oMath`, đủ đáp án), `pdf_student` (`64.241` B, `%PDF-`), `pdf_teacher` (`72.234` B, `%PDF-`), kiểm `POST /api/preview-variant` (`Mã đề 102`), và gọi thông suốt 3 cụm API thống nhất (`/api/lesson-catalog` + `/api/lesson-catalog/sources`, `/api/share` + `/api/community-exams` + `/clone` + `/revoke`, `/api/ocr/structure` + `/api/exports/*`).

### Cập nhật đo trực tiếp trên Ứng viên 51 (`37bf416`, `codex/ban-thu-13`, 20/11/2026)

- **Phân bố byte trên `37bf416` (`git ls-tree -rl HEAD`):** Sau khi ghép `presentation.py`, `poc_matrix.py` (`think: false` cho Qwen3) và kiểm chia sẻ không phụ thuộc Chrome (`e71e9ab`), Python tổng đạt **`1.478.677` byte (`52,55%`)** (`backend/src/`: **`739.026` B**, `scripts/` & gốc: `106.315` B, `backend/tests/`: **`633.336` B**), vượt JavaScript tự viết **`1.164.869` B (`41,40%`**; UI/legacy `708.699` B, `scripts/` `192.339` B, `tests/` `263.831` B) và CSS tự viết **`170.348` B (`6,05%`)**. `.gitattributes` vẫn chỉ khai báo thư viện bên thứ ba (`assets/katex/**` + `assets/mathlive/**` `4.030.667` B) và `assets/editor-engine.js` (`447.254` B).
- **Kiểm Python & không Node/npm trên `37bf416`:** `uv sync --frozen`, `ruff format --check .` (`102` tệp), `ruff check .`, `ty check src` đạt; `uv run pytest -q` **`752 passed, 5 skipped, 1 warning, 3 subtests passed`** (`145.72s`); lượt chạy không `node`/`npm` trên `PATH` qua 16 tệp đạt **`307 passed, 2 skipped, 1 warning`** (`109.10s`).
- **Đóng gói `SoanDeThi-UngVien-51.zip` (`1c329a02b2fb792926e1788ed9387d757e7697f123a20423a7f8075c8dfc3fd3`, `223` tệp / `224` mục ZIP, `0` tệp cấm):** cài sạch ngoài repo không Node/npm bằng `uv sync --frozen --no-dev`, xác nhận thêm luồng HTML trình chiếu học sinh ngoại tuyến (`id="exam-present"`, `0` rò) bên cạnh `sketch-board.js`, 4 Word/PDF, `/api/preview-variant` (`Mã đề 102`) và đủ 3 cụm API thống nhất.

### Cập nhật đo trực tiếp trên Ứng viên 52 (`d071b2b`, `codex/ban-thu-13`, 20/11/2026)

- **Phân bố byte trên `d071b2b` (`git ls-tree -rl HEAD`):** Sau khi hợp nhất Codex [`c087dcc`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/c087dcc) (`b542823`), [`8d6fbe0`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/8d6fbe0) + [`f9655d4`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/f9655d4) (chuẩn 1 schema `personalLesson` + sao lưu/khôi phục kho cá nhân giao dịch) và nối cộng đồng/clone/filter/xuất A4-DOCX vào UI + kiểm tích hợp cross-owner SQLite (`d071b2b`), Python tổng đạt **`1.510.817` byte (`52,78%`)** (`backend/src/`: **`749.243` B**, `scripts/` & gốc: `106.315` B, `backend/tests/`: **`655.259` B**), vượt JavaScript tự viết **`1.181.392` B (`41,27%`**; UI/legacy `721.931` B, `scripts/` `195.630` B, `tests/` `263.831` B) và CSS tự viết **`170.348` B (`5,95%`)** trên tổng `2.862.557` B. `.gitattributes` vẫn chỉ khai báo thư viện bên thứ ba (`assets/katex/**` + `assets/mathlive/**` `4.030.667` B) và `assets/editor-engine.js` (`447.254` B).
- **Kiểm Python & không Node/npm trên `d071b2b`:** `uv sync --frozen` (`29` gói), `ruff format --check .` (`102` tệp), `ruff check .`, `ty check src` đạt; mô phỏng không Chrome (`chrome_path = lambda: None`) trên `test_workspace_shares.py` + `test_extended_workspace_integration.py` đạt **`22 passed`**; `uv run pytest -q` **`759 passed, 5 skipped, 1 warning, 3 subtests passed`** (`245.40s`); lượt chạy không `node`/`npm` trên `PATH` qua 16 tệp đạt **`310 passed, 2 skipped, 1 warning`** (`96.51s`); `check:team` **`14 passed`**, `npm test` **`139 passed`**, `build-editor` `436.8kb` (`git diff --exit-code assets/editor-engine.js` sạch). Chrome `IT-01..IT-09` & `IT-11` đạt liên tiếp (`10/11`, `IT-10` chạm ngưỡng `180.0s` sau khi tạo `bo-ma-de.pdf.zip`), chạy bù `--case 10` trên cùng `d071b2b` đạt trọn vẹn.
- **Đóng gói `SoanDeThi-UngVien-52.zip` (`9023ba21e907d90394291e337f08cce387ea0040e4925ead7f6b3fd739b97aef`, `223` tệp / `224` mục ZIP, `0` tệp cấm):** cài sạch ngoài repo không Node/npm bằng `uv sync --frozen --no-dev`, chạy `uvicorn mach_backend.local_workspace:app --app-dir backend/src`: xác nhận `GET /sketch-board.js` (`5.833` B), `docx_student` (`37.062` B, `4 m:oMath`, `0` rò), `docx_teacher` (`37.142` B, `4 m:oMath`, đủ đáp án), `pdf_student` (`64.241` B, `%PDF-`), `pdf_teacher` (`72.234` B, `%PDF-`), `html_student` (`6.905` B, `id="exam-present"`, `0` rò), `POST /api/preview-variant` (`Đề kiểm tra sạch 50 · Mã đề 102`), và đủ 3 cụm API mở rộng thống nhất.

### Cập nhật đo trực tiếp trên Ứng viên 53 (`703d4c5`, `codex/ban-thu-13`, 20/11/2026)

- **Phân bố byte trên `703d4c5` (`git ls-tree -rl HEAD`):** Sau khi hợp nhất Codex [`90f6af9`](https://github.com/ngocthuan1505/proj_VA_soandethi/commit/90f6af9) (`98d43fa` cắt viền hình phác, `6b492b9` đồng bộ dòng đầu trang Word/PDF/HTML, `05602d2` nhập giáo án/slide vào kho cá nhân, `616e1a4` giữ thứ tự slide PPTX trình chiếu, `90f6af9` hiện vị trí nguồn gốc), bổ sung test PPTX đảo `slideId` (`64aabb5`), mở rộng `IT-09`/`IT-10` (`f8031cb`) và sửa payload `POST /api/exports/matrix-specification` trong `mvp.js` (`703d4c5`), Python tổng đạt **`1.514.977` byte (`52,61%`)** (`backend/src/`: **`750.861` B**, `scripts/` & gốc: `106.375` B, `backend/tests/`: **`657.741` B**), vượt JavaScript tự viết **`1.194.559` B (`41,48%`**; UI/legacy `726.790` B, `scripts/` `203.938` B, `tests/` `263.831` B) và CSS tự viết **`170.348` B (`5,92%`)** trên tổng `2.879.884` B. `.gitattributes` vẫn chỉ khai báo thư viện bên thứ ba (`assets/katex/**` + `assets/mathlive/**` `4.030.667` B) và `assets/editor-engine.js` (`447.254` B).
- **Kiểm Python & không Node/npm trên Ứng viên 53:** Ở `64aabb5` (commit Python cuối), `uv run pytest -q` đạt **`760 passed, 5 skipped, 1 warning, 3 subtests passed`** (`153.71s`), 16 tệp không Node/npm trên `PATH` đạt **`311 passed, 2 skipped, 1 warning`** (`72.77s`), và mô phỏng không Chrome đạt **`22 passed`**. Ở `703d4c5`: `ruff format --check .` (`102` tệp), `ruff check .`, `ty check src`, `check:team` (**`14 passed`**), `npm test` (**`139 passed`**), `build-editor` `436.8kb` sạch, và Chrome `IT-01..IT-11` đạt **11/11 trong một lượt duy nhất** (`outputs/qa-antigravity-it-53-full/result.json`).
- **Đóng gói `SoanDeThi-UngVien-53.zip` (`5cbee372a91743e93fd46df7409afc55c0656a1e26244fb45947e620313f83d0`, `223` tệp / `224` mục ZIP, `0` tệp cấm):** cài sạch ngoài repo không Node/npm bằng `uv sync --frozen --no-dev`, chạy `uvicorn mach_backend.local_workspace:app --app-dir backend/src`: xác nhận `GET /sketch-board.js` (`6.494` B), `docx_student` (`37.062` B, `4 m:oMath`, `header_synced: true`, `0` rò), `docx_teacher` (`37.142` B, `4 m:oMath`, `header_synced: true`, đủ đáp án), `pdf_student` (`66.656` B, `%PDF-`), `pdf_teacher` (`76.941` B, `%PDF-`), `html_student` (`6.993` B, `id="exam-present"`, `header_synced: true`, `0` rò), `POST /api/preview-variant` (`Đề kiểm tra sạch 50 · Mã đề 102`), và đủ 3 cụm API mở rộng thống nhất.

```powershell
# Chạy từ backend với môi trường Python đã cài. Dùng PowerShell mới để giữ PATH riêng.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
& ./.venv/Scripts/python.exe -c "import shutil; assert not shutil.which('node') and not shutil.which('npm')"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& ./.venv/Scripts/python.exe -m pytest -q tests/test_local_workspace.py tests/test_team_workspace.py tests/test_workspace_shares.py tests/test_workspace_backup.py tests/test_matrix_import.py tests/test_word_export.py
```
