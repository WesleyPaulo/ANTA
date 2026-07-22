"""A ponte Python <-> Vue do App de execucao (App B) — o HUD residente.

Ao contrario do Configurador, aqui e TUDO SO-LEITURA do config (single-writer: só o
Configurador escreve). O HUD reflete a `StateMachine` (empurrada via evaluate_js) e
oferece controles: falar/parar (converge no mesmo `_trigger` do atalho), carregar/
descarregar o modelo (libera VRAM), e abrir o Configurador no fluxo "nao ouviu".

Colaboradores injetados pelo `runtime_app` (e por testes): a maquina de estados, o
Event do toggle e o Pipeline. Nada de I/O pesado no __init__.
"""
from __future__ import annotations

from dataclasses import asdict

from anta.core.states import State


class RuntimeApi:
    """API exposta ao HUD. Instanciada pelo runtime_app e passada como js_api."""

    def __init__(self, statemachine, trigger, pipeline, *, config_path=None) -> None:
        self._sm = statemachine     # anta.gui.state.StateMachine
        self._trigger = trigger     # threading.Event (mesma fonte do atalho)
        self._pipeline = pipeline   # anta.core.pipeline.Pipeline
        self._config_path = config_path
        self._window = None

    def set_window(self, window) -> None:
        self._window = window

    # --- estado ---
    def get_state(self) -> dict:
        """Estado atual (o front chama no mount p/ evitar corrida no boot)."""
        return self._sm.snapshot()

    # --- push-to-talk (converge com o atalho no mesmo Event) ---
    def toggle(self) -> None:
        """Botao falar/parar: dispara o mesmo gatilho do atalho global."""
        self._trigger.set()

    # --- ciclo de vida do modelo (o botao "descarregar" libera VRAM) ---
    def load_model(self) -> dict:
        self._sm.transition(State.CARREGANDO)
        aviso = self._pipeline.warm()
        if aviso:
            self._sm.transition(State.ERRO, code="model", text=aviso)
            return {"ok": False, "msg": aviso}
        self._sm.transition(State.PRONTO)
        return {"ok": True, "msg": ""}

    def unload_model(self) -> dict:
        aviso = self._pipeline.unload()
        self._sm.transition(State.DESCARREGADO)
        # unload e best-effort: mesmo com aviso do Ollama, o estado vira descarregado.
        return {"ok": aviso is None, "msg": aviso or ""}

    # --- leitura (nunca escreve) ---
    def get_config(self) -> dict:
        from anta.core.config import load_user_config

        return asdict(load_user_config(self._config_path))

    def list_microphones(self) -> list[dict]:
        from anta.core.capture import list_input_devices

        return [{"name": d["name"]} for d in list_input_devices()]

    def list_speakers(self) -> list[dict]:
        from anta.core.capture import list_output_devices

        return [{"name": d["name"]} for d in list_output_devices()]

    # --- fluxo "nao ouviu" -> abre o Configurador (o unico writer) ---
    def open_configurador(self) -> dict:
        """Abre o Configurador noutro processo. O runtime NUNCA escreve o config;
        trocar de microfone e responsabilidade do Configurador (single-writer)."""
        import subprocess
        import sys

        try:
            subprocess.Popen([sys.executable, "-m", "anta", "config"])
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    # --- janela / bandeja ---
    def hide(self) -> None:
        if self._window is not None:
            try:
                self._window.hide()
            except Exception:  # noqa: BLE001
                pass

    def show(self) -> None:
        if self._window is not None:
            try:
                self._window.show()
            except Exception:  # noqa: BLE001
                pass
