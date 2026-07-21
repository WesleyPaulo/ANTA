"""Maquina de estados + emitter da GUI (usada pelo App de execucao, M4).

O `Pipeline`/`Session` emitem estados via `on_state` (string tipada; ver
`anta/core/states.py`). Aqui a `StateMachine` guarda o estado atual e repassa cada
transicao aos ouvintes — um deles e o `make_pywebview_emitter`, que empurra o evento
pro Vue via `window.__antaOnState` (marshalado na thread da GUI pelo pywebview).
"""
from __future__ import annotations

from typing import Callable

from anta.core.states import State

Listener = Callable[[dict], None]


class StateMachine:
    """Estado atual + lista de ouvintes. `transition` aceita State ou string
    (o que o `on_state` do pipeline emite) e normaliza para o enum."""

    def __init__(self, listeners: list[Listener] | None = None,
                 initial: State = State.CARREGANDO) -> None:
        self.current = initial
        self._listeners: list[Listener] = list(listeners or [])

    def add_listener(self, fn: Listener) -> None:
        self._listeners.append(fn)

    def transition(self, state: State | str, **payload) -> dict:
        self.current = state if isinstance(state, State) else State(state)
        event = {"state": self.current.value}
        event.update({k: v for k, v in payload.items() if v is not None})
        for fn in list(self._listeners):
            try:
                fn(event)
            except Exception:  # noqa: BLE001 - um ouvinte ruim nao trava os outros
                pass
        return event

    def snapshot(self) -> dict:
        """Estado atual (o front chama no mount p/ evitar corrida no boot)."""
        return {"state": self.current.value}


def make_pywebview_emitter(window) -> Listener:
    """Ouvinte que empurra o evento pro JS (window.__antaOnState). Best-effort."""
    def emit(event: dict) -> None:
        if window is None:
            return
        import json

        try:
            data = json.dumps(event)
            window.evaluate_js(f"window.__antaOnState && window.__antaOnState({data})")
        except Exception:  # noqa: BLE001
            pass

    return emit
