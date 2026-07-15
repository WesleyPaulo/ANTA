"""Handler de CriarNota: escreve uma nota .md unica no vault."""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.helpers import slug, unique_path
from anta.actions.schema import CriarNota


def handle(acao: CriarNota, ctx: ExecContext) -> str:
    path = unique_path(ctx.vault, slug(acao.titulo), "md")
    path.write_text(f"# {acao.titulo}\n\n{acao.conteudo}\n", encoding="utf-8")
    return f"Nota criada: {path.name}"
