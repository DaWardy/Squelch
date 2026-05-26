@echo off
title Squelch - Recreate Virtual Environment
cd /d "%~dp0"
echo.
echo  Squelch - Recreate Virtual Environment
echo  =======================================
echo  Rebuilds venv using the correct Python version
echo  so SoapySDR's .pyd files will load correctly.
echo.

:: Find conda/miniforge Python
set "CONDAPY="
for %%P in (
    "%USERPROFILE%\miniforge3\python.exe"
    "%USERPROFILE%\miniconda3\python.exe"
    "%USERPROFILE%\anaconda3\python.exe"
    "%USERPROFILE%\mambaforge\python.exe"
    "%LOCALAPPDATA%\miniforge3\python.exe"
    "%LOCALAPPDATA%\miniconda3\python.exe"
    "C:\miniforge3\python.exe"
    "C:\miniconda3\python.exe"
    "C:\Python313\python.exe"
    "C:\Python312\python.exe"
    "C:\Python311\python.exe"
    "C:\Python39\python.exe"
) do (
    if exist %%P (
        if not defined CONDAPY (
            set "CONDAPY=%%~P"
        )
    )
)

if not defined CONDAPY (
    echo  ERROR: No suitable Python found.
    echo  Install miniforge3 from:
    echo  github.com/conda-forge/miniforge/releases
    echo.
    pause & exit /b 1
)

echo  Found Python: %CONDAPY%
"%CONDAPY%" --version
echo.
echo  Current venv Python (for comparison):
if exist venv\Scripts\python.exe (
    venv\Scripts\python.exe --version
) else (
    echo  (no venv exists)
)
echo.
echo  This will DELETE the current venv and recreate it.
echo  Your settings in AppData\Roaming\Squelch are NOT affected.
echo.
set /p CONFIRM=Type YES to continue: 
if /i not "%CONFIRM%"=="YES" (
    echo  Cancelled.
    pause & exit /b 0
)

echo.
echo  Removing old venv...
if exist venv rmdir /s /q venv
echo  Done.

echo.
echo  Creating new venv...
"%CONDAPY%" -m venv venv
if %ERRORLEVEL% NEQ 0 (
    echo  ERROR: venv creation failed.
    pause & exit /b 1
)
echo  Venv created.

echo.
echo  Upgrading pip...
venv\Scripts\python.exe -m pip install --upgrade pip --quiet 2>nul

echo.
echo  Installing required packages...
venv\Scripts\pip install PyQt6 requests pyqtgraph numpy sounddevice sgp4 defusedxml --quiet
if %ERRORLEVEL% EQU 0 (
    echo  Packages installed.
) else (
    echo  WARNING: Some packages may have failed. Check internet connection.
)

echo.
echo  Fixing SoapySDR...
call fix_soapysdr.bat

echo.
echo  Venv rebuild complete.
echo  Run run_squelch.bat to launch Squelch.
echo.
pause
