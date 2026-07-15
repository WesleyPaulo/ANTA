"""Ponto de entrada dos efeitos colaterais: valida uma Acao e a despacha.

Este arquivo continua sendo o seam publico ("todo efeito passa por aqui"),
mas agora e uma fachada fina: cada efeito vive em anta/actions/handlers/
(um arquivo por acao), indexado pela tabela em anta/actions/registry.py, e
abrir_app valida contra a whitelist de anta/actions/apps.py.

Seguranca: nada de shell arbitrario — o LLM so escolhe uma Acao do schema.
"""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.registry import HANDLERS
from anta.actions.schema import Decisao

__all__ = ["ExecContext", "execute"]


def execute(decisao: Decisao, ctx: ExecContext | None = None) -> str:
    """Roda a acao escolhida e devolve uma mensagem curta de feedback."""
    ctx = ctx or ExecContext()
    acao = decisao.escolha
    handler = HANDLERS.get(type(acao))
    if handler is None:
        raise ValueError("acao desconhecida")
    return handler(acao, ctx)
