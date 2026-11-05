@echo off
setlocal
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo APEX is not installed. Run Install_Companion.cmd first.
 pause
 exit /b 1
)
echo.
echo Install optional free local Kokoro natural speech (~140 MB model files).
echo Models download from the original kokoro-onnx GitHub release.
echo No audio or recognized text is sent to this service.
echo The optional Python runtime is installed only after you confirm.
echo.
choice /M "Install the offline natural voice"
if errorlevel 2 exit /b 0
".venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r requirements-natural-voice.txt
if errorlevel 1 goto :fail
".venv\Scripts\python.exe" "tools\install_natural_voice.py"
if errorlevel 1 goto :fail
echo SUCCESS. Restart APEX and select Kokoro in VOICE OUTPUT SETTINGS.
pause
exit /b 0
:fail
echo Natural voice setup failed. Existing Windows speech remains available.
pause
exit /b 1
