@echo off
:: Squelch launcher — starts the app from the virtual environment
setlocal
cd /d "%~dp0"

if not exist "venv\Scripts\python.exe" (
    echo.
    echo ERROR: Virtual environment not found.
    echo Run install.bat first to set up Squelch.
    echo.
    pause
    exit /b 1
)

"venv\Scripts\python.exe" main.py
if errorlevel 1 (
    echo.
    echo Squelch exited with an error. Press a key to close.
    pause >nul
)
