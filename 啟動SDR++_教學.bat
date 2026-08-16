@echo off
setlocal
set "APPDIR=%~dp0sdrpp_windows_x64"
set "CFG=%~dp0sdrpp_config"
if not exist "%APPDIR%\sdrpp.exe" (
  echo [ERROR] sdrpp.exe not found in "%APPDIR%"
  pause
  exit /b 1
)
cd /d "%APPDIR%"
start "" "sdrpp.exe" -r "%CFG%"
endlocal
