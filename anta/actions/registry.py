"""Registro EXPLICITO de handlers: mapa literal tipo-de-acao -> funcao handle.

Sem decorator e sem registro por efeito colateral de import: a tabela abaixo
e greppable e deterministica. Adicionar uma acao = nova classe no schema +
novo arquivo em handlers/ + uma linha aqui. O teste de exaustividade em
tests/test_apps.py garante que nenhuma acao do schema fique sem handler.

Este modulo e uma TABELA pura: nao importa executor (evita ciclo) e nao
define execute() (o dispatch fica no seam documentado, executor.py).
"""
from __future__ import annotations

from typing import Callable

from anta.actions.context import ExecContext
from anta.actions.handlers import (
    abrir_app, adicionar_tarefa, buscar_web, consultar, criar_documento, criar_nota,
    lembrar, responder, resumir,
)
from anta.actions.schema import (
    Acao, AbrirApp, AdicionarTarefa, BuscarWeb, Consultar, CriarDocumento, CriarNota,
    Lembrar, Responder, Resumir,
)

Handler = Callable[[Acao, ExecContext], str]

HANDLERS: dict[type, Handler] = {
    CriarNota: criar_nota.handle,
    CriarDocumento: criar_documento.handle,
    AdicionarTarefa: adicionar_tarefa.handle,
    AbrirApp: abrir_app.handle,
    Responder: responder.handle,
    Lembrar: lembrar.handle,
    Consultar: consultar.handle,
    Resumir: resumir.handle,
    BuscarWeb: buscar_web.handle,
}
