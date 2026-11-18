@echo off
chcp 65001 >nul
setlocal
cd /d "%~dp0"
title Soan de thi - Demo luot moi
where uv >nul 2>&1
if errorlevel 1 (
  echo Chua co uv. Cai theo HUONG_DAN_TEST_NHOM.md roi mo lai.
  pause
  exit /b 1
)
uv run --project backend --frozen --no-dev --python 3.12 python scripts\theo-doi-poc.py --demo
set "DEMO_EXIT=%ERRORLEVEL%"
if not "%DEMO_EXIT%"=="0" pause
exit /b %DEMO_EXIT%
