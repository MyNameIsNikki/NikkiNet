; NikkiNet - Inno Setup 6 installer script
; Build: ISCC.exe /DAppVer=1.1.0 nikkinet.iss
; (installer/build_dist.ps1 -Compile does this automatically)

#ifndef AppVer
  #define AppVer "1.1.0"
#endif

#define AppName "NikkiNet"
#define AppExe "start.bat"

[Setup]
AppId={{8E4A9C21-3F5B-4D76-9A10-6B2C7D8E9F01}
AppName={#AppName}
AppVersion={#AppVer}
AppVerName={#AppName} {#AppVer}
AppPublisher=NikkiNet
AppPublisherURL=https://github.com/MyNameIsNikki/NikkiNet
AppSupportURL=https://github.com/MyNameIsNikki/NikkiNet/issues
DefaultDirName={autopf}\NikkiNet
DefaultGroupName={#AppName}
DisableProgramGroupPage=yes
OutputDir=Output
OutputBaseFilename=NikkiNet-Setup-{#AppVer}
SetupIconFile=nikkinet.ico
UninstallDisplayIcon={app}\nikkinet.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
CloseApplications=no

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[CustomMessages]
russian.DefenderExcl=Добавить папку программы в исключения Защитника Windows (рекомендуется)
english.DefenderExcl=Add the program folder to Windows Defender exclusions (recommended)

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"
Name: "defexcl"; Description: "{cm:DefenderExcl}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: ".build\dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\nikkinet.ico"; Tasks: desktopicon
Name: "{group}\{#AppName}"; Filename: "{app}\{#AppExe}"; WorkingDir: "{app}"; IconFilename: "{app}\nikkinet.ico"
Name: "{group}\{cm:UninstallProgram,{#AppName}}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\{#AppExe}"; Description: "{cm:LaunchProgram,{#AppName}}"; Flags: postinstall nowait skipifsilent

[UninstallRun]
Filename: "{cmd}"; Parameters: "/C taskkill /F /IM sing-box.exe >nul 2>&1"; Flags: runhidden; RunOnceId: "KillSingBox"
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""NikkiNet LAN proxy"""; Flags: runhidden; RunOnceId: "RemoveLanFirewallRule"
Filename: "powershell.exe"; Parameters: "-NoProfile -ExecutionPolicy Bypass -Command ""try {{ Remove-MpPreference -ExclusionPath '{app}' -ErrorAction SilentlyContinue }} catch {{}}"""; Flags: runhidden; RunOnceId: "RemoveDefenderExcl"

[UninstallDelete]
Type: filesandordirs; Name: "{app}\.update"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\config.json"
Type: files; Name: "{app}\geo.json"
Type: files; Name: "{app}\.lock"
Type: files; Name: "{app}\crash.log"
Type: files; Name: "{app}\sing-box-config.json"
Type: dirifempty; Name: "{app}"

[Code]
procedure RunHidden(const CmdLine: String);
var
  ResultCode: Integer;
begin
  Exec(ExpandConstant('{cmd}'), '/C ' + CmdLine, '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
end;

procedure KillOldInstance();
var
  LockFile: String;
  WasRunning: Boolean;
begin
  LockFile := ExpandConstant('{app}\.lock');
  WasRunning := FileExists(LockFile);
  if WasRunning then
  begin
    RunHidden('for /f "usebackq delims=" %i in ("' + LockFile + '") do @taskkill /F /PID %i >nul 2>&1');
    DeleteFile(LockFile);
  end;
  RunHidden('taskkill /F /IM sing-box.exe >nul 2>&1');
  Sleep(700);
  if WasRunning then
    { the app was killed while the system proxy may have been enabled }
    RunHidden('reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Internet Settings" /v ProxyEnable /t REG_DWORD /d 0 /f >nul 2>&1');
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  Result := '';
  if WizardIsTaskSelected('defexcl') then
    RunHidden('powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "try { Add-MpPreference -ExclusionPath ''' + ExpandConstant('{app}') + ''' -ErrorAction SilentlyContinue } catch {}"');
  KillOldInstance();
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    KillOldInstance();
end;
