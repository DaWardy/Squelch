@echo off
title Squelch - SoapySDR Fix
cd /d "%~dp0"
echo.
echo  Squelch SoapySDR Fix
echo  ====================
echo.

if not exist venv\Scripts\python.exe (
    echo  ERROR: venv not found. Run run_installer.bat first.
    echo.
    pause & exit /b 1
)

:: Get site-packages using sysconfig
for /f "delims=" %%S in ('venv\Scripts\python.exe -c "import sysconfig; print(sysconfig.get_path(chr(112)+chr(117)+chr(114)+chr(101)+chr(108)+chr(105)+chr(98)))"') do set "SITE=%%S"

:: Fallback
if not defined SITE set "SITE=%~dp0venv\Lib\site-packages"
if not exist "%SITE%" set "SITE=%~dp0venv\Lib\site-packages"

echo  Venv Python:
venv\Scripts\python.exe --version
echo  Site-packages: %SITE%
echo.

if not exist "%SITE%" (
    echo  ERROR: site-packages not found at: %SITE%
    echo  Run recreate_venv.bat to rebuild the venv.
    pause & exit /b 1
)

:: Test if already working
venv\Scripts\python.exe -c "import SoapySDR; print(SoapySDR.getAPIVersion())" 2>nul
if %ERRORLEVEL% EQU 0 (
    echo  SoapySDR already working.
    venv\Scripts\python.exe -c "import SoapySDR; d=SoapySDR.Device.enumerate(); print(str(len(d))+' device(s) found')"
    echo.
    pause & exit /b 0
)

echo  Searching for SoapySDR...
echo.

set "SOAPYFOUND="
for %%D in (
    "%USERPROFILE%\miniforge3\Lib\site-packages"
    "%USERPROFILE%\miniconda3\Lib\site-packages"
    "%USERPROFILE%\anaconda3\Lib\site-packages"
    "%USERPROFILE%\mambaforge\Lib\site-packages"
    "%LOCALAPPDATA%\miniforge3\Lib\site-packages"
    "%LOCALAPPDATA%\miniconda3\Lib\site-packages"
    "C:\miniforge3\Lib\site-packages"
    "C:\miniconda3\Lib\site-packages"
    "C:\Program Files\PothosSDR\lib\python3.9\site-packages"
) do (
    if exist "%%~D\SoapySDR.py" (
        if not defined SOAPYFOUND set "SOAPYFOUND=%%~D"
    )
)

if not defined SOAPYFOUND (
    echo  SoapySDR not found in conda or PothosSDR.
    echo  Install: conda install -c conda-forge soapysdr
    echo  Then run this script again.
    pause & exit /b 1
)

echo  Found: %SOAPYFOUND%

:: Version check
for /f "delims=" %%V in ('venv\Scripts\python.exe -c "import sys; print(str(sys.version_info.major)+str(sys.version_info.minor))"') do set "VENVVER=%%V"
echo  Venv Python version tag: cp%VENVVER%

:: Check .pyd file version
set "PYDVER="
for %%F in ("%SOAPYFOUND%\_SoapySDR.cp*-win_amd64.pyd") do (
    set "PYDNAME=%%~nF"
)
echo  SoapySDR .pyd: %PYDNAME%.pyd

echo.
echo  Copying to %SITE%
echo.

:: Copy SoapySDR.py (note: do NOT use -> in echo or it becomes a redirect!)
if exist "%SOAPYFOUND%\SoapySDR.py" (
    copy /y "%SOAPYFOUND%\SoapySDR.py" "%SITE%\SoapySDR.py" >nul
    if %ERRORLEVEL% EQU 0 (
        echo  OK: SoapySDR.py copied
    ) else (
        echo  FAIL: could not copy SoapySDR.py
    )
)

:: Copy SoapySDR folder if present
if exist "%SOAPYFOUND%\SoapySDR\" (
    if exist "%SITE%\SoapySDR\" rmdir /s /q "%SITE%\SoapySDR"
    xcopy /e /i /q "%SOAPYFOUND%\SoapySDR" "%SITE%\SoapySDR" >nul
    echo  OK: SoapySDR folder copied
)

:: Copy _SoapySDR.pyd files (core)
for %%F in ("%SOAPYFOUND%\_SoapySDR*.pyd") do (
    copy /y "%%F" "%SITE%\%%~nxF" >nul
    if %ERRORLEVEL% EQU 0 (
        echo  OK: %%~nxF
    ) else (
        echo  FAIL: %%~nxF
    )
)

:: Copy device plugins (RTL-SDR, HackRF, RSP, USRP, Airspy, LimeSDR)
echo.
echo  Copying device plugins...
set PLUGINS_FOUND=0
for %%F in (
    "%SOAPYFOUND%\SoapyRTLSDR*.pyd"
    "%SOAPYFOUND%\SoapyHackRF*.pyd"
    "%SOAPYFOUND%\SoapySDRPlay3*.pyd"
    "%SOAPYFOUND%\SoapySDRPlay*.pyd"
    "%SOAPYFOUND%\SoapyUHD*.pyd"
    "%SOAPYFOUND%\SoapyAirspy*.pyd"
    "%SOAPYFOUND%\SoapyLMS7*.pyd"
    "%SOAPYFOUND%\SoapyBladeRF*.pyd"
    "%SOAPYFOUND%\SoapyPluto*.pyd"
) do (
    if exist "%%F" (
        copy /y "%%F" "%SITE%\%%~nxF" >nul
        if %ERRORLEVEL% EQU 0 (
            echo  OK plugin: %%~nxF
            set PLUGINS_FOUND=1
        )
    )
)
if "%PLUGINS_FOUND%"=="0" (
    echo  No device plugins found in conda.
    echo  Install with:
    echo    conda install -c conda-forge soapyrtlsdr soapyhackrf soapysdrplay3 soapyuhd soapyairspy
    echo  Then run this script again.
)

echo.
echo  Verifying...
venv\Scripts\python.exe -c "import SoapySDR; print('  SoapySDR '+SoapySDR.getAPIVersion()+' working'); d=SoapySDR.Device.enumerate(); print('  Devices: '+str(len(d))+(str([str(x.get('label',x.get('driver','?'))) for x in d]) if d else ' -- none detected (check USB connection)'))"
if %ERRORLEVEL% EQU 0 (
    echo.
    echo  SUCCESS. Restart Squelch.
    echo.
    echo  If you see 0 devices, check:
    echo    RSP2Pro:  conda install -c conda-forge soapysdrplay3
    echo    RTL-SDR:  conda install -c conda-forge soapyrtlsdr
    echo    USRP:     conda install -c conda-forge soapyuhd
    echo    HackRF:   conda install -c conda-forge soapyhackrf
    echo  Then run this script again.
) else (
    echo.
    echo  FAILED. Check that Python versions match:
    venv\Scripts\python.exe --version
    echo  .pyd built for: %PYDNAME%
    echo.
    echo  If versions differ: run recreate_venv.bat
)
echo.
echo  Press any key to close...
pause >nul
