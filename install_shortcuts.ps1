# Creates "Lucy" shortcuts that start the app quietly (no console window).
#
#   powershell -ExecutionPolicy Bypass -File install_shortcuts.ps1            # Start menu + Desktop
#   powershell -ExecutionPolicy Bypass -File install_shortcuts.ps1 -Startup   # also start with Windows
#   powershell -ExecutionPolicy Bypass -File install_shortcuts.ps1 -Remove    # remove all shortcuts
#
# Re-run it if you move this folder.
param([switch]$Startup, [switch]$Remove)

$project = $PSScriptRoot
$pythonw = Join-Path $env:USERPROFILE ".venvs\gesture-volume\Scripts\pythonw.exe"
$name    = "Lucy.lnk"
$places  = @{
    StartMenu = Join-Path ([Environment]::GetFolderPath("Programs")) $name
    Desktop   = Join-Path ([Environment]::GetFolderPath("Desktop"))  $name
    Startup   = Join-Path ([Environment]::GetFolderPath("Startup"))  $name
}

if ($Remove) {
    foreach ($p in $places.Values) { if (Test-Path $p) { Remove-Item $p; "Removed $p" } }
    return
}

if (-not (Test-Path $pythonw)) { throw "Python environment not found at $pythonw" }

$targets = @("StartMenu", "Desktop")
if ($Startup) { $targets += "Startup" }

$shell = New-Object -ComObject WScript.Shell
foreach ($t in $targets) {
    $lnk = $shell.CreateShortcut($places[$t])
    $lnk.TargetPath       = $pythonw
    $lnk.Arguments        = '"' + (Join-Path $project "server.py") + '"'
    $lnk.WorkingDirectory = $project
    $lnk.IconLocation     = "$env:SystemRoot\System32\SndVol.exe,0"
    $lnk.Description      = "Control the volume with hand gestures"
    $lnk.Save()
    "Created $($places[$t])"
}
