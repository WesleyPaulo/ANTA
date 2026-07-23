"""Handler de Resumir: sintetiza a atividade do usuario no periodo e salva em resumos/.

O EFEITO (varrer o vault por atividade recente, salvar o resumo) vive aqui; a chamada
ao LLM e feita por Brain.summarize, invocada via o callable ctx.summarize injetado pelo
Pipeline — nenhum client LLM e construido no handler.
"""
from __future__ import annotations

from datetime import datetime

from anta.actions.context import ExecContext
from anta.actions.helpers import gather_activity, window_start, write_summary_note
from anta.actions.schema import Resumir


def handle(acao: Resumir, ctx: ExecContext) -> str:
    now = datetime.now()
    material = gather_activity(ctx.vault, window_start(acao.periodo, now))
    if not material:
        return f"Não há nada registrado no período ({acao.periodo})."
    resumo = ctx.summarize(acao.periodo, material) if ctx.summarize else material
    write_summary_note(ctx.vault, acao.periodo, now, resumo)  # salvo em resumos/ (indexado)
    if ctx.tts:
        from anta.core.tts import speak  # import preguicoso, como em responder.py

        speak(resumo, ctx.tts_voice, ctx.tts_output)
    return resumo
