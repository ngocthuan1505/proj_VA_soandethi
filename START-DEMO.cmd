@echo off
chcp 65001 >nul
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-app.ps1" -KeepOpen
if errorlevel 1 (
  echo Khởi động chưa thành công. Vui lòng xem thông báo phía trên.
  pause
)
