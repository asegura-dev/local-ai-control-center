@echo off
REM Starts Ollama on THIS machine with an 8-bit KV cache.
REM
REM Measured on this project: at a 32k window the KV cache costs about 8.6 GB in fp16
REM and about 4.3 GB at q8_0 - roughly 4 GB of VRAM back, for free, before any hardware
REM decision. That figure is in the log and is the reason this script exists.
REM
REM It sets variables for this session only. Nothing global is changed, nothing is
REM downloaded, and nothing is sent anywhere (ADR-071).
setlocal

set OLLAMA_KV_CACHE_TYPE=q8_0
set OLLAMA_FLASH_ATTENTION=1

REM Bind to loopback unless a host is given as the first argument. A host that is not
REM loopback makes this machine reachable from your network - pass one deliberately.
if "%~1"=="" (set OLLAMA_HOST=127.0.0.1:11434) else (set OLLAMA_HOST=%~1)

echo KV cache : %OLLAMA_KV_CACHE_TYPE%
echo Listening: %OLLAMA_HOST%
echo.
ollama serve
endlocal
