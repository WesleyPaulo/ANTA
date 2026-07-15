"""Handler de Responder: fala via TTS (se ctx.tts) e retorna o texto puro."""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.helpers import speak
from anta.actions.schema import Responder


def handle(acao: Responder, ctx: ExecContext) -> str:
    if ctx.tts:
        speak(acao.texto)
    return acao.texto
