#Requires -Version 5.1
# Integration checks use only localhost and packaged replays. Requires both ports free.
[CmdletBinding()]
param([switch]$OpenBrowser)
. "$PSScriptRoot\demodoctor-common.ps1"
if ((Test-DemoPort 8765) -or (Test-DemoPort 5173)) {
    throw 'Launcher integration tests require ports 8765 and 5173 free. No existing process was stopped.'
}
function Assert-Launcher([bool]$Condition, [string]$Message) {
    if (!$Condition) { throw "FAIL: $Message" }
    Write-Host "PASS: $Message"
}
try {
    & "$PSScriptRoot\start-demodoctor.ps1" -NoBrowser:(!$OpenBrowser)
    $cold = Read-DemoState
    Assert-Launcher ((Test-DemoOwned $cold.backend 'backend') -and (Test-DemoOwned $cold.frontend 'frontend')) 'cold launch owns both services'
    & "$PSScriptRoot\start-demodoctor.ps1" -NoBrowser
    $repeat = Read-DemoState
    Assert-Launcher ($repeat.backend.pid -eq $cold.backend.pid -and $repeat.frontend.pid -eq $cold.frontend.pid) 'repeat launch reuses both PIDs'
    Stop-DemoOwned $repeat.backend 'backend'
    & "$PSScriptRoot\start-demodoctor.ps1" -NoBrowser
    $recovered = Read-DemoState
    Assert-Launcher ($recovered.backend.instance -ne $cold.backend.instance -and $recovered.frontend.pid -eq $cold.frontend.pid) 'backend recovery preserves frontend'
    Test-DemoReplays
    Assert-Launcher $true 'PILOT through proxy plus all five cached investigations and videos'
    $identity = Get-DemoIdentity 'backend'
    Assert-Launcher ($identity.offline -eq $true) 'launcher backend advertises offline-only mode (guard tested with provider stubs)'
} finally { & "$PSScriptRoot\stop-demodoctor.ps1" }
Assert-Launcher (!(Test-DemoPort 8765) -and !(Test-DemoPort 5173)) 'clean shutdown releases both ports'

foreach ($port in @(8765, 5173)) {
    $listener = New-Object Net.Sockets.TcpListener([Net.IPAddress]::Loopback, $port)
    $listener.Start()
    try {
        $refused = $false
        try { & "$PSScriptRoot\start-demodoctor.ps1" -NoBrowser }
        catch { $refused = $_.Exception.Message -like "*Port $port is occupied*" }
        Assert-Launcher ($refused -and (Test-DemoPort $port)) "unrelated listener on $port is refused and left alive"
    } finally { $listener.Stop() }
}
# A corrupted/stale PID record must not authorize stopping another executable.
$current = Get-Process -Id $PID
$state = Read-DemoState
$state.backend = [pscustomobject]@{ pid = $PID; startedTicks = $current.StartTime.ToUniversalTime().Ticks.ToString() }
Save-DemoState $state
& "$PSScriptRoot\stop-demodoctor.ps1"
Assert-Launcher ($null -ne (Get-Process -Id $PID)) 'unrelated PID in ownership file is not killed'
Write-Host 'All launcher integration checks passed.'
