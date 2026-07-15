"""Helpers compartilhados pelos handlers de acao (nomeacao de arquivo).

Folha do grafo de imports: so stdlib. Promovidos a publicos (sem prefixo _)
porque agora cruzam modulos. (TTS foi para anta/core/tts.py, que precisa de
sounddevice/numpy e nao caberia nesta folha stdlib-only.)
"""
from __future__ import annotations

import re
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
