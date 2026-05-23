# Squelch — fix_soapysdr.ps1
# Copies SoapySDR from PothosSDR into Squelch's venv.
# Run from the Squelch folder: .\fix_soapysdr.ps1

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

Write-Host ""
Write-Host "Squelch — SoapySDR Setup" -ForegroundColor Cyan
Write-Host "========================" -ForegroundColor Cyan
Write-Host ""

# ── 1. Find venv site-packages ────────────────────────────────────────────
$VenvPython = "venv\Scripts\python.exe"
if (-not (Test-Path $VenvPython)) {
    Write-Host "ERROR: venv not found. Run installer.py first." -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

$SitePkgs = & $VenvPython -c "import site; print(site.getsitepackages()[0])"
Write-Host "Venv site-packages: $SitePkgs"
Write-Host ""

# ── 2. Check if SoapySDR already works ───────────────────────────────────
Write-Host "Checking current SoapySDR status..."
$TestResult = & $VenvPython -c "import SoapySDR; print(SoapySDR.getAPIVersion())" 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "SoapySDR already working: $TestResult" -ForegroundColor Green
    $Devs = & $VenvPython -c "import SoapySDR; d=SoapySDR.Device.enumerate(); print(f'{len(d)} device(s): {[str(x.get(chr(108)+chr(97)+chr(98)+chr(101)+chr(108),x.get(chr(100)+chr(114)+chr(105)+chr(118)+chr(101)+chr(114),chr(63)))) for x in d]}')"
    Write-Host "Devices: $Devs" -ForegroundColor Green
    Write-Host ""
    Write-Host "Nothing to do. Restart Squelch to use SDR tab." -ForegroundColor Green
    Read-Host "Press Enter to exit"
    exit 0
}

Write-Host "SoapySDR not in venv. Searching PothosSDR..." -ForegroundColor Yellow
Write-Host ""

# ── 3. Find PothosSDR install ─────────────────────────────────────────────
$SearchRoots = @(
    "C:\Program Files\PothosSDR",
    "C:\Program Files (x86)\PothosSDR",
    "C:\PothosSDR",
    "$env:LOCALAPPDATA\PothosSDR",
    "$env:ProgramW6432\PothosSDR"
)

# Also check registry
try {
    $RegKey = Get-ItemProperty -Path "HKLM:\SOFTWARE\PothosSDR" -ErrorAction SilentlyContinue
    if ($RegKey -and $RegKey.InstallDir) {
        $SearchRoots = @($RegKey.InstallDir) + $SearchRoots
    }
} catch {}

$FoundSoapy = $null

foreach ($Root in $SearchRoots) {
    if (-not (Test-Path $Root)) { continue }
    Write-Host "Searching: $Root"
    
    # Look for SoapySDR folder with __init__.py
    $Hits = Get-ChildItem $Root -Recurse -Directory -Filter "SoapySDR" -ErrorAction SilentlyContinue |
        Where-Object { Test-Path (Join-Path $_.FullName "__init__.py") }
    
    if ($Hits) {
        $FoundSoapy = $Hits[0].FullName
        Write-Host "  Found: $FoundSoapy" -ForegroundColor Green
        break
    }
    
    # Also look for SoapySDR.pyd directly
    $Pyds = Get-ChildItem $Root -Recurse -Filter "SoapySDR*.pyd" -ErrorAction SilentlyContinue
    if ($Pyds) {
        Write-Host "  Found .pyd: $($Pyds[0].FullName)" -ForegroundColor Yellow
        Write-Host "  (PothosSDR found but no Python wrapper — try reinstalling PothosSDR)" -ForegroundColor Yellow
    }
}

Write-Host ""

if (-not $FoundSoapy) {
    Write-Host "SoapySDR not found in PothosSDR." -ForegroundColor Red
    Write-Host ""
    Write-Host "Make sure PothosSDR is installed:" -ForegroundColor Yellow
    Write-Host "  https://downloads.myriadrf.org/builds/PothosSDR/"
    Write-Host ""
    Write-Host "SDRplay RSP users: install SDRplay API FIRST:" -ForegroundColor Yellow
    Write-Host "  https://www.sdrplay.com/softwarehome/"
    Write-Host "  Then reinstall PothosSDR"
    Write-Host ""
    Read-Host "Press Enter to exit"
    exit 1
}

# ── 4. Copy into venv ─────────────────────────────────────────────────────
$Dst = Join-Path $SitePkgs "SoapySDR"

Write-Host "Copying SoapySDR into Squelch venv..."
Write-Host "  From: $FoundSoapy"
Write-Host "  To:   $Dst"
Write-Host ""

try {
    if (Test-Path $Dst) {
        Remove-Item $Dst -Recurse -Force
    }
    Copy-Item $FoundSoapy $Dst -Recurse -Force
    Write-Host "Copy complete." -ForegroundColor Green
} catch {
    Write-Host "ERROR: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Try running this script as Administrator." -ForegroundColor Yellow
    Read-Host "Press Enter to exit"
    exit 1
}

# ── 5. Also copy SoapySDR DLLs if needed ─────────────────────────────────
# The Python package needs the SoapySDR .dll files in PATH or same directory
$PothosRoot = Split-Path -Parent (Split-Path -Parent $FoundSoapy)
$DllSrc = Get-ChildItem $PothosRoot -Filter "SoapySDR.dll" -Recurse -ErrorAction SilentlyContinue
if ($DllSrc) {
    Write-Host ""
    Write-Host "SoapySDR.dll found at: $($DllSrc[0].DirectoryName)"
    Write-Host "PothosSDR bin directory should already be in PATH."
}

# ── 6. Verify ─────────────────────────────────────────────────────────────
Write-Host ""
Write-Host "Verifying installation..."
$VerifyResult = & $VenvPython -c "import SoapySDR; print(f'SoapySDR {SoapySDR.getAPIVersion()} — OK')" 2>&1

if ($LASTEXITCODE -eq 0) {
    Write-Host $VerifyResult -ForegroundColor Green
    Write-Host ""
    
    # List devices
    $DevsResult = & $VenvPython -c "
import SoapySDR
devs = SoapySDR.Device.enumerate()
if devs:
    print(f'{len(devs)} SDR device(s) found:')
    for d in devs:
        print(f'  * {d.get(chr(108)+chr(97)+chr(98)+chr(101)+chr(108), d.get(chr(100)+chr(114)+chr(105)+chr(118)+chr(101)+chr(114),chr(63)))}')
else:
    print('No devices detected. Check USB connection.')
" 2>&1
    Write-Host $DevsResult -ForegroundColor Cyan
    
    Write-Host ""
    Write-Host "SUCCESS. Restart Squelch — SDR tab should now work." -ForegroundColor Green
} else {
    Write-Host "Import still failing: $VerifyResult" -ForegroundColor Red
    Write-Host ""
    Write-Host "The SoapySDR.dll may not be in PATH." -ForegroundColor Yellow
    Write-Host "Try adding PothosSDR\bin to your system PATH:" -ForegroundColor Yellow
    Write-Host "  System Properties -> Environment Variables -> Path"
    Write-Host "  Add: C:\Program Files\PothosSDR\bin"
    Write-Host ""
    Write-Host "Then restart PowerShell and run this script again."
}

Write-Host ""
Read-Host "Press Enter to exit"
