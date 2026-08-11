@echo off
setlocal
set "CHROME=%ProgramFiles%\Google\Chrome\Application\chrome.exe"
set "PROFILE=C:\ChatGPT_Automation_Profile"
if not exist "%CHROME%" (
  echo Chrome not found: %CHROME%
  exit /b 2
)
start "WebGPT Reviewer Chrome" "%CHROME%" --remote-debugging-port=9222 --user-data-dir="%PROFILE%"
endlocal
