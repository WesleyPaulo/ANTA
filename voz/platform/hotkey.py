"""Configuracao do atalho global, em camadas, decidida pelo SO detectado.

Estrategia (ver detect.Environment.hotkey_strategy):
  auto_win    -> Windows: listener na bandeja via RegisterHotKey (`keyboard`)
  auto_x11    -> Linux X11: pynput/keyboard capturam a tecla globalmente
  compositor  -> Linux Wayland/KDE: tenta kwriteconfig6; se falhar, cai na doc
  manual      -> macOS/desconhecido: apenas instrucao

Filosofia: automacao onde e confiavel; documentacao onde nao e. No Wayland
o proprio design bloqueia apps de sequestrar teclas globais, entao o caminho
manual (docs/atalhos.md) NAO e desistir — e o tier mais robusto.
"""
from __future__ import annotations

from voz.platform.detect import Environment, detect


def setup_hotkey(env: Environment | None = None, command: str = "python -m voz run") -> str:
    """Tenta configurar o atalho. Retorna uma instrucao para o usuario
    (vazia se conseguiu automaticamente).

    TODO(claude-code): implementar cada ramo. Para `compositor`, gerar os
    comandos kwriteconfig6 e, em erro, retornar o passo-a-passo de docs/atalhos.md
    ja preenchido com `command`.
    """
    env = env or detect()
    strategy = env.hotkey_strategy
    # TODO: ramos auto_win / auto_x11 / compositor / manual
    return instructions_for(env, command)


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
