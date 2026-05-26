@echo off
:: Squelch Bootstrap — redirects to install.bat
:: (kept for backwards compatibility — use install.bat going forward)
cd /d "%~dp0"
echo Redirecting to install.bat ...
call install.bat
