"""Resolve a raiz web (o `dist/` do Vite) que a janela PyWebview carrega.

Tres cenarios, controlados por ambiente (guia §3 "Dev vs build"):
  1. DEV   (ANTA_GUI_DEV=1): aponta pro dev server do Vite (hot reload).
  2. FROZEN (PyInstaller):   o `dist/` foi empacotado em `sys._MEIPASS/web/<app>`.
  3. BUILD  (editable/-e .):  o `dist/` fica em `frontend/apps/<app>/dist`, resolvido
     pela RAIZ DO REPO a partir deste arquivo (nunca do CWD — mesmo motivo do
     `config.default_modes_path`: o app pode subir de qualquer pasta).

Sob `file://` os assets tem que ser relativos (`base: './'` no vite.config) e o
router precisa ser hash/memory — senao quebra (guia §7).
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Uma porta por app, pra rodar os dois dev servers em paralelo no futuro.
DEV_PORTS = {"configurador": 5173, "runtime": 5174}


def is_dev() -> bool:
    """Modo dev = servir do Vite (hot reload) em vez do dist/ estatico."""
    return os.environ.get("ANTA_GUI_DEV", "").strip() in {"1", "true", "yes"}


def _repo_root() -> Path:
    """Raiz do repo, a partir deste arquivo: anta/gui/assets.py -> parents[2]."""
    return Path(__file__).resolve().parents[2]


def dist_index(app: str = "configurador") -> Path:
    """Caminho do `index.html` empacotado/buildado (cenarios FROZEN e BUILD)."""
    if getattr(sys, "frozen", False):
        base = Path(getattr(sys, "_MEIPASS", ".")) / "web" / app
    else:
        base = _repo_root() / "frontend" / "apps" / app / "dist"
    return base / "index.html"


def web_url(app: str = "configurador") -> str:
    """URL/caminho que o `webview.create_window(url=...)` deve carregar.

    DEV -> http do Vite; senao -> o index.html do dist como file:// URI."""
    if is_dev():
        port = DEV_PORTS.get(app, 5173)
        return f"http://localhost:{port}"
    return dist_index(app).as_uri()


def build_missing(app: str = "configurador") -> bool:
    """True se NAO estamos em dev e o dist/ ainda nao foi buildado.

    Deixa o bootstrap dar um erro com direcao ('rode npm run build') em vez de
    abrir uma janela em branco (guia §7: erros com direcao)."""
    return not is_dev() and not dist_index(app).exists()
