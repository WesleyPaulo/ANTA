"""Conjunto FECHADO de acoes que o assistente pode executar.

Regra de ouro de seguranca: o LLM NUNCA gera shell livre. Ele escolhe uma
destas acoes e preenche os campos. O executor (executor.py) roda apenas o
que estiver aqui. Nada fora desta lista executa.

Usado com `instructor` para forcar a saida do modelo neste schema.
"""
from __future__ import annotations

from typing import Literal, Union

from pydantic import BaseModel, Field


class CriarNota(BaseModel):
    acao: Literal["criar_nota"] = "criar_nota"
    titulo: str
    conteudo: str


class CriarDocumento(BaseModel):
    acao: Literal["criar_documento"] = "criar_documento"
    titulo: str
    conteudo: str
    formato: Literal["md", "docx", "pdf"] = "md"  # exportado via pandoc


class AdicionarTarefa(BaseModel):
    acao: Literal["adicionar_tarefa"] = "adicionar_tarefa"
    texto: str
    prazo: str | None = None


class AbrirApp(BaseModel):
    acao: Literal["abrir_app"] = "abrir_app"
    nome: str  # validado contra uma whitelist no executor


class Responder(BaseModel):
    acao: Literal["responder"] = "responder"
    texto: str  # apenas fala/mostra, nao altera nada no sistema


Acao = Union[CriarNota, CriarDocumento, AdicionarTarefa, AbrirApp, Responder]


class Decisao(BaseModel):
    """O modelo devolve exatamente uma acao."""
    escolha: Acao = Field(discriminator="acao")
