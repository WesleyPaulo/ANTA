#!/usr/bin/env bash
# Build do executavel da ANTA no Linux/macOS (rodar UMA VEZ neste SO).
#   ./packaging/build.sh            # front + PyInstaller
#   ./packaging/build.sh --appimage # + AppImage (precisa do appimagetool no PATH)
#
# Pre-requisitos: node/npm, python com as deps (pip install -r requirements.txt),
# e pyinstaller (o script instala se faltar).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> [1/3] build do frontend (Vite: configurador + runtime)"
( cd frontend && npm ci && npm run build )

echo "==> [2/3] PyInstaller"
python -c "import PyInstaller" 2>/dev/null || pip install pyinstaller
rm -rf build dist
pyinstaller packaging/anta.spec
echo "    -> dist/anta/anta"

if [[ "${1:-}" == "--appimage" ]]; then
  echo "==> [3/3] AppImage"
  if ! command -v appimagetool >/dev/null 2>&1; then
    echo "    appimagetool nao encontrado no PATH — pulei o AppImage."
    echo "    Baixe em https://github.com/AppImage/AppImageKit/releases"
    exit 0
  fi
  APPDIR="dist/ANTA.AppDir"
  rm -rf "$APPDIR"
  mkdir -p "$APPDIR/usr"
  cp -r dist/anta/* "$APPDIR/usr/"
  cp packaging/linux/AppRun "$APPDIR/AppRun"
  chmod +x "$APPDIR/AppRun"
  cp packaging/linux/anta.desktop "$APPDIR/anta.desktop"
  # icone placeholder (256x256) se houver; senao um vazio (o appimagetool exige um)
  cp packaging/linux/anta.png "$APPDIR/anta.png" 2>/dev/null || : > "$APPDIR/anta.png"
  appimagetool "$APPDIR" "dist/ANTA-x86_64.AppImage"
  echo "    -> dist/ANTA-x86_64.AppImage"
else
  echo "==> pronto. (rode com --appimage para gerar o AppImage)"
fi
