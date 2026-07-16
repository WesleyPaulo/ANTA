"""Helpers compartilhados pelos handlers de acao (nomeacao de arquivo).

Folha do grafo de imports: so stdlib. Promovidos a publicos (sem prefixo _)
porque agora cruzam modulos. (TTS foi para anta/core/tts.py, que precisa de
sounddevice/numpy e nao caberia nesta folha stdlib-only.)
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta
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


def write_memory_note(vault: Path, texto: str) -> Path:
    """Grava um fato de memoria como .md unico em <vault>/memoria/.

    Reusa a convencao de nomeacao das notas (slug + unique_path) para que o RAG
    indexe a memoria junto do resto do vault (indice unico). NAO indexa aqui: a
    indexacao e responsabilidade do chamador (handler/pipeline) via ctx.rag —
    este modulo e folha stdlib-only e nao conhece o RAG."""
    stem = slug(texto)[:60].rstrip("-") or "memoria"
    path = unique_path(vault / "memoria", stem, "md")
    path.write_text(note_body("Memoria", texto), encoding="utf-8")
    return path


# --- Resumo de atividade (acao 'resumir') ---
# Pastas do vault que NAO contam como "atividade produzida" (evita resumir resumos).
_TAREFA_TS = re.compile(r"<!--\s*(\d{4}-\d{2}-\d{2})\s+(\d{2}:\d{2})")


def window_start(periodo: str, now: datetime) -> datetime:
    """Inicio da janela do resumo: dia=hoje (meia-noite), semana=7 dias, mes=30 dias."""
    if periodo == "dia":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if periodo == "semana":
        return now - timedelta(days=7)
    return now - timedelta(days=30)  # mes (default seguro)


def _recent(fp: Path, since: datetime) -> bool:
    try:
        return datetime.fromtimestamp(fp.stat().st_mtime) >= since
    except OSError:
        return False


def gather_activity(vault: Path, since: datetime) -> str:
    """Junta o que o usuario produziu desde `since`: notas/documentos (por mtime),
    memoria (por mtime) e tarefas (por timestamp da linha em tarefas.md). Ignora
    'resumos/' (nao resume resumos). Devolve um bloco de texto para o LLM sintetizar."""
    vault = Path(vault)
    blocos: list[str] = []
    for fp in sorted(vault.glob("*.md")):
        if fp.name == "tarefas.md":
            continue  # tarefas entram por timestamp de linha, abaixo
        if _recent(fp, since):
            corpo = fp.read_text(encoding="utf-8", errors="ignore").strip()
            blocos.append(f"[nota] {fp.stem}\n{corpo}")
    mem = vault / "memoria"
    if mem.exists():
        for fp in sorted(mem.glob("*.md")):
            if _recent(fp, since):
                blocos.append(f"[memoria] {fp.read_text(encoding='utf-8', errors='ignore').strip()}")
    tarefas = vault / "tarefas.md"
    if tarefas.exists():
        for linha in tarefas.read_text(encoding="utf-8", errors="ignore").splitlines():
            m = _TAREFA_TS.search(linha)
            if not m:
                continue
            try:
                ts = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%Y-%m-%d %H:%M")
            except ValueError:
                continue
            if ts >= since:
                blocos.append(f"[tarefa] {linha.strip()}")
    return "\n\n".join(blocos)


def write_summary_note(vault: Path, periodo: str, now: datetime, texto: str) -> Path:
    """Salva o resumo em <vault>/resumos/ (o RAG indexa essa pasta -> pesquisavel)."""
    stem = f"{now.strftime('%Y-%m-%d')}-{periodo}"
    path = unique_path(Path(vault) / "resumos", stem, "md")
    titulo = f"Resumo ({periodo}) — {now.strftime('%Y-%m-%d')}"
    path.write_text(note_body(titulo, texto), encoding="utf-8")
    return path
