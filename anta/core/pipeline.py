"""Orquestrador: cola as pecas do fluxo push-to-talk.

    toggle (2a pressao) -> Recorder.stop() -> Transcriber -> Brain -> execute -> feedback
"""
from __future__ import annotations

from anta.actions.executor import ExecContext, execute
from anta.core.brain import Brain
from anta.core.stt import Transcriber


class Pipeline:
    def __init__(
        self,
        stt_key: str,
        llm: str,
        obsidian_vault: str | None = None,
        tts: bool = False,
        tts_voice: str | None = None,
        tts_output: str | None = None,
    ) -> None:
        self.transcriber = Transcriber(stt_key)
        self.brain = Brain(llm)
        self.ctx = ExecContext.from_config(obsidian_vault, tts, tts_voice, tts_output)

    def warm(self) -> None:
        """Carrega o Whisper e fixa o LLM na VRAM no boot para nao pagar o custo
        na 1a fala (STT na CPU; LLM via keep_alive=-1 no Ollama)."""
        self.transcriber.load()
        self.brain.warm()

    def run(self, audio) -> str:
        """Recebe o audio ja gravado e devolve a mensagem de feedback."""
        texto = self.transcriber.transcribe(audio)
        if not texto:
            return "Nao entendi — nada foi transcrito."
        decisao = self.brain.decide(texto)
        return execute(decisao, self.ctx)
