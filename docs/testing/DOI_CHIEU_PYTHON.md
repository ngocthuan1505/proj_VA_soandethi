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

## Lệnh chạy chính

`CHAY_THU_NHOM.cmd` và `npm start` đều khởi chạy Uvicorn với `mach_backend.local_workspace:app`. Chế độ có tài khoản dùng `mach_backend.team_workspace:app`. FastAPI thực thi phiên và phân quyền, kho SQLite, phiên bản và áp đề xuất, điều phối AI, nhập tệp và xuất đề. JavaScript vẫn chạy trong bàn soạn và trong Chrome khi dựng công thức, hình hoặc PDF. [Hướng dẫn chạy](../../HUONG_DAN_TEST_NHOM.md) · [Kiểm thử tích hợp](KIEM_THU_TICH_HOP.md)

## Kiểm API với Python riêng

Trên Windows ở commit `6a998ec`, tiến trình kiểm thử dùng PATH chỉ gồm thư mục hệ thống và xác nhận không tìm thấy `node` hoặc `npm`. Bộ kiểm gọi app FastAPI trong tiến trình Python trên SQLite tạm. Kết quả **131 ca đạt** trên các tệp dưới đây. Phạm vi gồm sinh và kiểm bằng phản hồi mẫu, duyệt và đọc lại đề, phiên và phân quyền, chia sẻ, khôi phục, nhập ma trận và cấu trúc bản Word. Lượt này chưa kiểm đóng gói sạch, mở Word/PDF thật hoặc gọi model thật.

```powershell
# Chạy từ backend với môi trường Python đã cài. Dùng PowerShell mới để giữ PATH riêng.
$env:PATH = "$env:SystemRoot\System32;$env:SystemRoot"
& ./.venv/Scripts/python.exe -c "import shutil; assert not shutil.which('node') and not shutil.which('npm')"
if ($LASTEXITCODE) { exit $LASTEXITCODE }
& ./.venv/Scripts/python.exe -m pytest -q tests/test_local_workspace.py tests/test_team_workspace.py tests/test_workspace_shares.py tests/test_workspace_backup.py tests/test_matrix_import.py tests/test_word_export.py
```
