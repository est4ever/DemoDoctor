"""Windows 5.1 command forwarding/profile regression tests. Never start providers."""
from pathlib import Path
import json
import shutil
import subprocess

import pytest

ROOT = Path(__file__).resolve().parents[1]
POWERSHELL = shutil.which("powershell.exe")
pytestmark = pytest.mark.skipif(not POWERSHELL, reason="Windows PowerShell required")


def run_ps(tmp_path, code):
    script = tmp_path / "check.ps1"
    script.write_text("$ErrorActionPreference = 'Stop'\n" + code, encoding="utf-8-sig")
    return subprocess.run(
        [POWERSHELL, "-NoLogo", "-NoProfile", "-NonInteractive", "-File", str(script)],
        cwd=tmp_path, capture_output=True, text=True, check=True, timeout=30,
    ).stdout


@pytest.fixture
def scripts(tmp_path):
    scripts = tmp_path / "scripts"
    scripts.mkdir()
    for name in ("start-demodoctor-real-analysis.ps1", "register-demodoctor.ps1", "demodoctor-common.ps1"):
        shutil.copyfile(ROOT / "scripts" / name, scripts / name)
    # Capture dispatch instead of launching any service or loading credentials.
    (scripts / "start-demodoctor.ps1").write_text(
        "param([switch]$RealAnalysis,[string]$CredentialsFile,[double]$PerRunBudgetUsd,"
        "[string]$Python,[switch]$NoBrowser,[int]$TimeoutSeconds)\n"
        "$PSBoundParameters | ConvertTo-Json -Compress\n", encoding="utf-8",
    )
    return scripts


def test_dedicated_command_forwards_explicit_options(scripts, tmp_path):
    result = json.loads(run_ps(tmp_path, r"""
& './scripts/start-demodoctor-real-analysis.ps1' -CredentialsFile 'C:\private folder\providers.env' -PerRunBudgetUsd 2.10 -Python 'C:\python path\python.exe' -NoBrowser -TimeoutSeconds 35
"""))
    assert result == {
        "RealAnalysis": {"IsPresent": True}, "CredentialsFile": r"C:\private folder\providers.env",
        "PerRunBudgetUsd": 2.1, "Python": r"C:\python path\python.exe",
        "NoBrowser": {"IsPresent": True}, "TimeoutSeconds": 35,
    }


def test_omitted_budget_and_credentials_are_not_overridden(scripts, tmp_path):
    result = json.loads(run_ps(tmp_path, "& './scripts/start-demodoctor-real-analysis.ps1'"))
    assert result == {"RealAnalysis": {"IsPresent": True}}
    # Validation occurs before the shared launcher runs.
    result = run_ps(tmp_path, """
try { & './scripts/start-demodoctor-real-analysis.ps1' -PerRunBudgetUsd 0; throw 'accepted invalid cap' }
catch { if ($_.FullyQualifiedErrorId -notlike 'ParameterArgumentValidationError*') { throw }; 'invalid cap rejected' }
""")
    assert result.strip() == "invalid cap rejected"


def test_registration_preserves_other_functions_and_loads_in_new_process(scripts, tmp_path):
    run_ps(tmp_path, """
$profilePath = Join-Path $PWD 'test-profile.ps1'
[IO.File]::WriteAllText($profilePath, "function Unrelated-Command { 'preserved' }`r`n")
$PROFILE = [pscustomobject]@{ CurrentUserCurrentHost = $profilePath }
& './scripts/register-demodoctor.ps1'
$first = [IO.File]::ReadAllText($profilePath)
& './scripts/register-demodoctor.ps1'
if ($first -cne [IO.File]::ReadAllText($profilePath)) { throw 'not idempotent' }
""")
    result = json.loads(run_ps(tmp_path, """
. './test-profile.ps1'
if ((Unrelated-Command) -ne 'preserved') { throw 'unrelated function lost' }
if ((Get-Command DemoDoctor).Definition -notlike '*start-demodoctor.ps1*') { throw 'offline command changed' }
if (!(Get-Command DemoDoctor-Stop) -or !(Get-Command DemoDoctor-Status)) { throw 'existing commands missing' }
DemoDoctor-RealAnalysis -PerRunBudgetUsd 2.10 -NoBrowser
"""))
    assert result["RealAnalysis"]["IsPresent"]
    assert result["PerRunBudgetUsd"] == 2.1
