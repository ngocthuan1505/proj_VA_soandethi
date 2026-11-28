@echo off
setlocal
chcp 65001 >nul
cd /d "%~dp0.."
title PoC - Doc API va log that - Khong goi AI
set "POC_PORT=%~1"
if not defined POC_PORT set "POC_PORT=4183"
if "%POC_PORT%"=="4182" goto port_ok
if "%POC_PORT%"=="4183" goto port_ok
if "%POC_PORT%"=="4184" goto port_ok
echo Chi chap nhan cong 4182, 4183 hoac 4184.
exit /b 1
:port_ok
set "CHROME_EXE=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" set "CHROME_EXE=%LocalAppData%\Google\Chrome\Application\chrome.exe"
if not exist "%CHROME_EXE%" goto no_chrome
start "" "%CHROME_EXE%" --new-window "http://127.0.0.1:%POC_PORT%/?ui=demo-20261117-2"
goto watch
:no_chrome
echo Khong tim thay Chrome. Tu mo URL http://127.0.0.1:%POC_PORT%/ trong cua so co thanh dia chi.
:watch
echo Chi doc API. Khong bat server, khong doi key/model, khong goi AI.
echo Theo de dang mo cho toi khi co luot sinh; sau do ghim dung luot do. Ctrl+C de dung; app van giu nguyen.
"backend\.venv\Scripts\python.exe" -X utf8 scripts\theo-doi-poc.py --port "%POC_PORT%" --follow
pause
