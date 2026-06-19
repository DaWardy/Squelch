@echo off
title Squelch Installer
cd /d "%~dp0"

echo.
echo  Squelch Installer
echo  =================
echo.

:: Try to find the right Python - prefer venv, then miniforge, then PATH
set PYEXE=

if exist ..\venv\Scripts\python.exe (
    set PYEXE=..\venv\Scripts\python.exe
    echo  Using: venv Python
    goto :run
)

:: Check common miniforge/conda locations
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
        set PYEXE=%%P
        echo  Using: %%P
        goto :run
    )
)

:: Last resort: system python
python --version >nul 2>&1
if %ERRORLEVEL% EQU 0 (
    set PYEXE=python
    echo  Using: system python
    goto :run
)

echo  ERROR: Python not found.
echo  Install Python 3.9+ from python.org or miniforge from:
echo  github.com/conda-forge/miniforge/releases
echo.
pause
exit /b 1

:run
echo.
%PYEXE% installer.py %*
echo.
echo  Press any key to close...
pause >nul
