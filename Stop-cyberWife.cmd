@echo off
setlocal
set "CYBERWIFE_ROOT=%~dp0"
powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%CYBERWIFE_ROOT%ops\windows\RuntimeLauncher.ps1" -Action stop
if errorlevel 1 (
  echo cyberWife failed to stop cleanly. Review the message above.
  pause
  exit /b 1
)
endlocal
