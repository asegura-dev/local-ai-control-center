@echo off
REM Opens the LACC window. Reads only: it runs no skill and calls no model.
REM Verified by scripts/SHA256SUMS.txt and by the test suite (ADR-071).
setlocal
cd /d "%~dp0.."

if "%~1"=="" (set CONFIG=configs/config.yaml) else (set CONFIG=%~1)

echo Opening the window with %CONFIG%
uv run --extra gui lacc window -c "%CONFIG%"
if errorlevel 1 (
  echo.
  echo The window did not open. If the toolkit is missing, run:
  echo     uv sync --extra gui
  pause
)
endlocal
