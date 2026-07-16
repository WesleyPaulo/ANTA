"""Handler de Consultar: busca RAG nas notas + sintese ancorada pelo LLM.

O EFEITO de leitura (recuperar trechos do indice) vive aqui; a chamada ao LLM
acontece em Brain.answer, apenas INVOCADA via o callable ctx.answer injetado pelo
Pipeline — nenhum client LLM e construido no handler.
"""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.schema import Consultar


def handle(acao: Consultar, ctx: ExecContext) -> str:
    if ctx.rag is None:
        return "Busca em notas desativada (rag=false)."
    chunks = ctx.rag.query(acao.pergunta)
    contexto = "\n\n".join(c.texto for c in chunks)
    if not contexto:
        resposta = "Nao encontrei nada nas suas notas sobre isso."
    elif ctx.answer is None:
        resposta = contexto  # sem LLM ligado: devolve os trechos crus
    else:
        resposta = ctx.answer(acao.pergunta, contexto)
    if ctx.tts:
        from anta.core.tts import speak  # import preguicoso, como em responder.py

        speak(resposta, ctx.tts_voice, ctx.tts_output)
    return resposta
