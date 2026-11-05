@echo off
setlocal EnableExtensions
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo APEX diagnostics: Python environment not installed.
 echo Run Install_Companion.cmd first.
 pause
 exit /b 1
)
echo APEX v0.8.0 - safe diagnostics (no keys displayed)
".venv\Scripts\python.exe" -c "from companion.holographic_ui import HolographicCore; from companion.away_mode import AwayMonitor; from companion.autonomy import SmallFixAutonomy; from companion.phone_brief import PhoneBriefing; from companion.operations_queue import OperationsQueue; from companion.operations_unity import UnityEditModeRunner; from companion.operations_phone import RemoteOperations; from companion.operations_desktop import DesktopInspector; from companion.settings import load_settings; import importlib.util; s=load_settings(); print('Core modules: OK'); print('Camera autostart:',bool(s.get('camera_autostart'))); print('Microphone autostart:',bool(s.get('microphone_autostart'))); print('Voice model: configured' if importlib.util.find_spec('vosk') else 'Voice model package not installed'); print('Approved project configured:',bool(s.get('approved_project_root'))); print('Phone delivery enabled:',bool(s.get('phone_brief_enabled'))); print('Unity tests permitted:',bool(s.get('ops_allow_unity_tests'))); print('Private phone commands enabled:',bool(s.get('ops_phone_commands')))"
if errorlevel 1 echo ERROR: One or more modules are unavailable. Re-run Install_Companion.cmd.
pause
