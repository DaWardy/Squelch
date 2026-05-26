@echo off
:: Squelch installer — VERBOSE mode for debugging install failures
:: Shows full pip output so you can see exactly what fails
setlocal
cd /d "%~dp0"
set PIP_DISABLE_PIP_VERSION_CHECK=1

echo.
echo ================================================================
echo  Squelch Setup — VERBOSE (debug) mode
echo  Full pip output will be shown.
echo ================================================================
echo.

set PYTHON=
for %%V in (3.13 3.12 3.11 3) do (
    if "%PYTHON%"=="" (
        py -%%V -c "import sys; sys.exit(0)" >nul 2>&1
        if not errorlevel 1 set PYTHON=py -%%V
    )
)
if "%PYTHON%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON=python
)
if "%PYTHON%"=="" (
    echo  ERROR: Python not found. Install from python.org
    exit /b 1
)

echo  Using: %PYTHON%
%PYTHON% installer.py --verbose

echo.
echo ================================================================
echo  Setup finished. Scroll up to review the full output.
echo ================================================================
