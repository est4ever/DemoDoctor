#Requires -Version 5.1
# Explicit, current-user registration. Run only after testing start/status/stop.
[CmdletBinding()]
param()
. "$PSScriptRoot\demodoctor-common.ps1"
$profilePath = $PROFILE.CurrentUserCurrentHost
$content = if (Test-Path -LiteralPath $profilePath) { [IO.File]::ReadAllText($profilePath) } else { '' }
$begin = '# BEGIN DemoDoctor launcher'
$end = '# END DemoDoctor launcher'
$scriptDirectory = $PSScriptRoot.Replace("'", "''")
$block = @"
$begin
function DemoDoctor { & '$scriptDirectory\start-demodoctor.ps1' @args }
function DemoDoctor-Status { & '$scriptDirectory\status-demodoctor.ps1' @args }
function DemoDoctor-Stop { & '$scriptDirectory\stop-demodoctor.ps1' @args }
$end
"@
$pattern = '(?ms)^# BEGIN DemoDoctor launcher\r?\n.*?^# END DemoDoctor launcher\r?\n?'
if ($content.Contains($begin)) {
    if (![regex]::IsMatch($content, $pattern)) { throw 'Incomplete DemoDoctor profile block; repair it manually first.' }
    $updated = [regex]::Replace($content, $pattern, [Text.RegularExpressions.MatchEvaluator]{ param($match) $block + [Environment]::NewLine })
} else { $updated = $content + [Environment]::NewLine + $block + [Environment]::NewLine }
# Parse before replacing the profile, preserving all unrelated content.
$tokens = $null; $parseErrors = $null
[Management.Automation.Language.Parser]::ParseInput($updated, [ref]$tokens, [ref]$parseErrors) | Out-Null
if ($parseErrors) { throw 'Profile parse failed. No profile was changed.' }
[IO.Directory]::CreateDirectory((Split-Path $profilePath -Parent)) | Out-Null
[IO.Directory]::CreateDirectory($script:DemoRuntime) | Out-Null
if (Test-Path -LiteralPath $profilePath) {
    Copy-Item -LiteralPath $profilePath -Destination (Join-Path $script:DemoRuntime ("profile-backup-" + [Guid]::NewGuid().ToString('N') + '.ps1'))
}
[IO.File]::WriteAllText($profilePath, $updated, (New-Object Text.UTF8Encoding($true)))
Write-Host "Registered DemoDoctor, DemoDoctor-Status and DemoDoctor-Stop in $profilePath"
Write-Host 'Open a new Windows PowerShell terminal. No PATH or execution-policy changes were made.'
