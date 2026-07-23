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
    release: str = ""  # ex: "11" (Windows), "6.6.87" (kernel Linux), "14" (macOS)

    @property
    def is_wayland(self) -> bool:
        return self.session == "wayland"

    @property
    def label(self) -> str:
        """Nome do SO para MOSTRAR ('Windows 11', 'Linux 6.6', 'macOS 14').

        O card do Configurador imprimia `os` e `session` crus, e no Windows os dois
        valem "windows" — a tela dizia "windows / windows", que nao informa nada."""
        nomes = {"windows": "Windows", "linux": "Linux", "macos": "macOS",
                 "unknown": "Sistema desconhecido"}
        base = nomes.get(self.os, self.os.capitalize())
        if not self.release:
            return base
        if self.os == "linux":  # kernel: 6.6.87.2-microsoft -> 6.6
            curto = ".".join(self.release.split(".")[:2])
            return f"{base} {curto}"
        return f"{base} {self.release}"

    @property
    def detail(self) -> str:
        """Segunda linha do card: o que ACRESCENTA ao nome do SO.

        No Linux, o que muda o comportamento e a sessao + desktop (e o que decide a
        estrategia de atalho). No Windows nao ha nada disso, entao dizemos o que de
        fato interessa ali: como o atalho global vai funcionar."""
        if self.os == "linux":
            partes = [p for p in (self.session, self.desktop) if p and p != "unknown"]
            return " · ".join(partes) or "sessão desconhecida"
        if self.captures_hotkey_in_process:
            return "atalho global automático"
        if self.hotkey_strategy == "compositor":
            return "atalho pelo sistema"
        return "atalho manual"

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
    release = platform.release()
    if system == "windows":
        return Environment(os="windows", session="windows", desktop="", release=release)
    if system == "darwin":
        # release() no mac e a versao do Darwin (23.x), nao a do macOS (14.x)
        return Environment(os="macos", session="unknown", desktop="",
                           release=platform.mac_ver()[0])
    if system == "linux":
        session = os.environ.get("XDG_SESSION_TYPE", "").lower() or "unknown"
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "")
        return Environment(os="linux", session=session, desktop=desktop, release=release)
    return Environment(os="unknown", session="unknown", desktop="")


if __name__ == "__main__":
    print(detect())
