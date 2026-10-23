; NikkiNet Parser installer (Inno Setup 6)
; Build: ISCC.exe /DAppVer=1.0.0 parser.iss

#ifndef AppVer
#define AppVer "1.0.0"
#endif

[Setup]
AppId={{C4E7A1B2-9D31-4F60-8E52-7A3B1C6D9F02}
AppName=NikkiNet Parser
AppVersion={#AppVer}
AppVerName=NikkiNet Parser {#AppVer}
AppPublisher=NikkiNet
DefaultDirName={localappdata}\NikkiNet Parser
DefaultGroupName=NikkiNet Parser
DisableProgramGroupPage=yes
PrivilegesRequired=lowest
OutputDir=Output
OutputBaseFilename=NikkiNet-Parser-Setup-{#AppVer}
SetupIconFile=parser.ico
UninstallDisplayIcon={app}\parser.ico
Compression=lzma2/max
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
UsePreviousAppDir=yes

[Languages]
Name: "russian"; MessagesFile: "compiler:Languages\Russian.isl"
Name: "english"; MessagesFile: "compiler:Default.isl"

[Tasks]
Name: "desktopicon"; Description: "{cm:CreateDesktopIcon}"; GroupDescription: "{cm:AdditionalIcons}"; Flags: checkedonce

[Files]
Source: ".build\dist\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs ignoreversion

[Icons]
Name: "{autodesktop}\NikkiNet Parser"; Filename: "{app}\start_parser.bat"; WorkingDir: "{app}"; IconFilename: "{app}\parser.ico"; Tasks: desktopicon
Name: "{group}\NikkiNet Parser"; Filename: "{app}\start_parser.bat"; WorkingDir: "{app}"; IconFilename: "{app}\parser.ico"
Name: "{group}\{cm:UninstallProgram,NikkiNet Parser}"; Filename: "{uninstallexe}"

[Run]
Filename: "{app}\start_parser.bat"; Description: "{cm:LaunchProgram,NikkiNet Parser}"; Flags: postinstall nowait skipifsilent

[UninstallDelete]
Type: filesandordirs; Name: "{app}\result"
Type: filesandordirs; Name: "{app}\tools"
Type: filesandordirs; Name: "{app}\__pycache__"
Type: files; Name: "{app}\parser_ui.lock"

[Code]
procedure KillOldInstance();
var
  ResultCode: Integer;
  LockFile: String;
begin
  LockFile := ExpandConstant('{app}\parser_ui.lock');
  if FileExists(LockFile) then
  begin
    Exec(ExpandConstant('{cmd}'),
      '/C for /f "usebackq delims=" %i in ("' + LockFile + '") do @taskkill /F /PID %i >nul 2>&1',
      '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    DeleteFile(LockFile);
    Sleep(600);
  end;
end;

function PrepareToInstall(var NeedsRestart: Boolean): String;
begin
  KillOldInstance();
  Result := '';
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  if CurUninstallStep = usUninstall then
    KillOldInstance();
end;
