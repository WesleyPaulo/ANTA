"""Handler de BuscarWeb: busca na internet (OPT-IN) + sintese ancorada pelo LLM.

So funciona com web=true (o Pipeline injeta ctx.web_search; senao fica None). O EFEITO
de leitura (baixar os resultados) vive aqui; a sintese e do LLM via ctx.answer.
"""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.schema import BuscarWeb


def handle(acao: BuscarWeb, ctx: ExecContext) -> str:
    if ctx.web_search is None:
        return "Busca na web desativada. Ligue com web = true na config (rompe o offline)."
    resultados = ctx.web_search(acao.consulta)
    if not resultados:
        return "Não consegui buscar na web agora."
    from anta.core.websearch import format_context, sources

    contexto = format_context(resultados)
    # answer_web (prompt BUSCA), nao answer (prompt das NOTAS): com o prompt do RAG, uma
    # busca que trouxe 3 paginas uteis virava "Nao encontrou." — e as fontes apareciam
    # logo abaixo, contradizendo a resposta. Cai em answer/contexto se nao houver.
    sintetizar = ctx.answer_web or ctx.answer
    resposta = sintetizar(acao.consulta, contexto) if sintetizar else contexto
    if ctx.tts:
        from anta.core.tts import speak  # import preguicoso, como em responder.py

        speak(resposta, ctx.tts_voice, ctx.tts_output)
    fontes = sources(resultados)
    return f"{resposta}\n\nFontes: {fontes}" if fontes else resposta
