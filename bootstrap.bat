@echo off
setlocal EnableDelayedExpansion
title Squelch Bootstrap
color 0A

echo.
echo  =====================================================
echo   Squelch -- Amateur Radio Operations Platform
echo   Bootstrap and Dependency Installer
echo   github.com/dawardy/squelch
echo  =====================================================
echo.
echo  This script will:
echo    1. Verify Python version
echo    2. Create a virtual environment
echo    3. Install Python packages
echo    4. Check for required external tools
echo    5. Generate config.json from template
echo    6. Create launch shortcuts
echo.
echo  External tools ^(Hamlib, WSJT-X, VARA etc.^) must be
echo  installed manually. This script will tell you exactly
echo  what is missing and where to get it.
echo.
pause

set ERRORS=0
set WARNINGS=0

:: ── Step 1: Python ───────────────────────────────────────────────────────
echo.
echo [1/6] Checking Python...
echo  -------------------------------------------------------

python --version >nul 2>&1
if errorlevel 1 (
    echo  [FAIL] Python not found in PATH.
    echo.
    echo  Download Python 3.11+ from:
    echo    https://www.python.org/downloads/
    echo.
    echo  IMPORTANT: Check "Add Python to PATH" during install.
    echo.
    pause
    exit /b 1
)

for /f "tokens=2 delims= " %%v in ('python --version 2^>^&1') do set PYVER=%%v
echo  [OK]   Python %PYVER% found.

for /f "tokens=1,2 delims=." %%a in ("%PYVER%") do (
    set PYMAJ=%%a
    set PYMIN=%%b
)

if %PYMAJ% LSS 3 (
    echo  [FAIL] Python 3.11+ required.
    pause & exit /b 1
)
if %PYMAJ% EQU 3 (
    if %PYMIN% LSS 11 (
        echo  [WARN] Python %PYVER% - 3.11+ recommended.
        set /A WARNINGS+=1
    ) else (
        echo  [OK]   Python version supported.
    )
)

:: ── Step 2: Virtual environment ──────────────────────────────────────────
echo.
echo [2/6] Setting up virtual environment...
echo  -------------------------------------------------------

if not exist venv (
    echo  Creating virtual environment...
    python -m venv venv
    if errorlevel 1 (
        echo  [FAIL] Could not create virtual environment.
        set /A ERRORS+=1
        goto STEP3
    )
    echo  [OK]   Virtual environment created.
) else (
    echo  [OK]   Virtual environment already exists.
)

call venv\Scripts\activate.bat 2>nul

:STEP3
:: ── Step 3: Python packages ───────────────────────────────────────────────
echo.
echo [3/6] Installing Python packages...
echo  -------------------------------------------------------
echo  This may take a few minutes on first run.
echo.

python -m pip install --upgrade pip --quiet --no-cache-dir 2>nul

pip install -r requirements.txt --no-cache-dir --quiet 2>nul
if errorlevel 1 (
    echo  [WARN] Some packages may have failed.
    echo         Run: python install_check.py --fix
    set /A WARNINGS+=1
) else (
    echo  [OK]   Python packages installed.
)

python -c "import PyQt6; print('  [OK]   PyQt6 OK')" 2>nul
if errorlevel 1 echo  [WARN] PyQt6 check inconclusive - run install_check.py

python -c "import numpy; print('  [OK]   numpy OK')" 2>nul
if errorlevel 1 (
    echo  [WARN] numpy not detected.
    set /A WARNINGS+=1
)

python -c "import pyqtgraph; print('  [OK]   pyqtgraph OK')" 2>nul
if errorlevel 1 (
    echo  [WARN] pyqtgraph missing - run: pip install pyqtgraph --no-cache-dir
    set /A WARNINGS+=1
)

python -c "import sounddevice; print('  [OK]   sounddevice OK')" 2>nul
if errorlevel 1 (
    echo  [WARN] sounddevice not detected.
    set /A WARNINGS+=1
)

