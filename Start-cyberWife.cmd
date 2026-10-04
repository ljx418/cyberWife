@echo off
setlocal
set "CYBERWIFE_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CYBERWIFE_ROOT%ops\windows\RuntimeLauncher.ps1" -Action start
if errorlevel 1 (
  echo cyberWife failed to start. Review the message above.
  pause
  exit /b 1
)
start "" "http://127.0.0.1:7860/"
endlocal
