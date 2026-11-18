# Backend chính của đồ án — Python

Python là ngôn ngữ chính theo quy định môn học. Backend đích: **FastAPI**, validation Pydantic và core nghiệp vụ Python; database/AI/job/tài liệu cũng do Python thực thi. JavaScript chỉ dùng frontend/editor, build và test UI. Không tạo Python facade gọi sang Node để thực hiện toàn bộ nghiệp vụ.

## Chạy bản tích hợp Python

Dùng [hướng dẫn bản 13](../HUONG_DAN_TEST_NHOM.md) trên Windows hoặc chạy FastAPI trực tiếp từ thư mục `backend/` trên máy có Python 3.12 và uv:

```sh
uv sync --frozen
MACH_DATA_DIR=../outputs/test-python/data uv run --frozen uvicorn mach_backend.local_workspace:app --app-dir src --host 127.0.0.1 --port 4188
```

Mở `http://127.0.0.1:4188/`. Lệnh trên dùng cú pháp shell Linux/macOS. Trên Windows dùng các file CMD trong hướng dẫn để tự chọn kho thử và cổng. Chế độ tài khoản của bản 13 khởi chạy bằng `CHAY_NHOM_CO_TAI_KHOAN.cmd`. Bàn soạn, lưu đề, sinh/kiểm, nhập và xuất của bản 13 đi qua API Python. Xem [bằng chứng kiểm bản 13](../docs/testing/NGHIEM_THU_BAN_13.md).

`mach_backend.main:app` là scaffold lịch sử, chỉ có health/readiness. Cổng 8000 trong tài liệu cũ là cổng ví dụ của scaffold. [Chẩn đoán lỗi cổng](../docs/team/LOI_CONG_API.md).

Từ thư mục gốc, `npm start` cũng mở bàn soạn FastAPI ở cổng 4182. uv cài thư viện Python theo lockfile. Nếu cổng bận, dùng `npm start -- --port 4188`.

## Kiểm tra

```sh
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run ty check src
```

Thêm phụ thuộc bằng `uv add`, thêm tool dev bằng `uv add --dev`, commit cả `pyproject.toml` và `uv.lock`. Không commit `.venv`, `.env`, DB thật hoặc khóa. Không thêm thư viện DB/AI/OCR hàng loạt trước khi task chọn và thử compatibility.

## Phân vùng triển khai tiếp

- BE-2: router/auth/dependency/DTO API; cấu trúc module được tạo theo nhu cầu task.
- BE-3: repository, transaction, versioning, migration theo ADR.
- BE-1 (Thuận): AI provider/worker/orchestration và xác thực dữ liệu AI trong Python.
- BE-4: import/OCR/export bằng thư viện hoặc công cụ hỗ trợ do Python điều phối. PDF.js/KaTeX/TipTap trình duyệt chỉ hỗ trợ UI; không chuyển toàn bộ core sang Node service.
- BE-5: job/cancel/SSE, tích hợp pytest, CI và kiểm nghiệm lỗi.

Luồng đối chiếu `npm run start:legacy` và các file `*.mjs` backend tại gốc là **legacy reference** để đọc hành vi và giữ demo trong quá trình chuyển đổi. Các kiểm tra cũ vẫn cần chạy để lập golden test; không dùng số lượng dòng Python hoặc đổi đuôi file để chứng minh đã đáp ứng quy định.
