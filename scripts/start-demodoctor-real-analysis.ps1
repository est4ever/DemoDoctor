#Requires -Version 5.1
# Explicit local opt-in. Credentials are loaded only by the backend child process.
[CmdletBinding()]
param(
    [string]$CredentialsFile,
    [ValidateRange(0.01, 10)][double]$PerRunBudgetUsd,
    [string]$Python,
    [switch]$NoBrowser,
    [ValidateRange(10, 180)][int]$TimeoutSeconds = 90
)

# Forward only supplied parameters: omitting the budget must preserve the ledger.
# The shared launcher retains ownership, origin, approval and offline-mode guards.
& "$PSScriptRoot\start-demodoctor.ps1" -RealAnalysis @PSBoundParameters
