; Inno Setup script da ANTA (Windows). ASCII-only.
; Empacota a saida do PyInstaller (dist\anta\*) num instalador com "run after
; install" e autostart opcional. Gere com:  ISCC.exe packaging\windows\anta.iss
; (ou packaging\build.ps1 -Inno). O exe da ANTA e um app de janela (GUI).

#define MyAppName "ANTA"
#define MyAppExeName "anta.exe"

[Setup]
AppName={#MyAppName}
AppVersion=0.4.0
DefaultDirName={autopf}\ANTA
DefaultGroupName=ANTA
DisableProgramGroupPage=yes
OutputDir=..\..\dist
OutputBaseFilename=ANTA-Setup
Compression=lzma2
SolidCompression=yes
ArchitecturesInstallIn64BitMode=x64compatible
PrivilegesRequired=lowest
WizardStyle=modern

[Files]
; a pasta COLLECT do PyInstaller (exe + _internal + web/ + modes.yaml)
Source: "..\..\dist\anta\*"; DestDir: "{app}"; Flags: recursesubdirs createallsubdirs

[Icons]
Name: "{group}\ANTA"; Filename: "{app}\{#MyAppExeName}"
Name: "{group}\Configurar ANTA"; Filename: "{app}\{#MyAppExeName}"; Parameters: "config"
Name: "{autodesktop}\ANTA"; Filename: "{app}\{#MyAppExeName}"; Tasks: desktopicon

[Tasks]
Name: "desktopicon"; Description: "Criar atalho na area de trabalho"; Flags: unchecked
Name: "autostart"; Description: "Iniciar a ANTA ao ligar o computador"; Flags: unchecked

[Registry]
; autostart do App de execucao no login (HKCU\...\Run), so se o usuario marcar
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; \
  ValueName: "anta"; ValueData: """{app}\{#MyAppExeName}"" app"; Tasks: autostart; Flags: uninsdeletevalue

[Run]
; "run after install": abre o Configurador ao terminar
Filename: "{app}\{#MyAppExeName}"; Parameters: "config"; \
  Description: "Configurar a ANTA agora"; Flags: nowait postinstall skipifsilent
