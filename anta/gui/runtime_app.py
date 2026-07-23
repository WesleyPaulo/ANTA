"""Bootstrap do App de execucao (App B) — o HUD residente na bandeja.

Modelo de threads (o pywebview e dono da thread principal / GUI):
  - Thread PRINCIPAL: cria a janela, registra SIGUSR1 (tem que ser na main) + o
    atalho pynput (X11/Windows), sobe a bandeja e chama webview.start() (bloqueia).
  - Thread WORKER: aquece os modelos (carregando->pronto) e roda o loop push-to-talk
    (`Session.toggle`), que emite os estados via on_state. O TTS bloqueia AQUI, entao
    a GUI nunca trava.
  - Tres fontes de gatilho convergem em `Session.request()`: pynput, SIGUSR1
    (`anta toggle`) e o botao do HUD (`RuntimeApi.toggle`). E a `request` que decide
    gravar / parar / ignorar (suspenso) — enfileirar sempre era o bug do botao
    "Falar" ativo durante a fala.

So LE o config (single-writer: quem escreve e o Configurador).
"""
from __future__ import annotations

import os
import sys
import threading

from anta.gui import assets
from anta.gui.bridge_runtime import RuntimeApi

_APP = "runtime"
_TITLE = "ANTA"


def _fechar_para_a_bandeja(window, api, tray) -> bool:
    """Com bandeja no ar, o X ESCONDE a janela em vez de matar o processo.

    Um app com icone na bandeja promete continuar rodando; fechar a janela e
    perder o atalho global (e a ANTA inteira) contradiz isso. 'Sair' do menu
    encerra de verdade — ele marca `tray.quitting`, que este handler respeita
    (o `destroy()` passa por aqui tambem). Best-effort: se o backend do pywebview
    nao expuser o evento, o X volta a encerrar, como antes."""
    def _closing(*_a):
        if tray.quitting:
            return True
        api.hide()
        return False  # cancela o fechamento

    try:
        window.events.closing += _closing
        return True
    except Exception as e:  # noqa: BLE001 - backend sem o evento: comportamento antigo
        print(f"[anta] fechar-para-a-bandeja indisponivel ({e}).", file=sys.stderr)
        return False


def main() -> None:
    from anta.gui.log import redirect_std_to_log

    redirect_std_to_log()  # app de janela: sem isso print/traceback crasham (stdout None)
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

    from anta.__main__ import (
        Session, _notify, _pidfile, _to_pynput_hotkey, install_sigusr1,
    )
    from anta.platform.singleton import SingleInstance

    # Uma ANTA por vez. Duas nao sao "duas janelas": sao dois Whispers na RAM, dois
    # preloads disputando a VRAM e dois pynput no mesmo atalho. A segunda so pede
    # foco pra primeira e sai — clicar no atalho de novo TRAZ A ANTA pra frente.
    trava = SingleInstance("runtime")
    if not trava.acquire():
        trava.signal_existing()
        print("[anta] a ANTA ja esta aberta — trouxe a janela existente pra frente.")
        sys.exit(0)

    from anta.core.capture import Recorder
    from anta.core.config import load_families, load_user_config
    from anta.core.pipeline import Pipeline
    from anta.core.states import State
    from anta.gui.state import StateMachine, make_pywebview_emitter
    from anta.gui.tray import Tray
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
    session = Session(recorder, pipeline, _notify, on_state=sm.transition, trigger=trigger)

    api = RuntimeApi(sm, trigger, pipeline, session=session)
    window = webview.create_window(
        _TITLE, url=assets.web_url(_APP), js_api=api,
        width=400, height=600, min_size=(360, 520), on_top=True,
    )
    sm.add_listener(make_pywebview_emitter(window))
    api.set_window(window)
    trava.watch_focus(api.show)  # 2a tentativa de abrir -> mostra esta janela

    # pidfile (p/ `anta toggle` do Wayland achar este processo) + SIGUSR1 (main thread)
    pid_path = _pidfile()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")
    install_sigusr1(session)

    env = detect()
    listener = None
    if env.captures_hotkey_in_process:
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys({_to_pynput_hotkey(cfg.hotkey): session.request})
            listener.start()
        except Exception as e:  # noqa: BLE001
            _notify(f"não consegui registrar {cfg.hotkey} in-process ({e}).")

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
                    # a worker NUNCA morre: um erro no toggle vira estado de erro e
                    # volta a 'pronto', em vez de matar a thread (HUD preso p/ sempre).
                    try:
                        session.toggle()
                    except Exception:  # noqa: BLE001
                        import traceback

                        traceback.print_exc()
                        sm.transition(State.ERRO, text="erro inesperado (veja o anta.log)")
                        sm.transition(State.PRONTO)

    threading.Thread(target=worker, daemon=True).start()

    # Bandeja: presenca visivel enquanto a janela esta escondida. Ela ASSINA a
    # maquina de estados (icone + tooltip mudam com o estado) — o icone parado nao
    # dizia nada, e um app residente que ocupa VRAM tem que mostrar o que esta fazendo.
    tray = Tray(api, window, hotkey=cfg.hotkey)
    if tray.start():
        sm.add_listener(tray.on_state)
        _fechar_para_a_bandeja(window, api, tray)
    else:
        # Sem bandeja o X CONTINUA encerrando: esconder a janela sem icone nenhum
        # deixaria a ANTA invisivel de novo, que e exatamente o que queremos evitar.
        _notify("bandeja indisponível neste ambiente — a ANTA fica só na janela.")

    try:
        webview.start()
    finally:
        stop.set()
        trigger.set()  # destrava o worker p/ ele ver o stop
        if listener is not None:
            listener.stop()
        tray.stop()
        pid_path.unlink(missing_ok=True)
        trava.release()


if __name__ == "__main__":
    main()
