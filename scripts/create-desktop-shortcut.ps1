$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$target = Join-Path $repoRoot "launch-desktop.bat"
$desktop = [Environment]::GetFolderPath("Desktop")
$shortcutPath = Join-Path $desktop "BiliBookLLM.lnk"

if (-not (Test-Path $target)) {
  throw "Launch script not found: $target"
}

$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $target
$shortcut.WorkingDirectory = $repoRoot
$shortcut.IconLocation = "$env:SystemRoot\System32\shell32.dll,220"
$shortcut.Description = "Launch the local BiliBookLLM desktop app"
$shortcut.Save()

Write-Host "Desktop shortcut created:"
Write-Host $shortcutPath
