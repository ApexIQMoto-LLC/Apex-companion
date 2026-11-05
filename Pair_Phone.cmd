@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install APEX Companion first so the required keyring package is present.
  pause
  exit /b 1
)
".venv\Scripts\python.exe" "tools\setup_telegram.py"
echo.
pause
