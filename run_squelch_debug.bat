@echo off
title Squelch Debug
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py --debug %*
if errorlevel 1 pause
