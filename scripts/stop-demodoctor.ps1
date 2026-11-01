#Requires -Version 5.1
[CmdletBinding()]
param()
. "$PSScriptRoot\demodoctor-common.ps1"
$lock = Enter-DemoLock
try {
    $state = Read-DemoState
    foreach ($kind in @('frontend', 'backend')) {
        $record = $state.$kind
        if (Test-DemoOwned $record $kind) {
            Stop-DemoOwned $record $kind
            Write-Host "Stopped managed DemoDoctor $kind (PID $($record.pid))."
        } else { Write-Host "No managed $kind process to stop; other services are left alone." }
        $state.$kind = $null
    }
    Save-DemoState $state
} finally { $lock.Dispose() }
