@echo off
cd /d "%~dp0"
if errorlevel 1 (
  echo Extract the ZIP to a normal folder first, then retry.
  pause
  exit /b 1
)
echo Running the installer in a persistent Command Prompt...
cmd.exe /d /k call install_windows.bat
