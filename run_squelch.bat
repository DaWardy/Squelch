@echo off
cd /d "%~dp0"
title Squelch console  -  KEEP OPEN (closing this window stops Squelch)
call venv\Scripts\activate.bat
echo ============================================================
echo   Squelch is starting - this is its live console and logs.
echo.
echo   ** KEEP THIS WINDOW OPEN - closing it stops Squelch. **
echo   To quit, close the Squelch app window instead.
echo   Do NOT press Ctrl+C here - it force-kills the program.
echo ============================================================
echo.
python main.py %*
