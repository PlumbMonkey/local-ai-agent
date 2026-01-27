; Gene Desktop Application - Inno Setup Script
; Creates a Windows installer with desktop shortcut

#define MyAppName "Gene"
#define MyAppVersion "1.0.0"
#define MyAppPublisher "Your Company Name"
#define MyAppURL "https://github.com/yourusername/gene"
#define MyAppExeName "Gene.exe"
#define MyAppDescription "Generative Engine for Natural Engagement"

[Setup]
; Application info
AppId={{A8B9C0D1-E2F3-4567-8901-ABCDEF012345}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppVerName={#MyAppName} {#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}

; Installation directories
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes

; Output settings
OutputDir=..\dist\installer
OutputBaseFilename=Gene_Setup_{#MyAppVersion}
SetupIconFile=gene.ico
UninstallDisplayIcon={app}\Gene.exe

; Compression
Compression=lzma2/ultra64
SolidCompression=yes
LZMANumBlockThreads=4

; Privileges
PrivilegesRequired=lowest
PrivilegesRequiredOverridesAllowed=dialog

; Visual
WizardStyle=modern
; WizardImageFile=wizard_large.bmp
; WizardSmallImageFile=wizard_small.bmp

; License (optional - create a LICENSE.txt)
; LicenseFile=..\LICENSE

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce
Name: "quicklaunchicon"; Description: "{cm:CreateQuickLaunchIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: unchecked; OnlyBelowVersion: 6.1; Check: not IsAdminInstallMode

[Files]
; Main application files
Source: "..\dist\Gene\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

; Create empty directories for user data
Source: "..\installer\placeholder.txt"; DestDir: "{app}\chat_history"; Flags: ignoreversion
Source: "..\installer\placeholder.txt"; DestDir: "{app}\business_data"; Flags: ignoreversion

[Dirs]
; Ensure data directories exist with user write permissions
Name: "{app}\chat_history"; Permissions: users-modify
Name: "{app}\business_data"; Permissions: users-modify

[Icons]
; Start Menu
Name: "{autoprograms}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Comment: "{#MyAppDescription}"

; Desktop shortcut (if selected)
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon; Comment: "{#MyAppDescription}"

; Quick Launch (legacy)
Name: "{userappdata}\Microsoft\Internet Explorer\Quick Launch\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; Tasks: quicklaunchicon

[Run]
; Option to launch after install
Filename: "{app}\{#MyAppExeName}"; Description: "{cm:LaunchProgram,{#StringChange(MyAppName, '&', '&&')}}"; Flags: nowait postinstall skipifsilent

[UninstallDelete]
; Clean up user data on uninstall (optional - commented out to preserve data)
; Type: filesandordirs; Name: "{app}\chat_history"
; Type: filesandordirs; Name: "{app}\business_data"

[Code]
// Check if Ollama is installed
function IsOllamaInstalled(): Boolean;
begin
  Result := FileExists(ExpandConstant('{localappdata}\Programs\Ollama\ollama.exe')) or 
            FileExists('C:\Program Files\Ollama\ollama.exe');
end;

// Show warning if Ollama not found
procedure CurPageChanged(CurPageID: Integer);
begin
  if CurPageID = wpReady then
  begin
    if not IsOllamaInstalled() then
    begin
      MsgBox('Note: Gene requires Ollama to be installed for AI functionality.' + #13#10 + #13#10 +
             'Please install Ollama from: https://ollama.ai' + #13#10 + #13#10 +
             'After installing Ollama, run: ollama pull qwen2.5-coder:7b', 
             mbInformation, MB_OK);
    end;
  end;
end;

// Initialize setup
function InitializeSetup(): Boolean;
begin
  Result := True;
end;
