#Requires -Version 5.1
[CmdletBinding()]
param([string]$Python, [switch]$NoBrowser, [ValidateRange(10, 180)][int]$TimeoutSeconds = 90)
. "$PSScriptRoot\demodoctor-common.ps1"
$lock = Enter-DemoLock
$created = @()
try {
    $state = Read-DemoState
    $missing = @()
    foreach ($kind in @('backend', 'frontend')) {
        $port = if ($kind -eq 'backend') { 8765 } else { 5173 }
        $existing = Get-DemoExisting $kind
        if ($null -ne $existing) {
            Write-Host "Reusing DemoDoctor $kind on port $port."
            if (!$existing.offline) { Write-Warning "Existing manual $kind is not managed by this launcher; it will not be stopped. Uploads still default to dry-run; the manual backend has its original API permissions." }
            continue
        }
        if (Test-DemoPort $port) { throw "Port $port is occupied by an unrecognized service. Close it yourself or use DemoDoctor-Status. Nothing was killed." }
        if (Test-DemoOwned $state.$kind $kind) { throw "Managed $kind is alive but unresponsive. Run DemoDoctor-Stop, inspect the logs, then retry." }
        $missing += $kind
    }
    if ($missing -contains 'backend') {
        if (!$Python) {
            foreach ($candidate in @((Join-Path $script:DemoRoot '.venv\Scripts\python.exe'), (Join-Path $script:DemoRoot 'venv\Scripts\python.exe'), (Join-Path (Split-Path $script:DemoRoot -Parent) 'DemoDoctor\venv\Scripts\python.exe'))) {
                if (Test-Path -LiteralPath $candidate) { $Python = $candidate; break }
            }
        }
        if (!$Python -or !(Test-Path -LiteralPath $Python)) { throw 'No Python environment found. Create .venv and install requirements-lock.txt, or pass -Python <python.exe>. Nothing was installed.' }
        $Python = (Resolve-Path -LiteralPath $Python).Path
        Push-Location $script:DemoRoot
        try {
            & $Python -c 'import sys; assert sys.version_info >= (3,12), "Python 3.12+ required"; import live_api, uvicorn' 2>&1 | Out-String | Write-Verbose
            if ($LASTEXITCODE -ne 0) { throw "Python dependencies are missing or incompatible in $Python. Install requirements-lock.txt explicitly (use -Verbose for diagnostics)." }
        } finally { Pop-Location }
        Write-Host "Python: $Python"
    }
    if ($missing -contains 'frontend') {
        $node = (Get-Command node.exe -ErrorAction Stop).Source
        $version = & $node -p 'process.versions.node'
        if ([version]$version -lt [version]'22.12.0') { throw 'Node 22.12+ required. Nothing was installed.' }
        if (!(Test-Path -LiteralPath (Join-Path $script:DemoRoot 'web\node_modules\vite\dist\node\index.js'))) { throw 'React dependencies missing. Run npm ci in web explicitly. Nothing was installed.' }
    }
    foreach ($kind in $missing) {
        $executable = if ($kind -eq 'backend') { $Python } else { $node }
        $state.$kind = Start-DemoProcess $kind $executable
        $created += $kind
        Save-DemoState $state
        Wait-DemoService $kind $state.$kind $TimeoutSeconds
        Save-DemoState $state
        Write-Host "Started $kind (PID $($state.$kind.pid))."
    }
    Test-DemoReplays
    if (!$NoBrowser) { Start-Process 'http://127.0.0.1:5173/' | Out-Null }
    Write-Host 'DemoDoctor ready: http://127.0.0.1:5173/ | PILOT + 5 cached investigations verified.'
    Write-Host "Replay ready; uploads default to dry-run. Launcher-started inference is offline-only. Logs: $script:DemoRuntime"
} catch {
    # Roll back only processes created by this invocation; preserve reused services.
    foreach ($kind in $created) { Stop-DemoOwned $state.$kind $kind; $state.$kind = $null }
    if ($created.Count) { Save-DemoState $state }
    throw
} finally { $lock.Dispose() }
