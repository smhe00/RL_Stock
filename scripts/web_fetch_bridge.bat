@echo off
REM Web Fetch Bridge V1 — Windows launcher (marker-driven wake-up bridge).
REM Prerequisites: dedicated Chrome profile + localhost CDP endpoint
REM (http://127.0.0.1:9222) + config/web_fetch_bridge.local.toml with
REM target_conversation_url filled (ignored local config; never commit URL).
setlocal
cd /d "%~dp0.."
set PY=.venv\Scripts\python.exe
if not exist "%PY%" (
  echo .venv\Scripts\python.exe not found. Run bootstrap first.
  exit /b 2
)
set CFG=config\web_fetch_bridge.local.toml
if not exist "%CFG%" (
  echo Missing local config: %CFG%  (copy from web_fetch_bridge.example.toml)
  exit /b 2
)
if "%~1"=="--check" (
  "%PY%" scripts\web_fetch_bridge.py --config "%CFG%" --check
  exit /b %errorlevel%
)
if "%~1"=="" (
  echo Usage: web_fetch_bridge.bat --check ^| --handoff ^<id^> [--wait-ack]
  exit /b 2
)
"%PY%" scripts\web_fetch_bridge.py --config "%CFG%" %*
exit /b %errorlevel%
