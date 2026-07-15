"""Speech-to-text com faster-whisper (CTranslate2).

Roda na CPU em int8 para deixar a GPU 100% livre para o LLM — decisao de
arquitetura importante em GPUs de 8GB, onde Whisper + LLM na VRAM ao mesmo
tempo estouraria.

O modelo (turbo | large-v3) vem do modo selecionado (modes.yaml -> stt).
"""
from __future__ import annotations

# Dependencia: faster-whisper

_MODEL_MAP = {
    "turbo": "large-v3-turbo",
    "large-v3": "large-v3",
}


class Transcriber:
    """
    TODO(claude-code):
      from faster_whisper import WhisperModel
      self.model = WhisperModel(_MODEL_MAP[stt_key],
                                device="cpu", compute_type="int8")
      def transcribe(audio) -> str:
          segments, _ = self.model.transcribe(audio, language="pt")
          return " ".join(s.text for s in segments).strip()
    Observacao PT-BR: large-v3 acerta muito mais nomes proprios e jargao
    tecnico que os modelos menores; 'turbo' e o trade-off de velocidade.
    """

    def __init__(self, stt_key: str) -> None:
        self.stt_key = stt_key

    def transcribe(self, audio) -> str:
        raise NotImplementedError