:: ── Step 4: External tools ────────────────────────────────────────────────
echo.
echo [4/6] Checking external tools...
echo  -------------------------------------------------------
echo  Warnings here do not prevent Squelch from launching.
echo  Affected tabs are grayed out until tools are installed.
echo.

:: Hamlib
where rigctld >nul 2>&1
if errorlevel 1 (
    if exist "C:\hamlib\bin\rigctld.exe" (
        echo  [WARN] Hamlib found at C:\hamlib\bin but NOT in PATH.
        echo         Add C:\hamlib\bin to system PATH then REBOOT.
    ) else (
        echo  [WARN] Hamlib not found.
        echo         Download: https://github.com/Hamlib/Hamlib/releases
        echo         Extract to C:\hamlib, add C:\hamlib\bin to PATH, REBOOT.
    )
    set /A WARNINGS+=1
) else (
    rigctld --version > "%TEMP%\hl_ver.txt" 2>&1
    set /p HL_VER=<"%TEMP%\hl_ver.txt"
    echo  [OK]   !HL_VER!
    del "%TEMP%\hl_ver.txt" >nul 2>&1
)

:: VB-Cable -- write check to temp file to avoid batch quoting issues
echo import sounddevice as sd > "%TEMP%\apex_vbcheck.py"
echo devs = [d['name'] for d in sd.query_devices()] >> "%TEMP%\apex_vbcheck.py"
echo vb = [d for d in devs if 'CABLE' in d.upper() or 'VB-AUDIO' in d.upper()] >> "%TEMP%\apex_vbcheck.py"
echo if vb: >> "%TEMP%\apex_vbcheck.py"
echo     print('  [OK]   VB-Cable:', vb[0]) >> "%TEMP%\apex_vbcheck.py"
echo else: >> "%TEMP%\apex_vbcheck.py"
echo     print('  [WARN] VB-Cable not detected.') >> "%TEMP%\apex_vbcheck.py"
echo     print('         Download: https://vb-audio.com/Cable/') >> "%TEMP%\apex_vbcheck.py"
echo     print('         Install as Administrator and reboot.') >> "%TEMP%\apex_vbcheck.py"
python "%TEMP%\apex_vbcheck.py" 2>nul
del "%TEMP%\apex_vbcheck.py" >nul 2>&1

:: SoapySDR -- write check to temp file
echo try: > "%TEMP%\apex_soapycheck.py"
echo     import SoapySDR >> "%TEMP%\apex_soapycheck.py"
echo     print('  [OK]   SoapySDR', SoapySDR.getAPIVersion()) >> "%TEMP%\apex_soapycheck.py"
echo except ImportError: >> "%TEMP%\apex_soapycheck.py"
echo     print('  [WARN] SoapySDR not installed - SDR Waterfall unavaiguestle.') >> "%TEMP%\apex_soapycheck.py"
echo     print('         See README.md for SDR driver installation.') >> "%TEMP%\apex_soapycheck.py"
python "%TEMP%\apex_soapycheck.py" 2>nul
del "%TEMP%\apex_soapycheck.py" >nul 2>&1

:: Serial ports -- write check to temp file
echo import serial.tools.list_ports > "%TEMP%\apex_serialcheck.py"
echo ports = list(serial.tools.list_ports.comports()) >> "%TEMP%\apex_serialcheck.py"
echo ic = [p for p in ports if any(x in (p.description or '').upper() for x in ['CP210','CI-V','IC-7100','UART','USB SERIAL'])] >> "%TEMP%\apex_serialcheck.py"
echo if ic: >> "%TEMP%\apex_serialcheck.py"
echo     print('  [OK]   Likely rig port:', ic[0].device, '--', ic[0].description) >> "%TEMP%\apex_serialcheck.py"
echo elif ports: >> "%TEMP%\apex_serialcheck.py"
echo     print('  [INFO] Serial ports found, no rig auto-detected.') >> "%TEMP%\apex_serialcheck.py"
echo     print('         Connect rig or select port manually in app.') >> "%TEMP%\apex_serialcheck.py"
echo else: >> "%TEMP%\apex_serialcheck.py"
echo     print('  [INFO] No serial ports - rig not connected (OK).') >> "%TEMP%\apex_serialcheck.py"
python "%TEMP%\apex_serialcheck.py" 2>nul
del "%TEMP%\apex_serialcheck.py" >nul 2>&1

