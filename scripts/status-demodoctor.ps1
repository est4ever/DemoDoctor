#Requires -Version 5.1
[CmdletBinding()]
param()
. "$PSScriptRoot\demodoctor-common.ps1"
$lock = Enter-DemoLock
try {
    $state = Read-DemoState
    foreach ($kind in @('backend', 'frontend')) {
        $port = if ($kind -eq 'backend') { 8765 } else { 5173 }
        $identity = Get-DemoExisting $kind
        $owned = Test-DemoOwned $state.$kind $kind
        $status = if ($null -ne $identity) { 'Running' } elseif (Test-DemoPort $port) { 'Port occupied / unrecognized' } elseif ($owned) { 'Starting / unresponsive' } else { 'Stopped' }
        [pscustomobject]@{ Service = $kind; Port = $port; Status = $status; Managed = $owned; PID = $(if ($owned) { $state.$kind.pid } elseif ($null -ne $identity) { $identity.pid } else { $null }); Logs = $script:DemoRuntime }
    }
} finally { $lock.Dispose() }
