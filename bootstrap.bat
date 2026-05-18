@echo off
:: Squelch Bootstrap — calls Python installer
:: For full setup use: python installer.py
:: This batch file is a thin wrapper only

cd /d "%~dp0"

:: Check Python is available
python --version >nul 2>&1
if errorlevel 1 (
    echo.
    echo  Python not found. Download from:
    echo  https://www.python.org/downloads/
    echo  Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

python installer.py %*
