@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0"
call MO_APP_LOCAL.cmd
if errorlevel 1 (
  pause
  exit /b 1
)
cls
title PoC - DEMO MỚI - Chờ tạo đề trên web
"backend\.venv\Scripts\python.exe" -X utf8 scripts\theo-doi-poc.py --port 4182 --follow --new-run
pause
