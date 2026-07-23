"""A ponte Python <-> Vue do App de execucao (App B) — o HUD residente.

Ao contrario do Configurador, aqui e TUDO SO-LEITURA do config (single-writer: só o
Configurador escreve). O HUD reflete a `StateMachine` (empurrada via evaluate_js) e
oferece controles: falar/parar (converge no mesmo gatilho do atalho), PARAR o turno
em andamento, desalocar/carregar a memoria, o quanto de RAM/VRAM esta em uso, e
abrir o Configurador no fluxo "nao ouviu".

Colaboradores injetados pelo `runtime_app` (e por testes): a maquina de estados, o
Event do toggle, o Pipeline e a Session. Nada de I/O pesado no __init__.
"""
from __future__ import annotations

from dataclasses import asdict

from anta.core.states import State


class RuntimeApi:
    """API exposta ao HUD. Instanciada pelo runtime_app e passada como js_api."""

    def __init__(self, statemachine, trigger, pipeline, *, session=None,
                 config_path=None) -> None:
        self._sm = statemachine     # anta.gui.state.StateMachine
        self._trigger = trigger     # threading.Event (mesma fonte do atalho)
        self._pipeline = pipeline   # anta.core.pipeline.Pipeline
        self._session = session     # anta.__main__.Session (None em testes de unidade)
        self._config_path = config_path
        self._window = None

    def set_window(self, window) -> None:
        self._window = window

    # --- estado ---
    def get_state(self) -> dict:
        """Estado atual (o front chama no mount p/ evitar corrida no boot)."""
        return self._sm.snapshot()

    # --- push-to-talk (converge com o atalho no mesmo caminho) ---
    def toggle(self) -> None:
        """Botao falar/parar: mesmo gatilho do atalho global.

        Vai por `Session.request()`, que decide gravar / parar / ignorar (memoria
        desalocada). O caminho antigo — armar o Event e pronto — fazia um clique
        durante a resposta virar gravacao assim que o turno terminava."""
        if self._session is not None:
            self._session.request()
            return
        self._trigger.set()

    def cancel(self) -> dict:
        """Botao 'Parar' durante processando/respondendo: corta a fala do TTS e
        aborta o resto do turno. Chamado explicitamente pelo HUD (em vez de
        `toggle`) pra que um clique que chegue tarde — o turno acabou de terminar —
        seja um no-op, e nao uma gravacao acidental."""
        if self._session is not None:
            self._session.cancel()
        elif hasattr(self._pipeline, "cancel"):
            self._pipeline.cancel()
        return {"ok": True}

    # --- ciclo de vida do modelo (o botao "desalocar memoria") ---
    def load_model(self) -> dict:
        self._sm.transition(State.CARREGANDO)
        aviso = self._pipeline.warm()
        if aviso:
            self._sm.transition(State.ERRO, code="model", text=aviso)
            return {"ok": False, "msg": aviso}
        if self._session is not None:
            self._session.resume()
        self._sm.transition(State.PRONTO)
        return {"ok": True, "msg": ""}

    def unload_model(self) -> dict:
        """Desaloca memoria: solta o LLM da VRAM, larga Whisper/embedder da RAM e
        SUSPENDE a ANTA (o atalho para de gravar ate o usuario carregar de novo).

        Suspender antes de soltar e o que da sentido ao botao: sem isso o proximo
        atalho recarregava tudo em silencio e a memoria voltava sozinha — o usuario
        pedia pra liberar e a ANTA desfazia pelas costas."""
        if self._session is not None:
            self._session.suspend()
        aviso = self._pipeline.unload()
        self._sm.transition(State.DESCARREGADO)
        # unload e best-effort: mesmo com aviso do Ollama, o estado vira desalocado.
        return {"ok": aviso is None, "msg": aviso or ""}

    # --- memoria (o app residente tem que mostrar o que ocupa) ---
    def get_memory(self) -> dict:
        """VRAM da GPU (usada/total) + RAM do processo da ANTA, em GiB.

        A ANTA fica de pe com o Whisper na RAM e o LLM fixo na VRAM: sem um numero
        na tela, um app que nao esta 'fazendo nada' e indistinguivel de um vazamento.
        A VRAM e a da GPU inteira (o LLM vive no processo do Ollama, fora daqui) —
        rotulada como tal no HUD. Best-effort: campos viram None se nao der pra medir.
        """
        from anta.gui.detection import process_ram_gb
        from anta.installer.hardware import vram_usage_gb

        usada, total = vram_usage_gb()
        return {
            "loaded": self._sm.current is not State.DESCARREGADO,
            "vram_used_gb": usada,
            "vram_total_gb": total,
            "ram_used_gb": process_ram_gb(),
            "llm": getattr(getattr(self._pipeline, "brain", None), "llm", "") or "",
        }

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
        """Mostra a janela. `restore()` junto porque "escondida" e "minimizada" sao
        estados diferentes: quem clica no atalho da bandeja (ou tenta abrir a ANTA
        de novo) quer a janela NA FRENTE, venha ela de qual dos dois vier."""
        if self._window is None:
            return
        for metodo in ("show", "restore"):
            try:
                getattr(self._window, metodo)()
            except Exception:  # noqa: BLE001 - backend sem o metodo / janela morta
                pass
