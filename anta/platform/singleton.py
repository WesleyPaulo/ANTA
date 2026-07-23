"""Trava de instancia unica (uma ANTA por vez) + pedido de foco pra que ja roda.

Por que uma trava, e nao um pidfile: o pidfile diz quem *dizia* estar rodando —
se o processo morre no tapa, o arquivo fica la mentindo, e o PID ainda pode ser
reciclado por outro programa. Aqui a garantia e do SO: um lock exclusivo sobre um
arquivo (`flock` no POSIX, `msvcrt.locking` no Windows) que o proprio kernel
libera quando o processo morre — de qualquer jeito que ele morra.

Duas ANTAs ao mesmo tempo nao sao so "duas janelas": sao dois Whispers na RAM,
dois preloads disputando a VRAM, dois `pynput` no mesmo atalho (a tecla dispara
gravacao nos dois) e dois donos do mesmo pidfile. A segunda instancia entao NAO
abre: ela pede foco pra primeira (sentinela `<nome>.focus`, que a viva consome
num watcher) e sai. Assim clicar no atalho de novo "traz a ANTA pra frente" em
vez de duplicar — inclusive no Windows, que nao tem sinais.

`nome` separa as travas: "runtime" (o assistente — `anta app` E `anta run`
compartilham, porque sao o mesmo processo com e sem janela) e "config".
"""
from __future__ import annotations

import os
import sys
import threading
from pathlib import Path

_INTERVALO = 1.0  # s entre checagens da sentinela de foco (um stat; barato)


def _dir() -> Path:
    from anta.core.config import config_dir

    return config_dir()


class SingleInstance:
    """Trava de instancia. Guarde a referencia viva: o lock cai junto com ela."""

    def __init__(self, nome: str) -> None:
        self.nome = nome
        self._fh = None

    # --- caminhos ---
    @property
    def lock_path(self) -> Path:
        return _dir() / f"{self.nome}.lock"

    @property
    def focus_path(self) -> Path:
        return _dir() / f"{self.nome}.focus"

    # --- trava ---
    def acquire(self) -> bool:
        """True se ESTA instancia pegou a trava; False se ja ha outra rodando."""
        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            fh = open(self.lock_path, "a+b")
        except OSError as e:  # sem disco/permissao: nao trave o app por causa da trava
            print(f"[anta] nao consegui criar a trava de instancia ({e}); seguindo.",
                  file=sys.stderr)
            return True
        if not _lock(fh):
            fh.close()
            return False
        self._fh = fh
        try:  # o PID e so diagnostico — quem garante a exclusao e o lock
            fh.truncate(0)
            fh.write(str(os.getpid()).encode("utf-8"))
            fh.flush()
        except OSError:
            pass
        return True

    def release(self) -> None:
        if self._fh is None:
            return
        try:
            _unlock(self._fh)
        except Exception:  # noqa: BLE001
            pass
        try:
            self._fh.close()
        except Exception:  # noqa: BLE001
            pass
        self._fh = None

    # --- foco (IPC minima: um arquivo sentinela) ---
    def signal_existing(self) -> bool:
        """Pede pra instancia viva mostrar a janela. Best-effort."""
        try:
            self.focus_path.parent.mkdir(parents=True, exist_ok=True)
            self.focus_path.write_text(str(os.getpid()), encoding="utf-8")
            return True
        except OSError:
            return False

    def consume_focus(self) -> bool:
        """True (uma vez) se alguem pediu foco desde a ultima checagem."""
        try:
            if not self.focus_path.exists():
                return False
            self.focus_path.unlink(missing_ok=True)
            return True
        except OSError:
            return False

    def watch_focus(self, callback, interval: float = _INTERVALO) -> None:
        """Thread daemon que chama `callback()` quando outra instancia pede foco."""
        self.focus_path.unlink(missing_ok=True)  # limpa pedido velho do boot

        def _loop() -> None:
            while True:
                try:
                    if self.consume_focus():
                        callback()
                except Exception:  # noqa: BLE001 - watcher nunca derruba o app
                    pass
                _sleep(interval)

        threading.Thread(target=_loop, daemon=True, name=f"anta-focus-{self.nome}").start()


def _sleep(segundos: float) -> None:
    import time

    time.sleep(segundos)


def _lock(fh) -> bool:
    """Lock exclusivo NAO-bloqueante. False = outro processo ja tem."""
    if os.name == "nt":
        import msvcrt

        try:
            fh.seek(0)
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
            return True
        except OSError:  # inclui PermissionError (lock de outro processo)
            return False
    try:
        import fcntl

        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        return True
    except (ImportError, OSError):
        return False


def _unlock(fh) -> None:
    if os.name == "nt":
        import msvcrt

        fh.seek(0)
        msvcrt.locking(fh.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
