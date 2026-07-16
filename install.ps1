# Bootstrap de instalacao do ANTA (Windows).
#
# Instala os pre-requisitos que o pip NAO cobre (pandoc, Ollama), prepara o
# ambiente Python com `uv` e abre o instalador TUI. No Windows os wheels de
# sounddevice/pynput ja trazem as libs nativas (nao precisa de portaudio/dev).
#
# Uso:  powershell -ExecutionPolicy Bypass -File .\install.ps1
$ErrorActionPreference = "Stop"

function Log($m)  { Write-Host "[anta] $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "[anta] $m" -ForegroundColor Yellow }

$RepoDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $RepoDir

function Have($cmd) { $null -ne (Get-Command $cmd -ErrorAction SilentlyContinue) }

Log "ANTA — bootstrap (Windows)"

# uv (gerencia Python + venv)
if (Have "uv") {
    Log "uv ja instalado."
} else {
    Log "instalando uv..."
    powershell -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    if (-not (Have "uv")) { throw "uv nao ficou no PATH. Abra um novo terminal e rode de novo." }
}

# pandoc + Ollama via winget (se disponivel)
if (Have "winget") {
    if (-not (Have "pandoc")) {
        Log "instalando pandoc (winget)..."
        winget install --id JohnMacFarlane.Pandoc -e --accept-package-agreements --accept-source-agreements
    }
    if (-not (Have "ollama")) {
        Log "instalando Ollama (winget)..."
        winget install --id Ollama.Ollama -e --accept-package-agreements --accept-source-agreements
    }
} else {
    Warn "winget nao encontrado. Instale manualmente: Pandoc (pandoc.org) e Ollama (ollama.com)."
}

# winget grava o PATH no registro, nao na sessao — recarrega pra TUI achar ollama/pandoc
$env:Path = [Environment]::GetEnvironmentVariable('Path', 'Machine') + ';' +
            [Environment]::GetEnvironmentVariable('Path', 'User')

Log "preparando o ambiente Python (.venv) com uv..."
uv venv --python 3.12 "$RepoDir\.venv"
$env:VIRTUAL_ENV = "$RepoDir\.venv"
uv pip install -r "$RepoDir\requirements.txt"
# Instala o proprio pacote (editavel). Sem isso, `python -m anta` so funciona com o
# CWD na pasta do repo — e o autostart do login (HKCU\...\Run) roda com o CWD do
# sistema, quebrando com ModuleNotFoundError. --no-deps: as deps ja vieram acima.
uv pip install -e "$RepoDir" --no-deps

Log "tudo pronto. Abrindo o instalador (escolha o modo e o microfone)..."
& "$RepoDir\.venv\Scripts\python.exe" -m anta
