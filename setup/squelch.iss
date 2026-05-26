; Squelch — Amateur Radio Operations Platform
; Copyright (C) 2026  github.com/dawardy/squelch
; Licensed under GNU GPL v3
;
; Inno Setup 6.x installer script.
; Download Inno Setup: jrsoftware.org/isinfo.php
;
; To build:
;   1. Install Inno Setup 6.x
;   2. Open this file in Inno Setup Compiler
;   3. Build → Compile  (or press F9)
;   Output: Output\Squelch_Setup_v0.10.0.exe
;
; Or from command line:
;   "C:\Program Files (x86)\Inno Setup 6\ISCC.exe" squelch.iss

#define MyAppName      "Squelch"
#define MyAppVersion   "0.10.0-alpha"
#define MyAppPublisher "Squelch Project"
#define MyAppURL       "https://github.com/dawardy/squelch"
#define MyAppExe       "run_squelch.bat"
#define MyOutputBase   "Squelch_Setup_v0.10.0"
#define MyBuildDir     ".."

[Setup]
AppId={{B4A72F3E-8D5C-4E2A-9F1B-6C3D8E4F5A7B}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}/issues
AppUpdatesURL={#MyAppURL}/releases
DefaultDirName={autopf}\Squelch
DefaultGroupName=Squelch
AllowNoIcons=yes
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog
OutputDir={#MyBuildDir}\setup\Output
OutputBaseFilename={#MyOutputBase}
SetupIconFile={#MyBuildDir}\assets\squelch.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
WizardResizable=yes
LicenseFile={#MyBuildDir}\LICENSE
MinVersion=10.10.0
ArchitecturesInstallIn64BitMode=x64compatible

; Windows SmartScreen workaround note:
; Sign with SignPath Foundation (free for open source) to avoid
; "Windows protected your PC" dialog.
; See: signpath.io/product/foundation

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon";    Description: "{cm:CreateDesktopIcon}";    GroupDescription: "{cm:AdditionalIcons}"
Name: "startmenuicon";  Description: "Create Start Menu shortcut"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checked
Name: "autostart";      Description: "Launch Squelch on Windows startup"; GroupDescription: "Startup"; Flags: unchecked

[Files]
; Main application files (exclude build artifacts)
Source: "{#MyBuildDir}\*.py";                   DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyBuildDir}\*.bat";                   DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyBuildDir}\*.txt";                   DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyBuildDir}\*.md";                    DestDir: "{app}"; Flags: ignoreversion
Source: "{#MyBuildDir}\*.json";                  DestDir: "{app}"; Flags: ignoreversion recursesubdirs

; Python packages directory
Source: "{#MyBuildDir}\core\*";                  DestDir: "{app}\core";      Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\ui\*";                    DestDir: "{app}\ui";        Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\network\*";               DestDir: "{app}\network";   Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\modes\*";                 DestDir: "{app}\modes";     Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\digital\*";               DestDir: "{app}\digital";   Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\sdr\*";                   DestDir: "{app}\sdr";       Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\aprs\*";                  DestDir: "{app}\aprs";      Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\winlink\*";               DestDir: "{app}\winlink";   Flags: ignoreversion recursesubdirs
Source: "{#MyBuildDir}\plugins\*";               DestDir: "{app}\plugins";   Flags: ignoreversion recursesubdirs

; Assets
Source: "{#MyBuildDir}\assets\*";               DestDir: "{app}\assets";    Flags: ignoreversion recursesubdirs skipifsourcedoesntexist

[Icons]
; Start menu
Name: "{group}\{#MyAppName}";                    Filename: "{app}\{#MyAppExe}";  IconFilename: "{app}\assets\squelch.ico"; Comment: "Amateur Radio Operations Platform"
Name: "{group}\{#MyAppName} (Debug)";            Filename: "{app}\run_squelch_debug.bat"; Comment: "Launch with debug logging"
Name: "{group}\Installer & Dependency Check";    Filename: "{app}\installer.py"; Parameters: "--check"
Name: "{group}\{cm:UninstallProgram,{#MyAppName}}"; Filename: "{uninstallexe}"

; Desktop
Name: "{autodesktop}\{#MyAppName}";              Filename: "{app}\{#MyAppExe}"; IconFilename: "{app}\assets\squelch.ico"; Tasks: desktopicon

; Startup (optional)
Name: "{autostartup}\{#MyAppName}";              Filename: "{app}\{#MyAppExe}"; Tasks: autostart

[Run]
; Run installer after setup
Filename: "{app}\installer.py"; Parameters: "--no-cache-install"; Description: "Install Python dependencies"; Flags: postinstall shellexec nowait

; Launch after install
Filename: "{app}\{#MyAppExe}"; Description: "{cm:LaunchProgram,{#MyAppName}}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
; Remove venv and cached packages on uninstall
Type: filesandordirs; Name: "{app}\venv"
Type: filesandordirs; Name: "{app}\offline_packages"
Type: filesandordirs; Name: "{app}\__pycache__"

[Registry]
; File association for .adif files
Root: HKCU; Subkey: "Software\Classes\.adif"; ValueType: string; ValueData: "Squelch.ADIFFile"; Flags: uninsdeletevalue
Root: HKCU; Subkey: "Software\Classes\Squelch.ADIFFile"; ValueType: string; ValueData: "ADIF Log File"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Classes\Squelch.ADIFFile\DefaultIcon"; ValueType: string; ValueData: "{app}\assets\squelch.ico"
Root: HKCU; Subkey: "Software\Classes\Squelch.ADIFFile\shell\open\command"; ValueType: string; ValueData: """{app}\{#MyAppExe}"" ""%1"""

; Register in Add/Remove Programs
Root: HKCU; Subkey: "Software\Squelch"; ValueType: string; ValueName: "InstallPath"; ValueData: "{app}"; Flags: uninsdeletekey
Root: HKCU; Subkey: "Software\Squelch"; ValueType: string; ValueName: "Version"; ValueData: "{#MyAppVersion}"

[Code]
// Check Python is installed before setup
function InitializeSetup(): Boolean;
var
  PythonPath: String;
  ResultCode: Integer;
begin
  Result := True;
  
  // Try to find Python
  if not RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.12\InstallPath', '', PythonPath) then
    if not RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.11\InstallPath', '', PythonPath) then
      if not RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.13\InstallPath', '', PythonPath) then
        if not RegQueryStringValue(HKLM, 'SOFTWARE\Python\PythonCore\3.14\InstallPath', '', PythonPath) then
        begin
          if MsgBox(
            'Python 3.11 or newer was not found on this system.' + #13#10 +
            #13#10 +
            'Squelch requires Python 3.11+ to run.' + #13#10 +
            'Download from: python.org/downloads' + #13#10 +
            #13#10 +
            'Note: Python 3.12 is recommended for full feature support.' + #13#10 +
            'Python 3.14 works but lacks PyQtWebEngine (map tab).' + #13#10 +
            #13#10 +
            'Continue installation anyway?',
            mbConfirmation, MB_YESNO) = IDNO then
            Result := False;
        end;
end;

// Show helpful message after install
procedure CurStepChanged(CurStep: TSetupStep);
begin
  if CurStep = ssDone then
  begin
    MsgBox(
      'Squelch installed successfully!' + #13#10 +
      #13#10 +
      'First launch may take 30-60 seconds while' + #13#10 +
      'Python packages finish installing.' + #13#10 +
      #13#10 +
      'Your settings are saved in:' + #13#10 +
      ExpandConstant('{userappdata}') + '\Squelch\' + #13#10 +
      #13#10 +
      'For help: open Squelch → Help tab (F1)',
      mbInformation, MB_OK);
  end;
end;
