@echo off
title Squelch — SDR Verification
cd /d "%~dp0"
color 0A

echo.
echo  Squelch SDR Verification
echo  ========================
echo.

if not exist venv\Scripts\python.exe (
    echo  ERROR: venv not found. Run installer.py first.
    echo.
    pause
    exit /b 1
)

venv\Scripts\python -c "
import sys, shutil
from pathlib import Path

print(f'  Python:     {sys.version.split()[0]}')
print(f'  Venv:       {sys.prefix}')
print()

# SoapySDR
try:
    import SoapySDR
    print(f'  SoapySDR:   {SoapySDR.getAPIVersion()}  OK')
    devs = SoapySDR.Device.enumerate()
    if devs:
        print(f'  Devices:    {len(devs)} found')
        for d in devs:
            label = d.get('label', d.get('driver','unknown'))
            print(f'    * {label}')
    else:
        print('  Devices:    None detected')
        print('              Check USB connection and drivers')
except ImportError:
    print('  SoapySDR:   NOT INSTALLED')
    print()
    # Search PothosSDR
    roots = [
        r'C:/Program Files/PothosSDR',
        r'C:/Program Files (x86)/PothosSDR',
        r'C:/PothosSDR',
    ]
    found = ''
    for base in roots:
        p = Path(base) / 'lib'
        if not p.exists(): continue
        for pydir in p.iterdir():
            if pydir.name.startswith('python3.'):
                sp = pydir / 'site-packages'
                soapy = sp / 'SoapySDR'
                pyd   = sp / '_SoapySDR.pyd'
                if soapy.exists() or pyd.exists():
                    found = str(sp)
                    pyver = pydir.name.replace('python','')
                    break
        if found: break
    if found:
        myver = f'{sys.version_info.major}.{sys.version_info.minor}'
        print(f'  PothosSDR found: {found}')
        if myver == pyver:
            print(f'  Python version matches ({myver}) -- run fix_soapysdr.bat')
        else:
            print(f'  VERSION MISMATCH: venv={myver}, PothosSDR={pyver}')
            print(f'  Fix: recreate venv with Python {pyver}')
            print(f'       python.org/downloads/release/python-{pyver}.x/')
    else:
        print('  PothosSDR not found. Install from:')
        print('  downloads.myriadrf.org/builds/PothosSDR/')
    print()
    print('  Or use RTL-TCP for RTL-SDR (no SoapySDR needed):')
    print('  github.com/airspy/airspyone_host/releases')

print()

# pyqtgraph
try:
    import pyqtgraph as pg
    print(f'  pyqtgraph:  {pg.__version__}  (waterfall OK)')
except ImportError:
    print('  pyqtgraph:  NOT INSTALLED')
    print('              Fix: install_package.bat pyqtgraph')

print()

# sounddevice
try:
    import sounddevice as sd
    inp = [d for d in sd.query_devices() if d['max_input_channels'] > 0]
    print(f'  sounddevice: OK  ({len(inp)} input devices)')
except ImportError:
    print('  sounddevice: NOT INSTALLED')
    print('               Fix: install_package.bat sounddevice')

print()

# sgp4
try:
    import sgp4
    print(f'  sgp4:       {sgp4.__version__}  (satellite tracking OK)')
except ImportError:
    print('  sgp4:       not installed  (no satellite tracking)')
    print('              Fix: install_package.bat sgp4')

print()
print('  Verification complete.')
"

echo.
echo  Press any key to close...
pause >nul
