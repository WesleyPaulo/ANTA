"""Estados do runtime — o contrato entre o pipeline/Session e a GUI.

So dados + um helper de emissao; ZERO I/O e ZERO dependencia de `anta.gui` (o
core nao pode depender da GUI). A `StateMachine` e o emitter pro front vivem em
`anta/gui/state.py`, que importa DAQUI. O daemon CLI (`anta run`) nao passa
`on_state`, entao `emit` vira no-op e nada muda no headless.
"""
from __future__ import annotations

from enum import Enum
from typing import Callable


class State(str, Enum):
    CARREGANDO = "carregando"     # subindo os modelos
    PRONTO = "pronto"             # aguardando o atalho
    OUVINDO = "ouvindo"           # gravando
    PROCESSANDO = "processando"   # transcrevendo + decidindo
    RESPONDENDO = "respondendo"   # executando a acao / falando
    DESCARREGADO = "descarregado" # memoria desalocada + ANTA pausada (!= app fechado)
    ERRO = "erro"                 # falha (code diz qual: "mic", ...)


# on_state recebe (state_str, **payload). Payload livre: text, code, hint...
OnState = Callable[..., None]


def emit(on_state: OnState | None, state: State | str, **payload) -> None:
    """Emite um estado tipado, se houver ouvinte. Best-effort: nunca levanta."""
    if on_state is None:
        return
    value = state.value if isinstance(state, State) else str(state)
    try:
        on_state(value, **payload)
    except Exception:  # noqa: BLE001 - emissao de estado nunca derruba o pipeline
        pass
