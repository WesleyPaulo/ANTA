"""Helpers compartilhados pelos handlers de acao (nomeacao de arquivo e TTS).

Folha do grafo de imports: so stdlib. Promovidos a publicos (sem prefixo _)
porque agora cruzam modulos.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def slug(texto: str) -> str:
    """Titulo -> nome de arquivo seguro."""
    s = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "nota"


def unique_path(directory: Path, stem: str, ext: str) -> Path:
    """Evita sobrescrever: nota.md, nota-2.md, ..."""
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{stem}.{ext}"
    n = 2
    while p.exists():
        p = directory / f"{stem}-{n}.{ext}"
        n += 1
    return p


def note_body(titulo: str, conteudo: str) -> str:
    """Corpo Markdown de uma nota/documento (a unica formatacao compartilhada)."""
    return f"# {titulo}\n\n{conteudo}\n"


def speak(texto: str) -> None:
    """TTS best-effort via Piper. No-op silencioso se Piper nao existir."""
    if shutil.which("piper") is None:
        return
    try:
        subprocess.run(["piper", "--output_file", "-"], input=texto.encode(),
                       capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        pass
