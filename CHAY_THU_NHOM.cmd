@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
where uv >nul 2>&1
if errorlevel 1 (
  echo Chưa có uv. Cài theo HUONG_DAN_TEST_NHOM.md rồi mở lại file này.
  pause
  exit /b 1
)
echo Đang chuẩn bị Python và thư viện. Lần đầu cần Internet.
uv sync --project backend --frozen --no-dev --python 3.12
if errorlevel 1 (
  echo Chưa cài được thư viện. Gửi ảnh nguyên cửa sổ này để báo lỗi.
  pause
  exit /b 1
)
set "PYTHONIOENCODING=utf-8"
set "MACH_DATA_DIR=%CD%\outputs\team-test\data"
echo.
echo Khi hiện Application startup complete, mở http://127.0.0.1:4182
echo Giữ cửa sổ này khi test. Nhấn Ctrl+C để tắt app.
echo Chưa cần Ollama. Muốn dùng AI, mở Kết nối trong app và nhập Gemini key riêng.
uv run --project backend --frozen --no-dev python -m uvicorn mach_backend.local_workspace:app --app-dir backend/src --host 127.0.0.1 --port 4182
if errorlevel 1 pause
