@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: Cannot access the extracted companion folder.
  echo Unzip the entire package to a local folder such as C:\ApexIQCompanion.
  pause
  exit /b 1
)
set "APEXIQ_INSTALL_LOG=%CD%\install.log"
> "%APEXIQ_INSTALL_LOG%" echo ApexIQ Companion Installer v0.10.0
>> "%APEXIQ_INSTALL_LOG%" echo Source folder: %CD%

echo.
echo === ApexIQ Companion - Windows Installation v0.10.0 ===
echo Current folder: %CD%
echo Log file: %APEXIQ_INSTALL_LOG%
echo.
if not exist "requirements.txt" (
 echo ERROR: requirements.txt is missing. Extract the full ZIP first.
 goto :failed
)

set "PYTHON_CMD=py -3.12"
py -3.12 -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)" >> "%APEXIQ_INSTALL_LOG%" 2>&1
if errorlevel 1 (
  set "PYTHON_CMD=python"
  python -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)" >> "%APEXIQ_INSTALL_LOG%" 2>&1
  if errorlevel 1 goto :python_missing
)

echo [1/4] Creating or checking Python virtual environment...
if not exist ".venv\Scripts\python.exe" (
  %PYTHON_CMD% -m venv ".venv" >> "%APEXIQ_INSTALL_LOG%" 2>&1
  if errorlevel 1 goto :venv_failed
)
".venv\Scripts\python.exe" -c "import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) and sys.maxsize > 2**32 else 1)" >> "%APEXIQ_INSTALL_LOG%" 2>&1
if errorlevel 1 (
  echo Existing .venv uses the wrong Python version. Rename or remove .venv, then rerun.
  goto :failed
)

echo [2/4] Checking pip...
".venv\Scripts\python.exe" -m pip --version >> "%APEXIQ_INSTALL_LOG%" 2>&1
if errorlevel 1 (
  ".venv\Scripts\python.exe" -m ensurepip --upgrade >> "%APEXIQ_INSTALL_LOG%" 2>&1
  if errorlevel 1 goto :pip_failed
)

echo [3/4] Installing dependencies... progress and errors go to install.log.
".venv\Scripts\python.exe" -m pip install -r "requirements.txt" >> "%APEXIQ_INSTALL_LOG%" 2>&1
if errorlevel 1 goto :deps_failed

echo [4/4] Preparing local configuration...
if not exist "config.json" copy /Y "config.example.json" "config.json" >> "%APEXIQ_INSTALL_LOG%" 2>&1
if not exist ".env" copy /Y ".env.example" ".env" >> "%APEXIQ_INSTALL_LOG%" 2>&1
if not exist "config.json" goto :config_failed
if not exist ".env" goto :config_failed

echo.
echo SUCCESS: Installation complete. Run start_windows.bat next.
echo APEX starts quietly in the Windows tray. Open via Launch_Companion.cmd.
echo Log: %APEXIQ_INSTALL_LOG%
pause
exit /b 0

:python_missing
echo ERROR: Python 3.12 x64 not found by either 'py -3.12' or 'python'.
echo Install Python 3.12 (64-bit) from https://www.python.org/downloads/windows/
goto :failed
:venv_failed
echo ERROR: Couldn't create the .venv folder. Check disk space or folder permissions.
goto :failed
:pip_failed
echo ERROR: pip is missing or broken in the virtual environment.
goto :failed
:deps_failed
echo ERROR: A Python dependency failed to install. Check install.log below.
goto :failed
:config_failed
echo ERROR: Could not create config.json or .env. Check folder permissions.
goto :failed
:failed
echo.
echo === Installer diagnostics (last 30 log lines) ===
powershell.exe -NoProfile -Command "Get-Content -LiteralPath $env:APEXIQ_INSTALL_LOG -Tail 30" 2>nul
echo.
echo The complete diagnostic log is here: %APEXIQ_INSTALL_LOG%
echo Please copy the ERROR and last relevant log lines when requesting help.
pause
exit /b 1
