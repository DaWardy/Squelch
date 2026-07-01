@echo off
cd /d "%~dp0"
title Squelch - application console (keep open; closing it stops Squelch)
call venv\Scripts\activate.bat
echo ============================================================
echo   Squelch is starting.
echo   This window is Squelch's console - it shows live activity
echo   and logs while the program runs.
echo   Keep it open; closing this window stops Squelch.
echo ============================================================
echo.
rem  Use console python (not pythonw) so log output is visible here.
python main.py %*
