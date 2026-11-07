# Giữ tương thích shortcut cũ; tên hiển thị hiện là Soạn đề thi.
param([switch]$NoBrowser)
& (Join-Path $PSScriptRoot 'OPEN-SOAN-DE.ps1') -NoBrowser:$NoBrowser
exit $LASTEXITCODE
