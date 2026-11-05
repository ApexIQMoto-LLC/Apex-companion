@echo off
setlocal
cd /d "%~dp0"
echo Testing your Windows speech synthesizer and default playback output...
echo.
powershell.exe -NoProfile -NonInteractive -Command "$ErrorActionPreference='Stop'; Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; try { $s.SetOutputToDefaultAudioDevice(); $s.Volume=100; $s.Speak('Hello. This is a Windows speech output test for Apex.'); Write-Host 'SPEECH COMMAND COMPLETED. If there was no sound, check Windows output device and volume.' } finally { $s.Dispose() }"
if errorlevel 1 (
  echo.
  echo ERROR: Windows voice synthesis failed. Use Voice Output Settings or check Windows speech components.
)
echo.
pause
