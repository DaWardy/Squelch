@echo off
:: Squelch installer — double-click this to set up Squelch
:: This launches installer.py, NOT install_check.py

setlocal
cd /d "%~dp0"
set PIP_DISABLE_PIP_VERSION_CHECK=1

echo.
echo ================================================================
echo  Squelch Setup
echo  This will install Python packages and create a virtual env.
echo ================================================================
echo.

:: Find Python — prefer 3.12/3.13 over 3.14+ (wheel compatibility)
set PYTHON=
for %%V in (3.13 3.12 3.11 3) do (
    if "%PYTHON%"=="" (
        py -%%V -c "import sys; sys.exit(0)" >nul 2>&1
        if not errorlevel 1 set PYTHON=py -%%V
    )
)

:: Fall back to default python
if "%PYTHON%"=="" (
    python --version >nul 2>&1
    if not errorlevel 1 set PYTHON=python
)

if "%PYTHON%"=="" (
    echo  ERROR: Python not found.
    echo  Install Python 3.11, 3.12, or 3.13 from python.org
    echo  https://www.python.org/downloads/
    echo.
    pause
    exit /b 1
)

echo  Using: %PYTHON%
%PYTHON% --version
echo.

%PYTHON% installer.py %*

echo.
echo ================================================================
echo  Setup finished. Window will stay open so you can read messages.
echo ================================================================
pause
