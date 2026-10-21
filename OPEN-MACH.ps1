param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
try {
    # Keep the launcher alive only when it starts a new server. The Desktop
    # shortcut hides this window, while start-app prevents duplicate servers.
    & (Join-Path $PSScriptRoot 'start-app.ps1') -KeepOpen -NoBrowser:$NoBrowser
} catch {
    if ($NoBrowser) { throw }
    $message = "Khong mo duoc Mach.`r`n`r`n" + $_.Exception.Message + "`r`n`r`nThu muc app: " + $PSScriptRoot
    $popup = New-Object -ComObject WScript.Shell
    $null = $popup.Popup($message, 0, 'Mach - Soan de', 16)
    exit 1
}
