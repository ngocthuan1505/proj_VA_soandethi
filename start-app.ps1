param([switch]$NoBrowser, [switch]$KeepOpen)
$ErrorActionPreference = 'Stop'
$projectDirectory = $PSScriptRoot
$appUrl = 'http://127.0.0.1:4173'
$launchMutex = New-Object System.Threading.Mutex($false, 'Local\SoanDe-MVP-4173-Launcher')
$hasLaunchLock = $false
$startedAppProcessId = $null
function Get-AppHealth {
    try {
        $health = Invoke-RestMethod -Uri "$appUrl/api/status" -TimeoutSec 2
        if ($health.storage -eq 'sqlite' -and $health.version) { return $health }
    } catch {}
    return $null
}
try {
    $hasLaunchLock = $launchMutex.WaitOne(15000)
    if (-not $hasLaunchLock) { throw 'Mot lan khoi dong khac dang chay. Hay thu lai sau vai giay.' }
    $health = Get-AppHealth
    if (-not $health) {
        $nodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
        $nodeExecutable = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\node\bin\node.exe' }
        if (-not (Test-Path -LiteralPath $nodeExecutable)) { throw 'Can Node.js 24 tro len de chay app.' }
        $nodeMajor = [int]((& $nodeExecutable --version).Trim().TrimStart('v').Split('.')[0])
        if ($nodeMajor -lt 24) { throw 'Can Node.js 24 tro len de chay app.' }
        $dataDirectory = Join-Path $projectDirectory '.data'
        New-Item -ItemType Directory -Path $dataDirectory -Force | Out-Null
        $previousPort = $env:PORT
        $previousDataDirectory = $env:APP_DATA_DIR
        try {
            $env:PORT = '4173'
            $env:APP_DATA_DIR = $null
            $appProcess = Start-Process -FilePath $nodeExecutable -ArgumentList 'server.mjs' -WorkingDirectory $projectDirectory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $dataDirectory 'app-stdout.log') -RedirectStandardError (Join-Path $dataDirectory 'app-stderr.log') -PassThru
        } finally {
            $env:PORT = $previousPort
            $env:APP_DATA_DIR = $previousDataDirectory
        }
        $readyDeadline = (Get-Date).AddSeconds(30)
        do {
            Start-Sleep -Milliseconds 350
            $health = Get-AppHealth
            if ($health) { break }
            $appProcess.Refresh()
            if ($appProcess.HasExited) { throw 'App dung khi khoi dong. Xem .data\app-stderr.log de biet nguyen nhan.' }
        } while ((Get-Date) -lt $readyDeadline)
        if (-not $health) { throw 'App chua san sang sau 30 giay. Xem .data\app-stderr.log.' }
        @{ pid = $appProcess.Id; startedAt = (Get-Date).ToUniversalTime().ToString('o'); url = $appUrl } | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $dataDirectory 'app-process.json') -Encoding UTF8
        $startedAppProcessId = $appProcess.Id
        Write-Output "App da khoi dong (PID $($appProcess.Id)), ban $($health.version)."
    } else {
        Write-Output "App da san sang, ban $($health.version). Khong mo them server."
    }
    Write-Output $appUrl
    if (-not $NoBrowser) { Start-Process $appUrl }
} finally {
    if ($hasLaunchLock) { $launchMutex.ReleaseMutex() }
    $launchMutex.Dispose()
}

if ($KeepOpen -and $startedAppProcessId) {
    Write-Output 'Giu cua so nay mo khi dung app. Dong cua so se dung server.'
    Wait-Process -Id $startedAppProcessId -ErrorAction SilentlyContinue
}
