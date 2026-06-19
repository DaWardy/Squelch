@echo off
title Squelch — Package Installer
cd /d "%~dp0"
color 0A

if "%1"=="" (
    echo.
    echo  Squelch Package Installer
    echo  =========================
    echo.
    echo  Usage:   install_package.bat ^<package^>
    echo  Example: install_package.bat soapysdr
    echo.
    echo  Common packages:
    echo    soapysdr      SDR waterfall ^(requires PothosSDR first^)
    echo    pyqtgraph     Spectrum/waterfall display
    echo    sounddevice   Audio input for rig audio mode
    echo    sgp4          Satellite tracking
    echo    pyyaml        GNU Radio .grc file import
    echo.
    echo  To install soapysdr for your RSP2Pro / RTL-SDR / USRP:
    echo    1. Install PothosSDR first ^(must match Python version^):
    echo       downloads.myriadrf.org/builds/PothosSDR/
    echo    2. Reboot
    echo    3. Run: install_package.bat soapysdr
    echo.
    echo  Note: Installs into Squelch^'s venv only.
    echo        NOT your system Python.
    echo.
    pause
    exit /b 0
)

if not exist ..\venv\Scripts\pip.exe (
    echo.
    echo  ERROR: Squelch venv not found.
    echo  Run installer.py first to set up the venv.
    echo.
    pause
    exit /b 1
)

echo.
echo  Installing: %*
echo  Into: %cd%\venv
echo.
echo  --------------------------------------------------------

..\venv\Scripts\pip install %* --no-warn-script-location
set RESULT=%ERRORLEVEL%

echo  --------------------------------------------------------
echo.

if %RESULT% EQU 0 (
    echo  SUCCESS: %1 installed.
    echo.
    echo  Restart Squelch to use the new package.
    echo  To verify: run verify_sdr.bat or python installer.py
) else (
    echo  FAILED: pip returned error %RESULT%
    echo.
    if /i "%1"=="soapysdr" (
        echo  SoapySDR is not on PyPI for Python 3.10+.
        echo  Use fix_soapysdr.bat to copy from PothosSDR instead.
        echo  Or run: fix_soapysdr.bat
    )
    echo.
    echo  Common fixes:
    echo    - Check internet connection
    echo    - For soapysdr: use fix_soapysdr.bat instead of pip
    echo    - Run as Administrator if permission denied
)

echo.
echo  Press any key to close...
pause >nul
exit /b %RESULT%