:: WSJT-X
set WSJTX_FOUND=0
if exist "%PROGRAMFILES%\WSJT-X\bin\wsjtx.exe" set WSJTX_FOUND=1
if exist "%PROGRAMFILES(X86)%\WSJT-X\bin\wsjtx.exe" set WSJTX_FOUND=1
if "%WSJTX_FOUND%"=="1" (
    echo  [OK]   WSJT-X found.
) else (
    echo  [WARN] WSJT-X not found - FT8/FT4/WSPR unavaiguestle.
    echo         Download: https://wsjt.sourceforge.io/wsjtx.html
    set /A WARNINGS+=1
)

:: VARA HF
set VARA_FOUND=0
if exist "C:\VARA HF\VARAHF.exe" set VARA_FOUND=1
if exist "C:\VARA\VARAHF.exe" set VARA_FOUND=1
if "%VARA_FOUND%"=="1" (
    echo  [OK]   VARA HF found.
) else (
    echo  [WARN] VARA HF not found - Winlink HF unavaiguestle.
    echo         Download: https://rosmodem.wordpress.com/
    set /A WARNINGS+=1
)

:: ── Step 5: Config ────────────────────────────────────────────────────────
echo.
echo [5/6] Setting up configuration...
echo  -------------------------------------------------------

if not exist config.json (
    if exist config.example.json (
        copy config.example.json config.json >nul
        echo  [OK]   config.json created from template.
        echo         Launch Squelch to enter callsign and grid square.
    ) else (
        echo  [WARN] config.example.json not found.
        set /A WARNINGS+=1
    )
) else (
    echo  [OK]   config.json already exists.
)

:: ── Step 6: Launch scripts ────────────────────────────────────────────────
echo.
echo [6/6] Creating launch scripts...
echo  -------------------------------------------------------

(
echo @echo off
echo cd /d "%%~dp0"
echo call venv\Scripts\activate.bat
echo python main.py %%*
echo if errorlevel 1 pause
) > run_apex.bat
echo  [OK]   run_apex.bat created.

(
echo @echo off
echo title Squelch -- Guest Mode
echo cd /d "%%~dp0"
echo call venv\Scripts\activate.bat
echo python main.py --guest-mode %%*
echo if errorlevel 1 pause
) > run_apex_guest.bat
echo  [OK]   run_apex_guest.bat created.

:: ── Summary ───────────────────────────────────────────────────────────────
echo.
echo  =====================================================
if %ERRORS% GTR 0 (
    echo   COMPLETED WITH %ERRORS% ERROR^(S^) AND %WARNINGS% WARNING^(S^).
    echo   Fix errors above before launching Squelch.
) else if %WARNINGS% GTR 0 (
    echo   COMPLETED WITH %WARNINGS% WARNING^(S^).
    echo   Squelch will launch. Missing tools gray out their tabs.
    echo.
    echo   NOTE: If Hamlib was just installed, REBOOT first.
) else (
    echo   ALL CHECKS PASSED. Squelch is ready.
)
echo.
echo   To launch:        double-click run_apex.bat
echo   To verify:        python install_check.py
echo   Documentation:    README.md
echo  =====================================================
echo.

if %ERRORS% EQU 0 (
    set /p LAUNCH="Launch Squelch now? [Y/N]: "
    if /i "!LAUNCH!"=="Y" (
        call venv\Scripts\activate.bat
        python main.py
    )
)

endlocal
pause
