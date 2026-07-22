# -*- mode: python ; coding: utf-8 -*-
"""Spec do PyInstaller para a ANTA. Roda UMA VEZ EM CADA SO (Windows/Linux nativo).

    cd <repo>
    # 1) build dos fronts (gera frontend/apps/*/dist):
    cd frontend && npm ci && npm run build && cd ..
    # 2) empacota:
    pyinstaller packaging/anta.spec

Pre-requisitos: deps instaladas (`pip install -r requirements.txt`) — o PyInstaller
rastreia os modulos REAIS, entao faster-whisper/piper/etc. precisam existir no venv.

Os dois `dist/` do Vite entram como `web/configurador` e `web/runtime` (o
`anta.gui.assets` resolve isso via sys._MEIPASS no frozen). `modes.yaml` idem
(`config.default_modes_path` ja tem o branch _MEIPASS). O entry e o launcher, que
roteia por argv/`configured`.
"""
from pathlib import Path

from PyInstaller.utils.hooks import collect_submodules

ROOT = Path(SPECPATH).parent  # SPECPATH = .../packaging ; ROOT = raiz do repo

_config_dist = ROOT / "frontend" / "apps" / "configurador" / "dist"
_runtime_dist = ROOT / "frontend" / "apps" / "runtime" / "dist"
for _d in (_config_dist, _runtime_dist):
    if not _d.exists():
        raise SystemExit(f"[anta.spec] front nao buildado: {_d}\n"
                         f"  Rode: cd frontend && npm ci && npm run build")

datas = [
    (str(ROOT / "modes.yaml"), "."),
    (str(ROOT / "config.example.toml"), "."),
    (str(_config_dist), "web/configurador"),
    (str(_runtime_dist), "web/runtime"),
]

# Deps importadas SOB DEMANDA (lazy) que a analise estatica do PyInstaller perde.
hiddenimports = [
    "faster_whisper", "fastembed", "piper", "sounddevice", "_sounddevice",
    "instructor", "openai", "webview", "yaml", "numpy", "pydantic", "ddgs",
]
# pynput/pystray/webview carregam backends de plataforma dinamicamente.
for _pkg in ("pynput", "pystray", "webview"):
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception:
        pass

a = Analysis(
    [str(ROOT / "packaging" / "entry.py")],
    pathex=[str(ROOT)],
    binaries=[],
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="anta",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,   # app de janela (GUI): sem console preto no Windows
    disable_windowed_traceback=False,
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="anta",
)
