"""Configuracao do atalho global, em camadas, decidida pelo SO detectado.

Estrategia (ver detect.Environment.hotkey_strategy):
  auto_win    -> Windows: daemon `anta run` no login; captura a tecla in-process
  auto_x11    -> Linux X11: daemon `anta run` no login; captura a tecla in-process
  compositor  -> Linux Wayland/KDE: daemon quente + atalho do SO chama `anta toggle`
  manual      -> macOS/desconhecido: apenas instrucao

Filosofia: automacao onde e confiavel; documentacao onde nao e. No Wayland
o proprio design bloqueia apps de sequestrar teclas globais, entao o caminho
manual (docs/atalhos.md) NAO e desistir — e o tier mais robusto.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from anta.platform.detect import Environment, detect


def _default_command() -> str:
    """Prefixo do comando usando o interpretador atual (robusto em venv)."""
    return f"{sys.executable} -m anta"


def _autostart_linux(command: str) -> bool:
    """Cria ~/.config/autostart/anta.desktop para subir o daemon ao logar."""
    try:
        path = Path.home() / ".config" / "autostart" / "anta.desktop"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=anta\n"
            f"Exec={command}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "Comment=Assistente de voz push-to-talk (daemon quente)\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def _autostart_windows(command: str) -> bool:
    """Registra o daemon no login via HKCU\\...\\Run."""
    try:
        subprocess.run(
            ["reg", "add",
             r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run",
             "/v", "anta", "/t", "REG_SZ", "/d", command, "/f"],
            capture_output=True, timeout=10, check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def _kde_instructions(toggle_command: str) -> str:
    """Passo-a-passo do KDE (Wayland) preenchido com o comando de toggle."""
    return (
        "KDE (Wayland): o daemon fica quente via autostart, mas o atalho e "
        "criado pelo proprio KDE (apps nao capturam teclas globais):\n"
        "  1. Configuracoes do Sistema > Atalhos > Adicionar > Atalho de Comando/URL\n"
        f"  2. Comando: {toggle_command}\n"
        "  3. Clique na coluna de atalho e pressione a combinacao (ex.: Ctrl+Alt+Espaco)\n"
        "  4. Aplicar\n"
        "Passo-a-passo completo em docs/atalhos.md."
    )


def setup_hotkey(env: Environment | None = None, command: str | None = None) -> str:
    """Configura o atalho conforme o ambiente. Retorna instrucao para o usuario."""
    env = env or detect()
    command = command or _default_command()
    strategy = env.hotkey_strategy

    if strategy == "auto_x11":
        ok = _autostart_linux(f"{command} run")
        base = instructions_for(env, f"{command} run")
        prefix = ("Daemon 'anta run' adicionado ao autostart; ele escuta o atalho "
                  "configurado ao logar.\n") if ok else ""
        return prefix + base

    if strategy == "auto_win":
        ok = _autostart_windows(f"{command} run")
        base = instructions_for(env, f"{command} run")
        prefix = "Daemon 'anta run' registrado no login do Windows.\n" if ok else ""
        return prefix + base

    if strategy == "compositor":
        _autostart_linux(f"{command} run")  # mantem o modelo quente
        return _kde_instructions(f"{command} toggle")

    return instructions_for(env, f"{command} run")


def instructions_for(env: Environment, command: str) -> str:
    """Texto de atalho correto para ESTE ambiente (nao um README generico)."""
    if env.os == "windows":
        return (f"Windows: o instalador registra o atalho automaticamente. "
                f"Se preferir manual, crie um atalho apontando para: {command}")
    if env.is_wayland:
        return (
            "KDE (Wayland): Configuracoes do Sistema > Atalhos > Adicionar > "
            "Atalho de Comando/URL. Aponte para:\n"
            f"    {command}\n"
            "e defina a combinacao de teclas desejada. Passo-a-passo completo "
            "em docs/atalhos.md."
        )
    if env.os == "linux":
        return (f"Linux (X11): o instalador pode registrar automaticamente. "
                f"Manual: mapeie um atalho para: {command}")
    return f"Crie um atalho do sistema apontando para: {command}"
