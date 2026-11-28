@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Soạn đề thi - Demo lượt mới
where uv >nul 2>&1
if errorlevel 1 (
  echo Chưa có uv. Cài theo HUONG_DAN_TEST_NHOM.md rồi mở lại.
  pause
  exit /b 1
)
set "PYTHONIOENCODING=utf-8"
uv run --project backend --frozen --no-dev --python 3.12 python scripts\theo-doi-poc.py --demo
set "DEMO_EXIT=%ERRORLEVEL%"
if not "%DEMO_EXIT%"=="0" pause
exit /b %DEMO_EXIT%
