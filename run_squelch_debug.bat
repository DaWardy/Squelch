@echo off
title Squelch — Debug Mode
cd /d "%~dp0"
venv\Scripts\python.exe main.py --debug %*
if errorlevel 1 (
    echo.
    echo Squelch exited with an error.
    echo Check %APPDATA%\Squelch\logs\squelch.log
    echo.
    pause
)
