"""Handler de Lembrar: grava um fato de memoria em <vault>/memoria/.

Nao indexa aqui: o RAG reconcilia o vault no momento da consulta (RAG.query), entao a
nota nova e encontrada na proxima pergunta sem acoplar este handler ao indexador nem
arriscar derrubar o comando por uma falha de indexacao.
"""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.helpers import write_memory_note
from anta.actions.schema import Lembrar


def handle(acao: Lembrar, ctx: ExecContext) -> str:
    write_memory_note(ctx.vault, acao.fato)
    return f"Vou lembrar: {acao.fato}"
