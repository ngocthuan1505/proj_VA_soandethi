@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0..\backend"
set "PYTHONPATH=src"
set "PYTHONIOENCODING=utf-8"
set "POC_MODEL=%~1"
if not defined POC_MODEL set "POC_MODEL=qwen2.5:3b"
set "POC_OUTPUT=%~2"
if not defined POC_OUTPUT set "POC_OUTPUT=..\outputs\poc-cmd\lan-%RANDOM%-%RANDOM%"
if not exist ".venv\Scripts\python.exe" (
  echo Chưa có môi trường Python. Chạy uv sync --frozen trong backend trước.
  exit /b 1
)
echo Chạy model thật trên localhost. Không có phản hồi soạn sẵn.
echo Model: %POC_MODEL%
echo Log: %POC_OUTPUT%
echo Hai lần nộp bộ câu = một lần đầu và tối đa một lần sửa.
".venv\Scripts\python.exe" -m mach_backend.poc_matrix --input poc-data/thu-vien.json --output "%POC_OUTPUT%" --model "%POC_MODEL%" --protocol structured --max-attempts 2 --timeout 900
exit /b %ERRORLEVEL%
