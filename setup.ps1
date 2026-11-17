# One-time setup for Lucy: creates the Python environment, installs the
# dependencies and adds Start menu + Desktop shortcuts.
#
#   powershell -ExecutionPolicy Bypass -File setup.ps1
#
# The environment lives outside the project folder (in %USERPROFILE%\.venvs)
# because long project paths can exceed Windows' 260-character path limit.
$ErrorActionPreference = "Stop"

$venv = Join-Path $env:USERPROFILE ".venvs\gesture-volume"
$python = Join-Path $venv "Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Host "Creating Python environment in $venv"
    python -m venv $venv
}

Write-Host "Installing dependencies"
& $python -m pip install --quiet --upgrade pip
& $python -m pip install --quiet -r (Join-Path $PSScriptRoot "requirements.txt")

& (Join-Path $PSScriptRoot "install_shortcuts.ps1")
Write-Host "`nDone. Launch 'Lucy' from the Start menu or your desktop."
