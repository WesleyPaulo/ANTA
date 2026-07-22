# Build do executavel da ANTA no Windows (rodar UMA VEZ neste SO).
#   powershell -ExecutionPolicy Bypass -File packaging\build.ps1
#   ...\build.ps1 -Inno   # + instalador (precisa do Inno Setup / ISCC no PATH)
#
# Pre-requisitos: node/npm, python com as deps (pip install -r requirements.txt).
# ASCII-only (mesma regra do install.ps1; ver tests/test_install_scripts.py).
param([switch]$Inno)

$ErrorActionPreference = "Stop"
$Root = (Resolve-Path "$PSScriptRoot\..").Path
Set-Location $Root

Write-Host "==> [1/3] build do frontend (Vite: configurador + runtime)"
Push-Location frontend
npm ci
npm run build
Pop-Location

Write-Host "==> [2/3] PyInstaller"
python -c "import PyInstaller" 2>$null
if ($LASTEXITCODE -ne 0) { pip install pyinstaller }
if (Test-Path build) { Remove-Item -Recurse -Force build }
if (Test-Path dist) { Remove-Item -Recurse -Force dist }
pyinstaller packaging\anta.spec
Write-Host "    -> dist\anta\anta.exe"

if ($Inno) {
  Write-Host "==> [3/3] Inno Setup"
  $iscc = Get-Command ISCC.exe -ErrorAction SilentlyContinue
  if ($null -eq $iscc) {
    Write-Host "    ISCC.exe (Inno Setup) nao encontrado no PATH - pulei o instalador."
    Write-Host "    Instale o Inno Setup: https://jrsoftware.org/isdl.php"
    exit 0
  }
  ISCC.exe packaging\windows\anta.iss
  Write-Host "    -> dist\ANTA-Setup.exe"
} else {
  Write-Host "==> pronto. (rode com -Inno para gerar o instalador)"
}
