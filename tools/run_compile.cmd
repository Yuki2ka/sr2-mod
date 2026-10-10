@echo off
rem ---------------------------------------------------------------------------
rem  Double-click build for the SR2HD mod in this repo.
rem
rem  All settings live in run_compile.py (SETTINGS block at the top).
rem  This .cmd only makes sure Python is found and the window stays open.
rem ---------------------------------------------------------------------------
setlocal
chcp 65001 >nul

set "SCRIPT_DIR=%~dp0"

rem Prefer the Windows Python launcher, fall back to plain python.
where py >nul 2>&1
if %ERRORLEVEL%==0 (
    py -3 "%SCRIPT_DIR%run_compile.py" %*
) else (
    python "%SCRIPT_DIR%run_compile.py" %*
)

set "RC=%ERRORLEVEL%"
echo.
echo exit code: %RC%
pause
endlocal & exit /b %RC%
