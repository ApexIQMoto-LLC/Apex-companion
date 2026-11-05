@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\pythonw.exe" (
  echo APEX is not installed. Run Install_Companion.cmd first.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "main.py"
exit /b 0
