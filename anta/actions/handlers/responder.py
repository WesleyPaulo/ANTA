"""Handler de Responder: fala via TTS (se ctx.tts) e retorna o texto puro."""
from __future__ import annotations

from anta.actions.context import ExecContext
from anta.actions.schema import Responder


def handle(acao: Responder, ctx: ExecContext) -> str:
    if ctx.tts:
        # Import preguicoso: so puxa piper/sounddevice quando realmente vai falar.
        from anta.core.tts import speak

        speak(acao.texto, ctx.tts_voice, ctx.tts_output)
    return acao.texto
