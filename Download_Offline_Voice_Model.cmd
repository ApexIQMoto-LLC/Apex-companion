@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo Install APEX first by running Install_Companion.cmd.
  pause
  exit /b 1
)
echo.
echo This downloads the official Vosk offline English model (~40 MB).
echo Voice audio stays local to your PC; only recognized text can reach the AI on your request.
echo.
choice /M "Download and install the offline voice model"
if errorlevel 2 exit /b 0
".venv\Scripts\python.exe" "tools\install_vosk_model.py"
if errorlevel 1 (
 echo Voice model setup failed. Check the error above.
 pause
 exit /b 1
)
pause
