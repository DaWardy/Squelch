@echo off
title Squelch — Guest Operator
cd /d "%~dp0"
call venv\Scripts\activate.bat
pythonw main.py --guest-op %*
