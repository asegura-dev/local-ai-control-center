@echo off
REM Checks every script here against scripts/SHA256SUMS.txt.
REM
REM What this proves and what it does not: it proves the files on this disk are the ones
REM the digests were taken over. It does not prove those digests are honest - anyone who
REM could edit a script could edit the list beside it. What makes it worth something is
REM that both are in Git, so `git log scripts/` shows when either changed (ADR-071).
setlocal enabledelayedexpansion
cd /d "%~dp0"

set FAILED=0
for /f "tokens=1,2" %%A in (SHA256SUMS.txt) do (
  if exist "%%B" (
    for /f %%H in ('powershell -NoProfile -Command "(Get-FileHash -Algorithm SHA256 '%%B').Hash.ToLower()"') do (
      if /i "%%H"=="%%A" (echo   ok       %%B) else (echo   CHANGED  %%B& set FAILED=1)
    )
  ) else (echo   MISSING  %%B& set FAILED=1)
)

if "!FAILED!"=="1" (
  echo.
  echo Something here is not what was recorded. Check `git log scripts/` before running it.
  exit /b 1
)
echo.
echo Every script matches what was recorded.
endlocal
