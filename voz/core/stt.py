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
    """Transcreve audio PT-BR com faster-whisper na CPU (int8).

    O modelo e carregado preguicosamente (load()) para nao baixar ~1GB so
    de instanciar — o runtime chama load() no boot para deixa-lo quente.

    PT-BR: large-v3 acerta muito mais nomes proprios e jargao tecnico que os
    modelos menores; 'turbo' e o trade-off de velocidade.
    """

    def __init__(self, stt_key: str) -> None:
        self.stt_key = stt_key
        self.model_name = _MODEL_MAP.get(stt_key, stt_key)
        self._model = None

    def load(self):
        """Carrega (e baixa, se preciso) o modelo. Idempotente."""
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name, device="cpu", compute_type="int8"
            )
        return self._model

    def transcribe(self, audio) -> str:
        if audio is None or len(audio) == 0:
            return ""
        segments, _ = self.load().transcribe(audio, language="pt")
        return " ".join(s.text.strip() for s in segments).strip()
