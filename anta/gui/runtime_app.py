"""Bootstrap do App de execucao (App B) — o HUD residente na bandeja.

Modelo de threads (o pywebview e dono da thread principal / GUI):
  - Thread PRINCIPAL: cria a janela, registra SIGUSR1 (tem que ser na main) + o
    atalho pynput (X11/Windows), sobe a bandeja e chama webview.start() (bloqueia).
  - Thread WORKER: aquece os modelos (carregando->pronto) e roda o loop push-to-talk
    (`Session.toggle`), que emite os estados via on_state. O TTS bloqueia AQUI, entao
    a GUI nunca trava.
  - Tres fontes de gatilho convergem no mesmo Event: pynput, SIGUSR1 (`anta toggle`)
    e o botao do HUD (`RuntimeApi.toggle`). `Session.on` ja sequencia grava/para.

So LE o config (single-writer: quem escreve e o Configurador).
"""
from __future__ import annotations

import os
import signal
import sys
import threading

from anta.gui import assets
from anta.gui.bridge_runtime import RuntimeApi

_APP = "runtime"
_TITLE = "ANTA"


def main() -> None:
    if assets.build_missing(_APP):
        idx = assets.dist_index(_APP)
        print(f"[anta] HUD nao buildado (nao achei {idx}).\n"
              f"       Rode:  cd frontend && npm install && npm run build\n"
              f"       Ou:  ANTA_GUI_DEV=1 anta app  (com 'npm run dev' rodando).",
              file=sys.stderr)
        sys.exit(1)
    try:
        import webview
    except ImportError:
        print("[anta] falta a dependencia 'pywebview'. Instale com:\n"
              "       pip install -r requirements.txt", file=sys.stderr)
        sys.exit(1)

    from anta.__main__ import Session, _notify, _pidfile, _to_pynput_hotkey
    from anta.core.capture import Recorder
    from anta.core.config import load_families, load_user_config
    from anta.core.pipeline import Pipeline
    from anta.core.states import State
    from anta.gui.state import StateMachine, make_pywebview_emitter
    from anta.gui.tray import start_tray
    from anta.platform.detect import detect

    cfg = load_user_config()
    families = load_families()
    family = cfg.family_or_default(families)
    mode = cfg.mode_or_default(family.modes)

    pipeline = Pipeline(
        stt_key=mode.stt, llm=mode.llm, obsidian_vault=cfg.obsidian_vault,
        tts=cfg.tts, tts_voice=cfg.tts_voice, tts_output=cfg.tts_output,
        rag=cfg.rag, web=cfg.web, web_engine=cfg.web_engine,
        web_searxng_url=cfg.web_searxng_url, structured=mode.structured,
    )
    sm = StateMachine(initial=State.CARREGANDO)
    trigger = threading.Event()
    recorder = Recorder(cfg.mic_device)
    session = Session(recorder, pipeline, _notify, on_state=sm.transition)

    api = RuntimeApi(sm, trigger, pipeline)
    window = webview.create_window(
        _TITLE, url=assets.web_url(_APP), js_api=api,
        width=400, height=540, min_size=(360, 480), on_top=True,
    )
    sm.add_listener(make_pywebview_emitter(window))
    api.set_window(window)

    # pidfile (p/ `anta toggle` do Wayland achar este processo) + SIGUSR1 (main thread)
    pid_path = _pidfile()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, lambda *_: trigger.set())

    env = detect()
    listener = None
    if env.captures_hotkey_in_process:
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys({_to_pynput_hotkey(cfg.hotkey): trigger.set})
            listener.start()
        except Exception as e:  # noqa: BLE001
            _notify(f"nao consegui registrar {cfg.hotkey} in-process ({e}).")

    stop = threading.Event()

    def worker() -> None:
        # carregando -> pronto (ou erro se o modelo nao esta instalado)
        try:
            aviso = pipeline.warm()
        except Exception as e:  # noqa: BLE001
            aviso = str(e)
        if aviso:
            sm.transition(State.ERRO, code="model", text=aviso)
        else:
            sm.transition(State.PRONTO)
        # loop push-to-talk (timeout p/ checar o stop e sair limpo)
        while not stop.is_set():
            if trigger.wait(timeout=0.5):
                trigger.clear()
                if not stop.is_set():
                    session.toggle()

    threading.Thread(target=worker, daemon=True).start()
    icon = start_tray(api, window)

    try:
        webview.start()
    finally:
        stop.set()
        trigger.set()  # destrava o worker p/ ele ver o stop
        if listener is not None:
            listener.stop()
        if icon is not None:
            try:
                icon.stop()
            except Exception:  # noqa: BLE001
                pass
        pid_path.unlink(missing_ok=True)


if __name__ == "__main__":
    main()
