# Shared Windows PowerShell 5.1+ launcher helpers. No administrator rights needed.
Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
$script:DemoRoot = [IO.Path]::GetFullPath((Split-Path $PSScriptRoot -Parent))
$script:DemoRuntime = Join-Path $script:DemoRoot '.demodoctor'
$script:DemoStateFile = Join-Path $script:DemoRuntime 'services.json'

function Enter-DemoLock {
    [IO.Directory]::CreateDirectory($script:DemoRuntime) | Out-Null
    $until = [DateTime]::UtcNow.AddSeconds(30)
    do {
        try { return [IO.File]::Open((Join-Path $script:DemoRuntime 'launcher.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
        catch [IO.IOException] { Start-Sleep -Milliseconds 200 }
    } while ([DateTime]::UtcNow -lt $until)
    throw 'Another DemoDoctor start/stop operation is still running. Try again shortly.'
}

function Read-DemoState {
    if (Test-Path -LiteralPath $script:DemoStateFile) {
        try { return Get-Content -LiteralPath $script:DemoStateFile -Raw | ConvertFrom-Json }
        catch { throw "Cannot read launcher ownership state: $script:DemoStateFile. No processes were stopped." }
    }
    return [pscustomobject]@{ backend = $null; frontend = $null }
}

function Save-DemoState($State) {
    $temp = Join-Path $script:DemoRuntime 'services.tmp'
    $State | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $temp -Encoding UTF8
    Move-Item -LiteralPath $temp -Destination $script:DemoStateFile -Force
}

function Get-DemoJson([string]$Url) {
    try { return Invoke-RestMethod -Uri $Url -TimeoutSec 3 -ErrorAction Stop }
    catch { return $null }
}

function Get-DemoIdentity([string]$Kind) {
    $url = if ($Kind -eq 'backend') { 'http://127.0.0.1:8765/api/launcher' } else { 'http://127.0.0.1:5173/__demodoctor_launcher' }
    $item = Get-DemoJson $url
    if ($null -eq $item) { return $null }
    try {
        if ($item.protocol -ne 1 -or $item.kind -ne $Kind) { return $null }
        if ([IO.Path]::GetFullPath($item.root).TrimEnd('\') -ine $script:DemoRoot.TrimEnd('\')) { return $null }
        if ($Kind -eq 'frontend' -and $item.api -ne 'http://127.0.0.1:8765') { return $null }
        return $item
    } catch { return $null }
}

function Get-DemoExisting([string]$Kind) {
    $identity = Get-DemoIdentity $Kind
    if ($null -ne $identity) { return $identity }
    # Read-only recognition of pre-launcher services. Never adopt/stop them.
    try {
        if ($Kind -eq 'backend') {
            $schema = Get-DemoJson 'http://127.0.0.1:8765/openapi.json'
            if ($null -eq $schema -or $schema.info.title -ne 'DemoDoctor Live API') { return $null }
            $response = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:8765/api/recorded-pilot/tracks.json' -TimeoutSec 5
            $expected = [IO.File]::ReadAllText((Join-Path $script:DemoRoot 'data\submission_demo\pilot\job\tracks.json'))
            if ($response.Content -cne $expected) { return $null }
            return [pscustomobject]@{ kind = $Kind; pid = $null; offline = $false; instance = 'manual' }
        }
        $prefix = Join-Path $script:DemoRoot 'web\node_modules\'
        $processes = @(Get-CimInstance Win32_Process -Filter "Name='node.exe'" | Where-Object {
            $_.CommandLine -and $_.CommandLine.Contains($prefix) -and $_.CommandLine -match 'vite[\\/]bin[\\/]vite.js' -and $_.CommandLine -match '--port[ =]+5173\b'
        })
        if ($processes.Count -ne 1) { return $null }
        $html = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 3
        if ($html.Content -notmatch '/@vite/client' -or $html.Content -notmatch '<title>DemoDoctor\b') { return $null }
        return [pscustomobject]@{ kind = $Kind; pid = $processes[0].ProcessId; offline = $false; instance = 'manual' }
    } catch { return $null }
}

function Test-DemoPort([int]$Port) {
    $socket = New-Object Net.Sockets.TcpClient
    try {
        $pending = $socket.ConnectAsync('127.0.0.1', $Port)
        if (!$pending.Wait(500)) { return $false }
        return $socket.Connected
    } catch { return $false } finally { $socket.Dispose() }
}

function Test-DemoOwned($Record, [string]$Kind) {
    if ($null -eq $Record) { return $false }
    try {
        $process = Get-Process -Id $Record.pid -ErrorAction Stop
        if ($process.StartTime.ToUniversalTime().Ticks.ToString() -ne $Record.startedTicks) { return $false }
        $entry = Join-Path $script:DemoRoot $(if ($Kind -eq 'backend') { 'scripts\launcher_backend.py' } else { 'scripts\launcher_frontend.mjs' })
        $info = Get-CimInstance Win32_Process -Filter "ProcessId=$($Record.pid)"
        return ($null -ne $info -and $info.CommandLine.Contains($entry))
    } catch { return $false }
}

function Stop-DemoOwned($Record, [string]$Kind) {
    $targets = @()
    if (Test-DemoOwned $Record $Kind) { $targets += $Record }
    if ($null -ne $Record -and $Record.PSObject.Properties['launchPid'] -and $Record.launchPid -ne $Record.pid) {
        $parent = [pscustomobject]@{ pid = $Record.launchPid; startedTicks = $Record.launchStartedTicks }
        if (Test-DemoOwned $parent $Kind) { $targets += $parent }
    }
    # Also handle a venv redirector whose child has not reached HTTP readiness yet.
    foreach ($target in @($targets)) {
        foreach ($child in @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($target.pid)")) {
            $proc = Get-Process -Id $child.ProcessId -ErrorAction SilentlyContinue
            if ($null -eq $proc) { continue }
            $candidate = [pscustomobject]@{ pid = $proc.Id; startedTicks = $proc.StartTime.ToUniversalTime().Ticks.ToString() }
            if (Test-DemoOwned $candidate $Kind) { $targets = @($candidate) + $targets }
        }
    }
    foreach ($target in $targets) {
        if (Test-DemoOwned $target $Kind) { Stop-Process -Id $target.pid -ErrorAction Stop }
    }
    for ($i = 0; $i -lt 50; $i++) {
        $alive = @($targets | Where-Object { Test-DemoOwned $_ $Kind })
        if (!$alive.Count) { return }
        Start-Sleep -Milliseconds 100
    }
    throw "The managed $Kind process did not exit. See $script:DemoRuntime."
}

function Start-DemoProcess([string]$Kind, [string]$Executable, [switch]$RealAnalysis, [string]$CredentialsFile, [string]$PerRunBudgetUsd) {
    $instance = [Guid]::NewGuid().ToString('N')
    $entry = Join-Path $script:DemoRoot $(if ($Kind -eq 'backend') { 'scripts\launcher_backend.py' } else { 'scripts\launcher_frontend.mjs' })
    $stdout = Join-Path $script:DemoRuntime "$Kind-$instance.log"
    $stderr = Join-Path $script:DemoRuntime "$Kind-$instance.err.log"
    $previous = $env:DEMODOCTOR_LAUNCH_INSTANCE
    $previousReal = $env:DEMODOCTOR_REAL_ANALYSIS
    $previousCredentials = $env:DEMODOCTOR_CREDENTIALS_FILE
    $previousLimit = $env:DEMODOCTOR_PER_RUN_BUDGET
    try {
        $env:DEMODOCTOR_LAUNCH_INSTANCE = $instance
        $env:DEMODOCTOR_REAL_ANALYSIS = $(if ($RealAnalysis) { '1' } else { '0' })
        $env:DEMODOCTOR_CREDENTIALS_FILE = $CredentialsFile
        $env:DEMODOCTOR_PER_RUN_BUDGET = $PerRunBudgetUsd
        $process = Start-Process -FilePath $Executable -ArgumentList ('"' + $entry + '"') -WorkingDirectory $script:DemoRoot -WindowStyle Hidden -PassThru -RedirectStandardOutput $stdout -RedirectStandardError $stderr
        $ticks = $process.StartTime.ToUniversalTime().Ticks.ToString()
        return [pscustomobject]@{ pid = $process.Id; startedTicks = $ticks; launchPid = $process.Id; launchStartedTicks = $ticks; instance = $instance; stdout = $stdout; stderr = $stderr }
    } finally {
        $env:DEMODOCTOR_LAUNCH_INSTANCE = $previous
        $env:DEMODOCTOR_REAL_ANALYSIS = $previousReal
        $env:DEMODOCTOR_CREDENTIALS_FILE = $previousCredentials
        $env:DEMODOCTOR_PER_RUN_BUDGET = $previousLimit
    }
}

function Wait-DemoService([string]$Kind, $Record, [int]$TimeoutSeconds) {
    $until = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    do {
        $identity = Get-DemoIdentity $Kind
        if ($null -ne $identity) {
            if ($null -eq $Record) { return }
            if ($identity.instance -eq $Record.instance) {
                $actual = Get-Process -Id $identity.pid -ErrorAction Stop
                $candidate = [pscustomobject]@{ pid = $actual.Id; startedTicks = $actual.StartTime.ToUniversalTime().Ticks.ToString() }
                if (!(Test-DemoOwned $candidate $Kind)) { throw 'Service identity did not match its process entrypoint.' }
                $Record.pid = $candidate.pid
                $Record.startedTicks = $candidate.startedTicks
                return
            }
            throw "Port was claimed by another $Kind instance. No unrelated process will be stopped."
        }
        if ($null -ne $Record -and !(Test-DemoOwned $Record $Kind)) {
            throw "$Kind exited during startup. Inspect $($Record.stderr)"
        }
        Start-Sleep -Milliseconds 500
    } while ([DateTime]::UtcNow -lt $until)
    throw "$Kind was not ready within $TimeoutSeconds seconds. Logs: $script:DemoRuntime"
}

function Test-DemoReplays {
    $page = Invoke-WebRequest -UseBasicParsing -Uri 'http://127.0.0.1:5173/' -TimeoutSec 5
    if ($page.StatusCode -ne 200 -or $page.Content -notmatch '<title>DemoDoctor\b' -or $page.Content -notmatch '/@vite/client') {
        throw 'Frontend application index is unavailable.'
    }
    $health = Get-DemoJson 'http://127.0.0.1:8765/api/health'
    if ($null -eq $health -or !$health.ok) { throw 'Backend health check failed.' }
    $pilot = Get-DemoJson 'http://127.0.0.1:5173/api/recorded-pilot/analysis.json'
    if ($null -eq $pilot -or $pilot.task_outcome -ne 'uncertain' -or $null -eq $pilot.recorded_evidence) { throw 'Recorded PILOT is unavailable through the frontend proxy.' }
    foreach ($episode in @('ep010', 'ep005', 'ep003', 'ep013', 'ep006')) {
        $analysis = Get-DemoJson "http://127.0.0.1:5173/data/$episode/analysis.json"
        if ($null -eq $analysis -or $analysis.episode_key -ne $episode) { throw "Cached investigation $episode is unavailable." }
        $media = Invoke-WebRequest -UseBasicParsing -Method Head -Uri "http://127.0.0.1:5173/replays/$episode/video.mp4" -TimeoutSec 5
        if ($media.StatusCode -ne 200 -or $media.Headers['Content-Type'] -notlike 'video/*') { throw "Cached video $episode is unavailable." }
    }
    # Windows PowerShell 5.1 forbids setting Range via Invoke-WebRequest -Headers.
    $request = [Net.HttpWebRequest]::Create('http://127.0.0.1:5173/api/recorded-pilot/video.mp4')
    $request.Timeout = 10000
    $request.AddRange(0, 0)
    $video = $request.GetResponse()
    try {
        if ([int]$video.StatusCode -ne 206) { throw 'Recorded PILOT video range request failed.' }
    } finally { $video.Dispose() }
}
