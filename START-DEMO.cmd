@echo off
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-app.ps1" -KeepOpen
if errorlevel 1 (
  echo Khoi dong chua thanh cong. Vui long xem thong bao phia tren.
  pause
)
