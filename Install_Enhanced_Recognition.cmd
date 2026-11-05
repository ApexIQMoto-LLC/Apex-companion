@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Install APEX using Install_Companion.cmd first.
 pause
 exit /b 1
)
echo.
echo Optional offline Whisper recognition can improve noisy speech accuracy.
echo Requires ~500 MB model download plus Python dependencies, installed by consent.
echo Your spoken audio remains on your PC.
echo Quit APEX before continuing and restart it after installation.
echo.
choice /M "Install and enable enhanced local speech recognition"
if errorlevel 2 exit /b 0
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-enhanced-recognition.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" "tools\install_enhanced_recognition.py"
if errorlevel 1 goto :fail
echo SUCCESS. Restart APEX.
pause
exit /b 0
:fail
echo Enhanced speech install failed. Normal Vosk + WebRTC fallback remains available.
pause
exit /b 1
