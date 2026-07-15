"""Reconhecimento de sistema operacional e sessão.

Não decide NADA de audio aqui — só reporta o ambiente para que a camada
de atalho (hotkey.py) escolha a estrategia certa.
"""
from __future__ import annotations

import os
import platform
from dataclasses import dataclass


@dataclass(frozen=True)
class Environment:
    os: str            # "windows" | "linux" | "macos" | "unknown"
    session: str       # "wayland" | "x11" | "windows" | "unknown"
    desktop: str       # ex: "KDE", "GNOME", "" (vazio no Windows)

    @property
    def is_wayland(self) -> bool:
        return self.session == "wayland"

    @property
    def hotkey_strategy(self) -> str:
        """Qual caminho de atalho global e viavel neste ambiente."""
        if self.os == "windows":
            return "auto_win"          # pynput GlobalHotKeys (in-process)
        if self.os == "linux" and self.session == "x11":
            return "auto_x11"          # pynput GlobalHotKeys (in-process)
        if self.os == "linux" and self.session == "wayland":
            return "compositor"        # KDE: tenta kwriteconfig6, cai no manual
        return "manual"                # macOS / desconhecido -> so documentacao

    @property
    def captures_hotkey_in_process(self) -> bool:
        """True quando o daemon captura a tecla via pynput no proprio processo
        (X11/Windows). No Wayland/manual o atalho do SO chama `anta toggle`."""
        return self.hotkey_strategy in ("auto_x11", "auto_win")


def detect() -> Environment:
    system = platform.system().lower()
    if system == "windows":
        return Environment(os="windows", session="windows", desktop="")
    if system == "darwin":
        return Environment(os="macos", session="unknown", desktop="")
    if system == "linux":
        session = os.environ.get("XDG_SESSION_TYPE", "").lower() or "unknown"
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        return Environment(os="linux", session=session, desktop=desktop)
    return Environment(os="unknown", session="unknown", desktop="")


if __name__ == "__main__":
    print(detect())
