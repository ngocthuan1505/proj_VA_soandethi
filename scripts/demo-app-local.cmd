@echo off
chcp 65001 >nul
setlocal
set "PYTHONIOENCODING=utf-8"
cd /d "%~dp0.."
if not exist "backend\.venv\Scripts\python.exe" (
  echo Chưa có môi trường Python. Chạy uv sync --frozen trong backend trước.
  exit /b 1
)
"backend\.venv\Scripts\python.exe" "scripts\mo-app-local.py"
if errorlevel 1 pause
exit /b %ERRORLEVEL%
