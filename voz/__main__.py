"""Entrypoint.

  python -m voz          -> abre o instalador (TUI)
  python -m voz run      -> roda o assistente (daemon quente, push-to-talk)
  python -m voz toggle   -> alterna a gravacao do daemon (usado pelo atalho do SO
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
    from voz.core.config import config_dir

    return config_dir() / "voz.pid"


def _notify(msg: str) -> None:
    """Feedback curto: notify-send no Linux, print sempre."""
    print(f"[voz] {msg}")
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "voz", msg], timeout=5, check=False)
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


def run() -> None:
    from voz.core.config import config_path, load_modes, load_user_config
    from voz.core.capture import Recorder
    from voz.core.pipeline import Pipeline
    from voz.platform.detect import detect
    from voz.platform.hotkey import instructions_for

    cfg = load_user_config()
    modes = load_modes()
    mode = cfg.mode_or_default(modes)

    _notify(f"iniciando modo '{mode.label}' — carregando modelos...")
    pipeline = Pipeline(
        stt_key=mode.stt, llm=mode.llm, mic_device=cfg.mic_device,
        obsidian_vault=cfg.obsidian_vault, tts=cfg.tts,
    )
    try:
        pipeline.warm()
    except Exception as e:  # noqa: BLE001 - nao deixar o boot morrer por causa do STT
        _notify(f"aviso: falha ao carregar STT ({e}). Vou tentar sob demanda.")

    recorder = Recorder(cfg.mic_device)
    recording = {"on": False}

    def toggle() -> None:
        if not recording["on"]:
            try:
                recorder.start()
                recording["on"] = True
                _notify("gravando... (aperte de novo para encerrar)")
            except Exception as e:  # noqa: BLE001
                _notify(f"nao consegui abrir o microfone: {e}")
            return
        # 2a pressao: encerra e roda o pipeline
        recording["on"] = False
        try:
            audio = recorder.stop()
        except Exception as e:  # noqa: BLE001
            _notify(f"erro ao encerrar a gravacao: {e}")
            return
        _notify("processando...")
        try:
            feedback = pipeline.run(audio)
        except Exception as e:  # noqa: BLE001
            _notify(f"erro no pipeline: {e}")
            return
        _notify(feedback)

    # pidfile para o `voz toggle` achar este processo
    pid_path = _pidfile()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    # SIGUSR1 -> dispara o toggle (Wayland/manual e universal em POSIX)
    if hasattr(signal, "SIGUSR1"):
        signal.signal(signal.SIGUSR1, lambda *_: _trigger.set())

    env = detect()
    listener = None
    strategy = env.hotkey_strategy
    if strategy in ("auto_x11", "auto_win"):
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys(
                {_to_pynput_hotkey(cfg.hotkey): _trigger.set}
            )
            listener.start()
            _notify(f"ouvindo atalho {cfg.hotkey}. Fale apos apertar.")
        except Exception as e:  # noqa: BLE001
            _notify(f"nao consegui registrar {cfg.hotkey} in-process ({e}). "
                    f"Use: python -m voz toggle (vincule ao atalho do SO).")
    else:
        _notify(instructions_for(env, "python -m voz toggle"))
        _notify(f"daemon quente. Config em {config_path()}. "
                f"Vincule o atalho do SO a: python -m voz toggle")

    try:
        while True:
            _trigger.wait()
            _trigger.clear()
            toggle()
    except KeyboardInterrupt:
        pass
    finally:
        if listener is not None:
            listener.stop()
        pid_path.unlink(missing_ok=True)


def toggle_daemon() -> None:
    """`voz toggle`: sinaliza o daemon (`voz run`) para alternar a gravacao."""
    pid_path = _pidfile()
    if not pid_path.exists():
        print("[voz] daemon nao esta rodando. Inicie com: python -m voz run")
        sys.exit(1)
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGUSR1)
    except (ValueError, ProcessLookupError, PermissionError, OSError) as e:
        print(f"[voz] nao consegui sinalizar o daemon ({e}). "
              f"Reinicie com: python -m voz run")
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
    from voz.installer.app import main as installer

    installer()


if __name__ == "__main__":
    main()
