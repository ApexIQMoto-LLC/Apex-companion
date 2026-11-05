$ErrorActionPreference = 'Stop'
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$pythonw = Join-Path $root '.venv\Scripts\pythonw.exe'
$script = Join-Path $root 'main.py'
if (-not (Test-Path $pythonw)) { throw 'Run install_windows.bat first to create the Python environment.' }
if (-not (Test-Path $script)) { throw 'main.py not found. Extract the entire Companion folder.' }
$startup = [Environment]::GetFolderPath('Startup')
$shortcutPath = Join-Path $startup 'ApexIQ Companion.lnk'
$shell = New-Object -ComObject WScript.Shell
$shortcut = $shell.CreateShortcut($shortcutPath)
$shortcut.TargetPath = $pythonw
$shortcut.Arguments = '"' + $script + '"'
$shortcut.WorkingDirectory = $root
$shortcut.Description = 'Start ApexIQ Companion when this Windows user signs in'
$shortcut.Save()
Write-Host 'Installed startup shortcut:' $shortcutPath
Write-Host 'It starts after Windows sign-in; it does not run while the PC is off or asleep.'
