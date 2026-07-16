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


class Lembrar(BaseModel):
    acao: Literal["lembrar"] = "lembrar"
    fato: str  # fato duravel a memorizar quando o usuario pede ("lembre que...")


class Consultar(BaseModel):
    acao: Literal["consultar"] = "consultar"
    pergunta: str  # pergunta sobre o que o usuario anotou/pediu p/ lembrar (busca RAG)


class Resumir(BaseModel):
    # Resumo da ATIVIDADE do usuario num periodo de tempo. Resumo de um ASSUNTO/tema
    # (das notas) e 'consultar', nao 'resumir' — a desambiguacao vive no prompt decide.
    acao: Literal["resumir"] = "resumir"
    periodo: Literal["dia", "semana", "mes"] = "dia"  # janela de tempo do resumo


class BuscarWeb(BaseModel):
    # OPT-IN (so quando web=true): busca na internet. Rompe o offline da ANTA.
    acao: Literal["buscar_web"] = "buscar_web"
    consulta: str  # o que buscar na web


Acao = Union[
    CriarNota, CriarDocumento, AdicionarTarefa, AbrirApp, Responder, Lembrar, Consultar,
    Resumir, BuscarWeb,
]


class Decisao(BaseModel):
    """O modelo devolve exatamente uma acao, e opcionalmente um fato a memorizar."""
    escolha: Acao = Field(discriminator="acao")
    # Canal AUTOMATICO de memoria: preenchido so quando ha um fato duravel/reutilizavel
    # sobre o usuario a lembrar junto da acao (senao None). Nao repete o comando.
    memoria: str | None = None

    @classmethod
    def model_json_schema(cls, *args, **kwargs):  # type: ignore[override]
        """Schema com `acao` sempre em `required` — o discriminador nao e opcional.

        Ter default (`acao: Literal["resumir"] = "resumir"`) e otimo em Python
        (`Responder(texto="ok")`), mas o pydantic entao deixa `acao` FORA de `required`.
        O Ollama compila esse schema numa gramatica GBNF, e campo fora de `required`
        vira opcional na gramatica: o modelo podia omitir o discriminador — e `Resumir`,
        cujos campos tem todos default, virava o valido-e-inutil `{"escolha": {}}`.
        Ai o pydantic nao consegue discriminar e a tentativa se perde.

        Corrigimos no schema em vez de tirar os defaults pra nao poluir todas as
        construcoes em Python com `acao="..."` redundante.
        """
        schema = super().model_json_schema(*args, **kwargs)
        for definicao in schema.get("$defs", {}).values():
            if "acao" in definicao.get("properties", {}):
                obrigatorios = definicao.setdefault("required", [])
                if "acao" not in obrigatorios:
                    obrigatorios.insert(0, "acao")
        return schema
