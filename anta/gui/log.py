"""Log em arquivo para o app de JANELA (PyInstaller --noconsole).

Num exe windowed `sys.stdout`/`sys.stderr` sao **None**: qualquer `print()` ou
`traceback.print_exc()` estoura (`AttributeError: 'NoneType' object has no attribute
'write'`). No runtime isso e fatal — mata a worker thread no meio do pipeline e o HUD
fica preso em 'processando' pra sempre.

`redirect_std_to_log()` aponta os dois streams para `config_dir()/anta.log`. Isso
(1) conserta o crash e (2) deixa o traceback VISIVEL — app de janela nao tem console,
entao sem isso todo erro e silencioso (a armadilha classica do Windows).

No dev / com console, os streams existem -> no-op (nao mexe em nada).
"""
from __future__ import annotations

import sys


def log_path():
    from anta.core.config import config_dir

    return config_dir() / "anta.log"


def redirect_std_to_log() -> None:
    """Se stdout/stderr forem None (app de janela), aponta-os pro anta.log."""
    if sys.stdout is not None and sys.stderr is not None:
        return  # console/dev: nao mexe

    stream = _open_log()
    if sys.stdout is None:
        sys.stdout = stream
    if sys.stderr is None:
        sys.stderr = stream


def _open_log():
    """Abre o anta.log (line-buffered) ou, em ultimo caso, um stream nulo — o
    importante e NUNCA deixar stdout/stderr como None (senao print/traceback crasham)."""
    try:
        p = log_path()
        p.parent.mkdir(parents=True, exist_ok=True)
        return open(p, "a", encoding="utf-8", errors="replace", buffering=1)
    except Exception:  # noqa: BLE001 - sem disco/permissao: cai no stream nulo
        import io

        return io.StringIO()
