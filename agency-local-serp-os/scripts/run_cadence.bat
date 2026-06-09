@echo off
REM Cadence launcher for Windows Task Scheduler.
REM   Usage: run_cadence.bat <daily|weekly|monthly> [client] [--dry-run]
REM Resolves the repo root from this file's location, loads the repo .env (via cadence.py),
REM logs stdout+stderr and the exit code to logs\cadence_<freq>.log.
setlocal
set "REPO=%~dp0.."
set "FREQ=%~1"
set "CLIENT=%~2"
if "%FREQ%"=="" set "FREQ=daily"
if "%CLIENT%"=="" set "CLIENT=example-hvac-client"
if not exist "%REPO%\logs" mkdir "%REPO%\logs"
cd /d "%REPO%"
echo ============================================================ >> "%REPO%\logs\cadence_%FREQ%.log"
echo [%date% %time%] cadence %FREQ% for %CLIENT% %3 >> "%REPO%\logs\cadence_%FREQ%.log"
"C:\Python312\python.exe" "%REPO%\scripts\cadence.py" --frequency %FREQ% --client %CLIENT% %3 >> "%REPO%\logs\cadence_%FREQ%.log" 2>&1
echo [%date% %time%] exit code %ERRORLEVEL% >> "%REPO%\logs\cadence_%FREQ%.log"
endlocal
