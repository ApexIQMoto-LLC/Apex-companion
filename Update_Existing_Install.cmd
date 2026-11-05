@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if errorlevel 1 (
  echo ERROR: Could not access the extracted APEX v0.11.0 files.
  pause
  exit /b 1
)
if not exist "companion\personal_intelligence.py" (
  echo ERROR: Extract the complete APEX v0.10 ZIP first.
  pause
  exit /b 1
)
echo.
echo ===========================================================
echo  APEX BUSINESS + PERSONAL v0.11.0 - SAFE WINDOWS UPDATE
 echo ===========================================================
echo.
echo Close APEX completely before continuing.
echo This updater PRESERVES .env, config.json, data, .venv,
echo all local memory databases, and Windows Credential Manager.
echo Dependencies are installed BEFORE existing code is replaced.
echo.
set "TARGET=C:\ApexIQCompanion"
if not exist "%TARGET%\main.py" (
  echo Installed APEX not found at C:\ApexIQCompanion.
  set /p "TARGET=Paste your existing APEX installation folder: "
)
if not exist "%TARGET%\main.py" (
  echo ERROR: The selected folder does not contain an existing main.py.
  pause
  exit /b 1
)
for %%I in ("%TARGET%") do set "TARGET=%%~fI"
set "SOURCE=%~dp0."
for %%I in ("%SOURCE%") do set "SOURCE=%%~fI"
if /I "%SOURCE%"=="%TARGET%" (
  echo This extracted folder is already the installed APEX folder.
  echo Run Install_Companion.cmd to check dependencies; no update copying is needed.
  pause
  exit /b 0
)
echo.
echo Existing installation: %TARGET%
choice /M "Proceed with safe APEX v0.11.0 upgrade"
if errorlevel 2 (
  echo Cancelled; your installation is unchanged.
  pause
  exit /b 0
)
set "LOG=%TEMP%\ApexIQ-v0.11.0-Update.log"
> "%LOG%" echo APEX v0.11.0 update diagnostics
if not exist "%TARGET%\.venv\Scripts\python.exe" (
  echo ERROR: Existing Python virtual environment is missing.
  echo Open the existing installation folder, run Install_Companion.cmd,
  echo then rerun this updater.
  pause
  exit /b 1
)
echo.
echo [1/5] Installing and validating required Python packages...
"%TARGET%\.venv\Scripts\python.exe" -m pip install --disable-pip-version-check -r "%SOURCE%\requirements.txt" >> "%LOG%" 2>&1
if errorlevel 1 (
  echo ERROR: Dependency installation failed; existing APEX code is unchanged.
  echo Check %LOG%
  powershell.exe -NoProfile -Command "Get-Content -LiteralPath $env:LOG -Tail 20" 2>nul
  pause
  exit /b 1
)
echo [2/5] Backing up current application code...
set "BACKUP=%TARGET%\data\upgrade_backups\before_v0_11_0_%RANDOM%%RANDOM%"
if not exist "%BACKUP%" mkdir "%BACKUP%"
if not exist "%BACKUP%" goto :backup_fail
copy /Y "%TARGET%\main.py" "%BACKUP%\main.py" > nul
if errorlevel 1 goto :backup_fail
if exist "%TARGET%\companion\" (
  robocopy "%TARGET%\companion" "%BACKUP%\companion" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XD __pycache__ > "%LOG%.backup" 2>&1
  if errorlevel 8 goto :backup_fail
)
echo [3/5] Installing upgraded source; leaving credentials and private data untouched...
robocopy "%SOURCE%" "%TARGET%" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP /XF .env config.json install.log usage.sqlite3 activity.jsonl *.sqlite3 *.sqlite3-shm *.sqlite3-wal /XD .venv data __pycache__ .git > "%LOG%.copy" 2>&1
if errorlevel 8 goto :copy_fail
echo [4/5] Verifying importable v0.11.0 operations and natural-voice modules...
"%TARGET%\.venv\Scripts\python.exe" -c "import cryptography, keyring; from companion.personal_intelligence import PersonalIntelStore; from companion.autonomy import SmallFixAutonomy; from companion.private_imports import EncryptedImportVault; from companion.phone_brief import PhoneBriefing; from companion.holographic_ui import HolographicCore; from companion.away_mode import AwayMonitor; from companion.operations_queue import OperationsQueue; from companion.operations_unity import UnityEditModeRunner, VerifiedPatchTrial; from companion.operations_phone import RemoteOperations; from companion.operations_desktop import DesktopInspector; from companion.business_studio import BusinessStudioStore; from companion.social_auth import WindowsVault, OAuthFlow; from companion.conversation import ConversationSession; from companion.mini_ui import MiniCompanion; from companion.tray import TrayController; from companion.speech_output import WindowsSpeech, build_windows_speech_command; from companion.voice_processing import SpeechGate, PauseAwareTurn; from companion.natural_voice import NaturalVoice; from companion.model_router import routes_for, detect_task, LOCAL_PROVIDERS; import pystray; print('APEX 0.11 model router/voice/tray dependencies present')" >> "%LOG%" 2>&1
if errorlevel 1 goto :verify_fail
echo [5/5] Applying one-time always-on sensor migration...
"%TARGET%\.venv\Scripts\python.exe" "%TARGET%\tools\enable_hologram_defaults.py" "%TARGET%" >> "%LOG%" 2>&1
if errorlevel 1 goto :verify_fail
echo.
echo SUCCESS: APEX v0.11.0 updated safely.
echo Existing API key, cloud session, preferences, memory, and data remain intact.
echo Backup of PREVIOUS CODE: %BACKUP%
echo.
echo Start APEX quietly from the tray using: %TARGET%\Launch_Companion.cmd
echo Phone: run %TARGET%\Pair_Phone.cmd when you want Telegram briefings.
pause
exit /b 0
:backup_fail
echo ERROR: Could not make the original code backup. No new app code was copied.
echo Check permissions in %TARGET%\data\upgrade_backups
pause
exit /b 1
:copy_fail
echo ERROR: Update copy failed. Restoring previous code from: %BACKUP%
goto :restore
:verify_fail
echo ERROR: The new app did not verify. Restoring previous code from: %BACKUP%
:restore
if exist "%BACKUP%\main.py" copy /Y "%BACKUP%\main.py" "%TARGET%\main.py" > nul
if exist "%BACKUP%\companion\" robocopy "%BACKUP%\companion" "%TARGET%\companion" /E /R:1 /W:1 /NFL /NDL /NJH /NJS /NP > "%LOG%.restore" 2>&1
echo Check updater diagnostics: %LOG%
echo Existing .env, config.json, data and .venv were not overwritten.
pause
exit /b 1
