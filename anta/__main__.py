"""Entrypoint.

  python -m anta          -> abre o instalador (TUI)
  python -m anta run      -> roda o assistente (daemon quente, push-to-talk)
  python -m anta toggle   -> alterna a gravacao do daemon (usado pelo atalho do SO
                            no Wayland, onde apps nao capturam teclas globais)
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading

# Evento disparado por qualquer fonte de atalho (pynput ou SIGUSR1).
_trigger = threading.Event()


def _pidfile():
    from anta.core.config import config_dir

    return config_dir() / "anta.pid"


def _notify(msg: str) -> None:
    """Feedback curto: notify-send no Linux, print sempre."""
    print(f"[anta] {msg}")
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "anta", msg], timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            pass


def _to_pynput_hotkey(hotkey: str) -> str:
    """'ctrl+alt+space' -> '<ctrl>+<alt>+<space>' (formato do pynput)."""
    special = {"ctrl", "alt", "shift", "cmd", "super", "win", "space",
               "enter", "tab", "esc", "escape", "up", "down", "left", "right"}
    alias = {"super": "cmd", "win": "cmd", "escape": "esc"}
    parts = []
    for raw in hotkey.split("+"):
        tok = raw.strip().lower()
        if tok in special:
            parts.append(f"<{alias.get(tok, tok)}>")
        else:
            parts.append(tok)
    return "+".join(parts)


class Session:
    """Maquina de estado do push-to-talk: alterna gravar/encerrar e roda o
    pipeline ao encerrar. Isolada de run() (que so faz wiring de ciclo de vida)
    para ser testavel com fakes de recorder/pipeline/notify."""

    def __init__(self, recorder, pipeline, notify=_notify) -> None:
        self.recorder = recorder
        self.pipeline = pipeline
        self.notify = notify
        self.on = False

    def toggle(self) -> None:
        if not self.on:
            try:
                self.recorder.start()
                self.on = True
                self.notify("gravando... (aperte de novo para encerrar)")
            except Exception as e:  # noqa: BLE001
                self.notify(f"nao consegui abrir o microfone: {e}")
            return
        # 2a pressao: encerra e roda o pipeline
        self.on = False
        try:
            audio = self.recorder.stop()
        except Exception as e:  # noqa: BLE001
            self.notify(f"erro ao encerrar a gravacao: {e}")
            return
        self.notify("processando...")
        try:
            feedback = self.pipeline.run(audio)
        except Exception as e:  # noqa: BLE001
            self.notify(f"erro no pipeline: {e}")
            return
        self.notify(feedback)


def run() -> None:
    from anta.core.config import config_path, load_modes, load_user_config
    from anta.core.capture import Recorder
    from anta.core.pipeline import Pipeline
    from anta.platform.detect import detect
    from anta.platform.hotkey import default_command, instructions_for

    cfg = load_user_config()
    modes = load_modes()
    mode = cfg.mode_or_default(modes)

    _notify(f"iniciando modo '{mode.label}' — carregando modelos...")
    pipeline = Pipeline(
        stt_key=mode.stt, llm=mode.llm,
        obsidian_vault=cfg.obsidian_vault, tts=cfg.tts,
        tts_voice=cfg.tts_voice, tts_output=cfg.tts_output,
        rag=cfg.rag, web=cfg.web, web_engine=cfg.web_engine,
        web_searxng_url=cfg.web_searxng_url,
    )
    try:
        pipeline.warm()
    except Exception as e:  # noqa: BLE001 - nao deixar o boot morrer por causa do STT
        _notify(f"aviso: falha ao carregar STT ({e}). Vou tentar sob demanda.")

    recorder = Recorder(cfg.mic_device)
    session = Session(recorder, pipeline, _notify)

    # pidfile para o `anta toggle` achar este processo
    pid_path = _pidfile()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    # SIGUSR1 -> dispara o toggle (Wayland/manual e universal em POSIX)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, lambda *_: _trigger.set())

    env = detect()
    listener = None
    toggle_cmd = f"{default_command()} toggle"
    if env.captures_hotkey_in_process:
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys(
                {_to_pynput_hotkey(cfg.hotkey): _trigger.set}
            )
            listener.start()
            _notify(f"ouvindo atalho {cfg.hotkey}. Fale apos apertar.")
        except Exception as e:  # noqa: BLE001
            _notify(f"nao consegui registrar {cfg.hotkey} in-process ({e}). "
                    f"Use: {toggle_cmd} (vincule ao atalho do SO).")
    else:
        _notify(instructions_for(env, toggle_cmd))
        _notify(f"daemon quente. Config em {config_path()}. "
                f"Vincule o atalho do SO a: {toggle_cmd}")

    try:
        while True:
            _trigger.wait()
            _trigger.clear()
            session.toggle()
    except KeyboardInterrupt:
        pass
    finally:
        if listener is not None:
            listener.stop()
        pid_path.unlink(missing_ok=True)


def toggle_daemon() -> None:
    """`anta toggle`: sinaliza o daemon (`anta run`) para alternar a gravacao."""
    from anta.platform.hotkey import default_command

    if not hasattr(signal, "SIGUSR1"):  # Windows
        print("[anta] 'anta toggle' e para Linux (Wayland/manual). No Windows o "
              "atalho e capturado in-process pelo proprio 'anta run'.")
        sys.exit(1)
    pid_path = _pidfile()
    if not pid_path.exists():
        print(f"[anta] daemon nao esta rodando. Inicie com: {default_command()} run")
        sys.exit(1)
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGUSR1)
    except (ValueError, ProcessLookupError, PermissionError, OSError) as e:
        print(f"[anta] nao consegui sinalizar o daemon ({e}). "
              f"Reinicie com: {default_command()} run")
        pid_path.unlink(missing_ok=True)
        sys.exit(1)


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "run":
        run()
        return
    if arg == "toggle":
        toggle_daemon()
        return
    from anta.installer.app import main as installer

    installer()


if __name__ == "__main__":
    main()
