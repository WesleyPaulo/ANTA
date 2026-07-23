"""Deteccao de RAM e disco para o Configurador.

O guia de frontend assume que a deteccao entrega "GPU/RAM/VRAM/disco", mas o
codigo so tinha GPU/VRAM (`anta/installer/hardware.py`). Aqui entram RAM e disco,
para o Configurador avisar cedo se falta memoria ou espaco para os modelos (GBs).

Tudo em GiB (base 1024), para casar com a VRAM (nvidia-smi reporta MiB, e
`hardware.best_vram_gb` divide por 1024). Tudo best-effort: falha -> 0.0, nunca
derruba a deteccao (mesma filosofia de `best_vram_gb`, que devolve 0.0 sem NVIDIA).
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

_GIB = 1024 ** 3


def ram_gb() -> float:
    """RAM fisica total em GiB (0.0 se nao der pra medir).

    Primario: psutil (multiplataforma). Fallback: sysconf no POSIX / ctypes no
    Windows — assim a deteccao funciona mesmo antes de `psutil` estar instalado."""
    try:
        import psutil  # dep nova; import preguicoso p/ nao quebrar sem ela

        return round(psutil.virtual_memory().total / _GIB, 1)
    except Exception:  # noqa: BLE001 - psutil ausente ou falho -> tenta stdlib
        return _ram_gb_stdlib()


def _ram_gb_stdlib() -> float:
    """RAM total via stdlib, sem psutil. Best-effort por SO."""
    try:
        if hasattr(os, "sysconf") and "SC_PHYS_PAGES" in os.sysconf_names:
            total = os.sysconf("SC_PHYS_PAGES") * os.sysconf("SC_PAGE_SIZE")
            return round(total / _GIB, 1)
        if os.name == "nt":
            import ctypes

            class _MemStatus(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong),
                    ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong),
                    ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong),
                    ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong),
                    ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = _MemStatus()
            stat.dwLength = ctypes.sizeof(_MemStatus)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / _GIB, 1)
    except Exception:  # noqa: BLE001
        pass
    return 0.0


def process_ram_gb() -> float | None:
    """RAM residente (RSS) DESTE processo em GiB, ou None se nao der pra medir.

    E o numero que o HUD mostra como "RAM da ANTA": o Whisper e o embedder ficam
    aqui dentro (por principio, na CPU). Usa psutil, que ja e dependencia declarada
    (o `ram_gb` acima tem fallback stdlib porque roda no Configurador, que pode abrir
    antes das deps completas; o HUD nao — se chegou aqui, psutil existe). None se
    faltar: 'nao sei' e honesto, chutar um numero de memoria nao."""
    try:
        import psutil

        return round(psutil.Process().memory_info().rss / _GIB, 2)
    except Exception:  # noqa: BLE001 - psutil ausente/sem permissao
        return None


def disk_free_gb(path: str | Path | None = None) -> float:
    """Espaco LIVRE em disco (GiB) na particao de `path` (default: home).

    Interessa o livre, nao o total: os modelos (varios GB) vao para o disco do
    usuario, e o Configurador deve avisar antes de um download falhar sem espaco."""
    target = Path(path) if path is not None else Path.home()
    try:
        return round(shutil.disk_usage(str(target)).free / _GIB, 1)
    except Exception:  # noqa: BLE001 - caminho invalido/inacessivel
        return 0.0
