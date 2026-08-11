@echo off
setlocal
if "%~1"=="" (
  echo Usage: run_daemon.bat ^<path-to-bridge.local.toml^>
  exit /b 2
)
webgpt-bridge daemon --config "%~1"
endlocal
