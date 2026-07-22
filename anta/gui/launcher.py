"""Ponto de entrada do executavel empacotado (PyInstaller).

Um exe so, que roteia por argv/estado:
  - COM argv (ex.: `anta config`, `anta run`, `anta toggle`): delega ao dispatch
    normal do `__main__` — o exe se comporta como o CLI.
  - SEM argv (duplo-clique): primeira vez (config nao 'configured') abre o
    Configurador; ja configurado sobe o App de execucao (HUD). Nunca a TUI —
    no build empacotado a GUI e o padrao (a TUI fica pro `-m anta` no dev).
"""
from __future__ import annotations

import sys


def choose_default() -> str:
    """Subcomando padrao no frozen quando nao ha argv: 'config' ou 'app'."""
    from anta.core.config import load_user_config

    return "app" if load_user_config().configured else "config"


def main() -> None:
    # Chokepoint do exe empacotado: sem console, stdout/stderr sao None e todo
    # print/traceback crasharia (mata a worker do runtime). Redireciona pro anta.log.
    from anta.gui.log import redirect_std_to_log

    redirect_std_to_log()
    if len(sys.argv) <= 1:
        # sem argv: injeta o subcomando escolhido antes de delegar
        sys.argv.append(choose_default())
    from anta.__main__ import main as dispatch

    dispatch()


if __name__ == "__main__":
    main()
