@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo Chưa có uv. Xem HUONG_DAN_TEST_NHOM.md để cài công cụ.
  pause
  exit /b 1
)
uv sync --project backend --frozen --no-dev --python 3.12
if errorlevel 1 (
  echo Chưa chuẩn bị được thư viện. Giữ lại thông báo lỗi.
  pause
  exit /b 1
)
set "PYTHONIOENCODING=utf-8"
echo Chế độ nhóm dùng kho riêng tại cổng 4185, không chuyển đề từ bản PoC cũ.
echo Giữ cửa sổ này khi dùng app. Ctrl+C để dừng.
uv run --project backend --frozen --no-dev python scripts/chay-nhom-tai-khoan.py
if errorlevel 1 pause
