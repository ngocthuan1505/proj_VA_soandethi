# Backend chính của đồ án — Python

Python là ngôn ngữ chính theo quy định môn học. Backend đích: **FastAPI**, validation Pydantic và core nghiệp vụ Python; database/AI/job/tài liệu cũng do Python thực thi. JavaScript chỉ dùng frontend/editor, build và test UI. Không tạo Python facade gọi sang Node để thực hiện toàn bộ nghiệp vụ.

## Chạy nền khởi tạo

Cài Python 3.12+ và [uv chính thức](https://docs.astral.sh/uv/getting-started/installation/), rồi từ thư mục repo:

```sh
cd backend
uv sync --frozen
uv run uvicorn mach_backend.main:app --app-dir src --host 127.0.0.1 --port 8000 --reload
```

Mở `http://127.0.0.1:8000/docs` hoặc `/api/health`. **Hiện chỉ có liveness và readiness trả 503**, chưa có auth/đề/DB/AI/import/export Python hoàn chỉnh. Không đưa scaffold này lên Internet hoặc gọi nó là app đã migrate xong. Frontend hiện vẫn dùng hợp đồng Node cũ cho đến khi các task Python tương ứng hoàn tất; UI có thể phát triển bằng fixture.

## Nếu cổng 8000 bị lỗi

Không có ràng buộc phải dùng 8000. Có thể đổi thành `--port 8080` trong lệnh trên và mở `http://127.0.0.1:8080/docs`; nếu 8080 cũng bận thì chọn cổng trống khác. Đổi cổng không triển khai thêm nghiệp vụ và UI demo 4173 chưa tự nối nền Python. [Phân biệt lỗi bind/import/readiness và cách kiểm tra](../docs/team/LOI_CONG_API.md).

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

Luồng cũ `npm start` và các file `*.mjs` backend tại gốc là **legacy reference** để đọc hành vi và giữ demo trong quá trình chuyển đổi. Các kiểm tra cũ vẫn cần chạy để lập golden test; không dùng số lượng dòng Python hoặc đổi đuôi file để chứng minh đã đáp ứng quy định.
