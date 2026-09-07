; BamDude Windows Installer — Inno Setup script
;
; Builds a self-contained installer that lays down:
;   - embedded Python 3.12 + pre-installed venv
;   - backend source + pre-built frontend bundle
;   - NSSM + ffmpeg under bin/
;   - a Windows service running as LocalSystem
;
; Build prerequisites: run installers/windows/build.py first to stage
; the build/staging/ tree, then compile this file with ISCC.exe.
;
; See installers/windows/README.md for the full pipeline.

#define MyAppName "BamDude"
#define MyAppPublisher "BamDude Contributors"
#define MyAppURL "https://bamdude.top"
#define MyAppExeName "bamdude.exe"
#define ServiceName "BamDude"
#define DefaultPort "8000"

; Version is stamped by build.py into build\staging\version.iss as a
; #define directive. Falls back to a placeholder if you ran ISCC without
; running build.py first (don't ship that build).
#ifexist "build\staging\version.iss"
  #include "build\staging\version.iss"
#else
  #define MyAppVersion "0.0.0+dev"
#endif

[Setup]
AppId={{6D2F9C41-8A73-4B25-9E60-2C7A1F0B4D88}}
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
AppPublisherURL={#MyAppURL}
AppSupportURL={#MyAppURL}
AppUpdatesURL={#MyAppURL}
DefaultDirName={autopf}\BamDude
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
LicenseFile=..\..\LICENSE
OutputDir=build\output
OutputBaseFilename=bamdude-{#MyAppVersion}-windows-x64-setup
Compression=lzma
SolidCompression=yes
WizardStyle=modern
ArchitecturesAllowed=x64compatible
ArchitecturesInstallIn64BitMode=x64compatible
; Admin required: we register a Windows service and write to ProgramData
PrivilegesRequired=admin
PrivilegesRequiredOverridesAllowed=
; BamDude branding — bamdude.ico is the brand pack's favicon.ico (16/32/48/
; 64/128/256, dark bars on transparent), copied from bamdude.top/public/brand/;
; regenerate from the pack, never edit here. The dark-bars variant, not the
; dark-tile app-icon.ico: this icon is shown on light surfaces (Explorer, the
; Programs list, the wizard), where the tile's own dark ground swallowed the
; mark. Lives next to this .iss so the SourcePath-relative reference works
; during compile, and the [Files] entry stages it into {app} for Add/Remove
; Programs.
SetupIconFile=bamdude.ico
UninstallDisplayIcon={app}\bamdude.ico
; Don't allow installing to a network drive — service won't start cleanly
DisableDirPage=no
DisableReadyPage=no
ChangesEnvironment=no
CloseApplications=no

[Languages]
Name: "english"; MessagesFile: "compiler:Default.isl"
Name: "ukrainian"; MessagesFile: "compiler:Languages\Ukrainian.isl"

; Every string the wizard shows that is ours rather than Inno's. Keep both
; languages in step — a key present in only one falls back to the other
; language's text, which reads like a bug to the user.
[CustomMessages]
english.TaskDesktopIcon=Create a desktop shortcut
english.TaskGroupShortcuts=Additional shortcuts:
english.TaskFirewall=Add Windows Firewall rule for BamDude (port {#DefaultPort})
english.TaskGroupNetwork=Network:
english.IconDashboard=Open BamDude Dashboard
english.IconLogs=BamDude Logs
english.IconUninstall=Uninstall BamDude
english.StatusRegisterService=Registering BamDude service...
english.StatusFirewall=Adding firewall rule...
english.DbPageCaption=Database
english.DbPageDescription=Where should BamDude keep its data?
english.DbPageSubCaption=SQLite needs nothing and is a fine choice for most farms. PostgreSQL suits large, busy farms.
english.DbOptSqlite=SQLite (a single file, no server - recommended)
english.DbOptEmbeddedService=Bundled PostgreSQL 18, as its own Windows service (most robust)
english.DbOptEmbeddedChild=Bundled PostgreSQL 18, started and stopped by BamDude (simpler)
english.DbOptExternal=An external PostgreSQL server (enter its URL)
english.UrlPageCaption=External PostgreSQL
english.UrlPageDescription=Connection URL
english.UrlPageSubCaption=The database must already exist - BamDude creates the tables, not the database.
english.UrlPrompt=postgresql+asyncpg://user:password@host:5432/bamdude
english.UrlRequired=Please enter the PostgreSQL connection URL, or go back and choose SQLite.
english.UninstallDeleteData=Also delete all BamDude data (database, print archives, settings) in%n%1?%n%nChoose No to keep it for a future reinstall.
english.ServiceSetupFailed=BamDude was installed, but its Windows service could not be registered, so nothing is running yet.%n%nThe setup log is at:%n%1%n%nOpen it to see what failed, then re-run this installer.

ukrainian.TaskDesktopIcon=Створити ярлик на робочому столі
ukrainian.TaskGroupShortcuts=Додаткові ярлики:
ukrainian.TaskFirewall=Додати правило брандмауера Windows для BamDude (порт {#DefaultPort})
ukrainian.TaskGroupNetwork=Мережа:
ukrainian.IconDashboard=Відкрити панель BamDude
ukrainian.IconLogs=Журнали BamDude
ukrainian.IconUninstall=Видалити BamDude
ukrainian.StatusRegisterService=Реєстрація служби BamDude...
ukrainian.StatusFirewall=Додавання правила брандмауера...
ukrainian.DbPageCaption=База даних
ukrainian.DbPageDescription=Де BamDude має зберігати дані?
ukrainian.DbPageSubCaption=SQLite не потребує нічого і підходить більшості ферм. PostgreSQL — для великих завантажених ферм.
ukrainian.DbOptSqlite=SQLite (один файл, без сервера — рекомендовано)
ukrainian.DbOptEmbeddedService=Вбудований PostgreSQL 18 окремою службою Windows (найнадійніше)
ukrainian.DbOptEmbeddedChild=Вбудований PostgreSQL 18 під керуванням BamDude (простіше)
ukrainian.DbOptExternal=Зовнішній сервер PostgreSQL (вкажіть URL)
ukrainian.UrlPageCaption=Зовнішній PostgreSQL
ukrainian.UrlPageDescription=URL підключення
ukrainian.UrlPageSubCaption=База вже має існувати — BamDude створює таблиці, а не базу.
ukrainian.UrlPrompt=postgresql+asyncpg://user:password@host:5432/bamdude
ukrainian.UrlRequired=Введіть URL підключення до PostgreSQL або поверніться назад і оберіть SQLite.
ukrainian.UninstallDeleteData=Також видалити всі дані BamDude (база, архіви друку, налаштування) у%n%1?%n%nОберіть «Ні», щоб зберегти їх для наступного встановлення.
ukrainian.ServiceSetupFailed=BamDude встановлено, але службу Windows зареєструвати не вдалося, тож зараз нічого не запущено.%n%nЖурнал встановлення:%n%1%n%nВідкрийте його, щоб побачити причину, потім запустіть інсталятор ще раз.

[Tasks]
Name: "desktopicon"; Description: "{cm:TaskDesktopIcon}"; GroupDescription: "{cm:TaskGroupShortcuts}"; Flags: unchecked
Name: "firewallrule"; Description: "{cm:TaskFirewall}"; GroupDescription: "{cm:TaskGroupNetwork}"

[Files]
; Embedded Python (entire tree)
Source: "build\staging\python\*"; DestDir: "{app}\python"; Flags: recursesubdirs ignoreversion
; Backend + frontend
Source: "build\staging\app\*"; DestDir: "{app}\app"; Flags: recursesubdirs ignoreversion
; NSSM, ffmpeg, ffprobe
Source: "build\staging\bin\*"; DestDir: "{app}\bin"; Flags: recursesubdirs ignoreversion
; Service install/uninstall scripts
Source: "build\staging\service\*"; DestDir: "{app}\service"; Flags: recursesubdirs ignoreversion
; Version stamp
Source: "build\staging\VERSION"; DestDir: "{app}"; Flags: ignoreversion
; App icon — used by UninstallDisplayIcon (Add/Remove Programs) and the
; Start Menu / desktop shortcuts. Lives at the install root so the
; UninstallDisplayIcon path stays stable when the [Files] tree changes.
Source: "bamdude.ico"; DestDir: "{app}"; Flags: ignoreversion

[Dirs]
; ProgramData layout — created with permissions LocalSystem can write to
Name: "{commonappdata}\BamDude"; Permissions: users-modify
Name: "{commonappdata}\BamDude\data"; Permissions: users-modify
Name: "{commonappdata}\BamDude\logs"; Permissions: users-modify

[Icons]
Name: "{group}\{cm:IconDashboard}"; Filename: "http://localhost:{#DefaultPort}"; IconFilename: "{app}\bamdude.ico"
Name: "{group}\{cm:IconLogs}"; Filename: "{commonappdata}\BamDude\logs"
Name: "{group}\{cm:IconUninstall}"; Filename: "{uninstallexe}"
Name: "{commondesktop}\BamDude"; Filename: "http://localhost:{#DefaultPort}"; IconFilename: "{app}\bamdude.ico"; Tasks: desktopicon

[Run]
; Register and start the Windows service. The trailing arguments (database
; backend + optional URL) are built by GetInstallServiceParams in [Code] from
; the storage-chooser wizard page.
Filename: "{app}\service\install-service.bat"; Parameters: "{code:GetInstallServiceParams}"; Flags: runhidden waituntilterminated; StatusMsg: "{cm:StatusRegisterService}"

; Open Windows Firewall on the dashboard port. We do this only if the
; user opted in via the firewallrule task — some environments manage
; firewall centrally and prefer to handle this themselves.
Filename: "netsh.exe"; Parameters: "advfirewall firewall add rule name=""BamDude Dashboard"" dir=in action=allow protocol=TCP localport={#DefaultPort}"; Flags: runhidden waituntilterminated; Tasks: firewallrule; StatusMsg: "{cm:StatusFirewall}"

; Open the dashboard in the user's default browser at the end of install
Filename: "http://localhost:{#DefaultPort}"; Flags: shellexec postinstall nowait skipifsilent; Description: "{cm:IconDashboard}"

[UninstallRun]
; Stop + deregister the service before file removal. RunOnceId makes the
; entry run-once per uninstall pass (Inno Setup default is to re-run on
; every pass, which can fire multiple times during upgrade flows).
Filename: "{app}\service\uninstall-service.bat"; Parameters: """{app}"""; Flags: runhidden waituntilterminated; RunOnceId: "StopBamDudeService"

; Remove the firewall rule (silently — if it doesn't exist, netsh just complains)
Filename: "netsh.exe"; Parameters: "advfirewall firewall delete rule name=""BamDude Dashboard"""; Flags: runhidden waituntilterminated; RunOnceId: "RemoveFirewallRule"

[UninstallDelete]
; Remove install dir contents; leave ProgramData\BamDude alone so the
; user keeps their database + archives. Re-installing on top picks them
; back up automatically.
Type: filesandordirs; Name: "{app}"

[Code]

// --- Storage backend chooser -------------------------------------------------
//
// One wizard page with four choices, mirroring the app's DATABASE_URL states:
//   0 SQLite                              -> sqlite
//   1 bundled PostgreSQL, own service     -> embedded-service
//   2 bundled PostgreSQL, run by BamDude  -> embedded-child
//   3 external PostgreSQL (URL)           -> external
// The external URL is asked on a second page, shown only for choice 3.

var
  StoragePage: TInputOptionWizardPage;
  UrlPage: TInputQueryWizardPage;
  RemoveDataOnUninstall: Boolean;

// Read the current backend from the installed BamDude service's environment
// (NSSM keeps AppEnvironmentExtra as a REG_MULTI_SZ), so an upgrade defaults to
// what is already in use instead of silently reverting to SQLite. Returns the
// selected index, and the external URL through ExistingUrl.
function DetectExistingChoice(var ExistingUrl: String): Integer;
var
  Env: String;
begin
  Result := 0;
  ExistingUrl := '';
  if RegQueryMultiStringValue(HKLM, 'SYSTEM\CurrentControlSet\Services\BamDude\Parameters',
       'AppEnvironmentExtra', Env) then
  begin
    if Pos('EMBEDDED_PG_EXTERNAL_SERVICE=1', Env) > 0 then
      Result := 1
    else if Pos('DATABASE_URL=embedded', Env) > 0 then
      Result := 2
    else if Pos('DATABASE_URL=postgresql', Env) > 0 then
    begin
      Result := 3;
      // pull the URL out of the DATABASE_URL=... line for the field default
      ExistingUrl := Copy(Env, Pos('DATABASE_URL=postgresql', Env) + Length('DATABASE_URL='), 4096);
      // Cut at the first separator, whichever form RegQueryMultiStringValue used.
      if Pos(#0, ExistingUrl) > 0 then ExistingUrl := Copy(ExistingUrl, 1, Pos(#0, ExistingUrl) - 1);
      if Pos(#13, ExistingUrl) > 0 then ExistingUrl := Copy(ExistingUrl, 1, Pos(#13, ExistingUrl) - 1);
      if Pos(#10, ExistingUrl) > 0 then ExistingUrl := Copy(ExistingUrl, 1, Pos(#10, ExistingUrl) - 1);
    end;
  end;
end;

procedure InitializeWizard();
var
  ExistingUrl: String;
begin
  StoragePage := CreateInputOptionPage(wpSelectDir,
    CustomMessage('DbPageCaption'), CustomMessage('DbPageDescription'),
    CustomMessage('DbPageSubCaption'),
    True, False);
  StoragePage.Add(CustomMessage('DbOptSqlite'));
  StoragePage.Add(CustomMessage('DbOptEmbeddedService'));
  StoragePage.Add(CustomMessage('DbOptEmbeddedChild'));
  StoragePage.Add(CustomMessage('DbOptExternal'));

  UrlPage := CreateInputQueryPage(StoragePage.ID,
    CustomMessage('UrlPageCaption'), CustomMessage('UrlPageDescription'),
    CustomMessage('UrlPageSubCaption'));
  UrlPage.Add(CustomMessage('UrlPrompt'), False);

  StoragePage.SelectedValueIndex := DetectExistingChoice(ExistingUrl);
  if ExistingUrl <> '' then
    UrlPage.Values[0] := ExistingUrl;
end;

function ShouldSkipPage(PageID: Integer): Boolean;
begin
  Result := False;
  // The URL page only matters for the external choice (index 3).
  if PageID = UrlPage.ID then
    Result := StoragePage.SelectedValueIndex <> 3;
end;

function NextButtonClick(CurPageID: Integer): Boolean;
begin
  Result := True;
  if (CurPageID = UrlPage.ID) and (Trim(UrlPage.Values[0]) = '') then
  begin
    MsgBox(CustomMessage('UrlRequired'), mbError, MB_OK);
    Result := False;
  end;
end;

function GetDbMode(): String;
begin
  case StoragePage.SelectedValueIndex of
    1: Result := 'embedded-service';
    2: Result := 'embedded-child';
    3: Result := 'external';
  else
    Result := 'sqlite';
  end;
end;

// Full argument string for install-service.bat:
//   "<app>" "<data root>" <port> <db mode> "<url>"
function GetInstallServiceParams(Param: String): String;
var
  Url: String;
begin
  Url := '';
  if StoragePage.SelectedValueIndex = 3 then
    Url := Trim(UrlPage.Values[0]);
  Result := '"' + ExpandConstant('{app}') + '" "' + ExpandConstant('{commonappdata}\BamDude') + '" ' +
            '{#DefaultPort}' + ' ' + GetDbMode() + ' "' + Url + '"';
end;

// Stop the BamDude service (and the bundled PostgreSQL service, if any) BEFORE
// the [Files] section copies anything, so file locks on python.exe / .pyd /
// nssm.exe / postgres.exe release in time for the overwrite. Without this,
// upgrading over a running install fails with "permission denied" on every
// file a service has open.
//
// On a fresh install {app}\bin\nssm.exe doesn't exist yet — FileExists guards
// that path so the hook is a no-op for first-time installers. The Sleep gives
// Windows a beat to finalize the unload before [Files] grabs exclusive handles.
function PrepareToInstall(var NeedsRestart: Boolean): String;
var
  ResultCode: Integer;
  NssmPath: string;
begin
  Result := '';
  NeedsRestart := False;

  // Stop the bundled PostgreSQL service first (BamDude depends on it), then
  // BamDude. Both are best-effort — a missing service just returns non-zero.
  Exec(ExpandConstant('{cmd}'), '/c net stop BamDudePostgres', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);

  NssmPath := ExpandConstant('{app}\bin\nssm.exe');
  if FileExists(NssmPath) then
  begin
    Log('Stopping BamDude service before file copy...');
    Exec(NssmPath, 'stop BamDude', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
    Sleep(1500);
  end;
end;

// install-service.bat runs hidden and Inno does not abort on a non-zero [Run]
// exit code, so a failed service registration used to leave the user with a
// finished-looking install, no service, an empty data directory and no message
// at all. Check for the service and point at the log if it is not there.
procedure CurStepChanged(CurStep: TSetupStep);
var
  ResultCode: Integer;
  Ok: Boolean;
  LogPath: String;
begin
  if CurStep <> ssPostInstall then
    Exit;
  // A line may not START with '[' anywhere in the script — the parser reads
  // that as a section tag, even inside [Code] — so the message argument is
  // bound to a variable first rather than written as an inline array.
  LogPath := ExpandConstant('{commonappdata}\BamDude\logs\install-service.log');
  Ok := Exec(ExpandConstant('{sys}\sc.exe'), 'query BamDude', '', SW_HIDE, ewWaitUntilTerminated, ResultCode);
  if (not Ok) or (ResultCode <> 0) then
    MsgBox(FmtMessage(CustomMessage('ServiceSetupFailed'), [LogPath]), mbError, MB_OK);
end;

function InitializeSetup(): Boolean;
begin
  Result := True;
  // Port-conflict check deferred: Inno has no native socket API, so a conflict
  // on 8000 surfaces at first service start and the user reads the log.
end;

// --- Uninstall: optionally remove all data ----------------------------------

function InitializeUninstall(): Boolean;
begin
  Result := True;
  // Default is to KEEP data (database, archives, config). Ask explicitly.
  RemoveDataOnUninstall :=
    MsgBox(FmtMessage(CustomMessage('UninstallDeleteData'), [ExpandConstant('{commonappdata}\BamDude')]),
      mbConfirmation, MB_YESNO or MB_DEFBUTTON2) = IDYES;
end;

procedure CurUninstallStepChanged(CurUninstallStep: TUninstallStep);
begin
  // The service-stop + deregister runs from [UninstallRun] before file removal.
  // Delete the data tree only here, after everything is stopped, and only if
  // the user asked for it.
  if (CurUninstallStep = usPostUninstall) and RemoveDataOnUninstall then
  begin
    Log('Removing BamDude data directory at user request');
    DelTree(ExpandConstant('{commonappdata}\BamDude'), True, True, True);
  end;
end;
