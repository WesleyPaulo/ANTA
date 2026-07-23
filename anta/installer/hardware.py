"""Deteccao de VRAM. Cross-platform (Windows + Linux) via nvidia-smi,
com fallback opcional para pynvml.

Retorna VRAM total em GB para que o instalador pinte cada modo:
  verde  = cabe            (vram_disponivel >= modo.vram_gb)
  amarelo= cabe apertado   (dentro de ~1GB do limite)
  vermelho= nao roda
"""
from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass


@dataclass
class GPU:
    name: str
    vram_gb: float


def _via_nvidia_smi() -> list[GPU]:
    if shutil.which("nvidia-smi") is None:
        return []
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=name,memory.total",
             "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return []
    gpus: list[GPU] = []
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        name, mib = (p.strip() for p in line.split(","))
        gpus.append(GPU(name=name, vram_gb=round(int(mib) / 1024, 1)))
    return gpus


def _via_pynvml() -> list[GPU]:
    try:
        import pynvml  # type: ignore
        pynvml.nvmlInit()
        gpus = []
        for i in range(pynvml.nvmlDeviceGetCount()):
            h = pynvml.nvmlDeviceGetHandleByIndex(i)
            name = pynvml.nvmlDeviceGetName(h)
            mem = pynvml.nvmlDeviceGetMemoryInfo(h)
            gpus.append(GPU(name=name, vram_gb=round(mem.total / 1024**3, 1)))
        pynvml.nvmlShutdown()
        return gpus
    except Exception:
        return []


def detect_gpus() -> list[GPU]:
    return _via_nvidia_smi() or _via_pynvml()


def vram_usage_gb() -> tuple[float | None, float | None]:
    """(VRAM em uso, VRAM total) em GiB da GPU mais capaz, ou (None, None).

    E a ocupacao da PLACA, nao a de um processo: o LLM vive dentro do Ollama, que
    e outro processo — medir so a ANTA daria ~0 e mentiria sobre o custo real. Sem
    NVIDIA (ou sem nvidia-smi) devolve (None, None) e o HUD simplesmente omite."""
    if shutil.which("nvidia-smi") is None:
        return None, None
    try:
        out = subprocess.check_output(
            ["nvidia-smi",
             "--query-gpu=memory.used,memory.total",
             "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        )
    except (subprocess.SubprocessError, OSError):
        return None, None
    melhor: tuple[float, float] | None = None
    for line in out.strip().splitlines():
        if not line.strip():
            continue
        try:
            usada, total = (float(p.strip()) for p in line.split(",")[:2])
        except ValueError:
            continue
        if melhor is None or total > melhor[1]:
            melhor = (round(usada / 1024, 1), round(total / 1024, 1))
    return melhor if melhor is not None else (None, None)


def best_vram_gb() -> float:
    """VRAM da GPU mais capaz. 0.0 se nenhuma GPU NVIDIA for encontrada."""
    gpus = detect_gpus()
    return max((g.vram_gb for g in gpus), default=0.0)


def status_for(mode_vram_gb: float, available_gb: float) -> str:
    """verde | amarelo | vermelho para um modo dado a VRAM disponivel."""
    if available_gb >= mode_vram_gb:
        return "verde"
    if available_gb >= mode_vram_gb - 1.0:
        return "amarelo"
    return "vermelho"


if __name__ == "__main__":
    for g in detect_gpus():
        print(f"{g.name}: {g.vram_gb} GB")
    print("melhor:", best_vram_gb(), "GB")
