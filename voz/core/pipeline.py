"""Orquestrador: cola as pecas do fluxo push-to-talk.

    toggle (2a pressao) -> Recorder.stop() -> Transcriber -> Brain -> execute -> feedback
"""
from __future__ import annotations

from voz.actions.executor import execute
from voz.core.brain import Brain
from voz.core.stt import Transcriber


class Pipeline:
    def __init__(self, stt_key: str, llm: str, mic_device: str | None) -> None:
        self.transcriber = Transcriber(stt_key)
        self.brain = Brain(llm)
        self.mic_device = mic_device

    def run(self, audio) -> str:
        """Recebe o audio ja gravado e devolve a mensagem de feedback.

        TODO(claude-code):
          texto = self.transcriber.transcribe(audio)
          decisao = self.brain.decide(texto)
          return execute(decisao)
        """
        raise NotImplementedError
