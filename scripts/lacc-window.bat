@echo off
REM Opens the LACC window. Reads only: it runs no skill and calls no model.
REM Verified by scripts/SHA256SUMS.txt and by the test suite (ADR-071).
setlocal
cd /d "%~dp0.."

if "%~1"=="" (set CONFIG=configs/config.yaml) else (set CONFIG=%~1)

echo Opening the window with %CONFIG%
REM Through run.ps1, never `uv` directly: the wrapper points UV_PROJECT_ENVIRONMENT
REM outside this folder. Calling uv here builds a .venv inside it, which a synchroniser
REM then locks mid-build - the failure run.ps1 exists to prevent (ADR-084).
powershell -NoProfile -ExecutionPolicy Bypass -File "run.ps1" run lacc window -c "%CONFIG%"
if errorlevel 1 (
  echo.
  echo The window did not open. If the toolkit is missing, run:
  echo     .un.ps1 sync --extra gui
  pause
)
endlocal
