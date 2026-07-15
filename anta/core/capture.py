"""Captura de audio do MICROFONE. Cross-platform via sounddevice.

MVP: SO microfone. Nada de audio do sistema, sink virtual ou loopback.
Isso mantem um unico caminho de codigo em Windows e Linux e elimina o
risco de feedback loop (gravar o proprio TTS).
"""
from __future__ import annotations

import threading

import numpy as np

# Dependencias: sounddevice, numpy

SAMPLE_RATE = 16000       # Whisper espera 16kHz mono
MAX_SECONDS = 60          # corte de seguranca: atalho esquecido apertado
_MAX_SAMPLES = SAMPLE_RATE * MAX_SECONDS


def _input_devices():
    """(indice_global, device) apenas dos devices de ENTRADA (microfones)."""
    import sounddevice as sd

    for idx, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) > 0:
            yield idx, d


def list_input_devices() -> list[dict]:
    """Retorna os microfones disponiveis para o usuario escolher no instalador.

    Guardar o NOME do device escolhido na config (nao o indice/default),
    para nao quebrar quando um headset USB mudar o default no meio do dia.
    """
    return [dict(d) for _, d in _input_devices()]


def _resolve_device(device_name: str | None) -> int | None:
    """Nome do device -> indice de entrada. None (default do sistema) se o
    nome estiver vazio ou nao existir mais (ex.: headset desconectado)."""
    if not device_name:
        return None
    import sounddevice as sd

    target = device_name.strip().lower()
    fallback = None
    for idx, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) <= 0:
            continue
        name = d["name"].lower()
        if name == target:
            return idx                      # nome exato vence
        if fallback is None and target in name:
            fallback = idx                  # tolera mudanca de sufixo (headset renomeado)
    return fallback  # None se o nome sumiu -> cai no default em vez de quebrar


class Recorder:
    """Gravador em toggle: start() abre um stream para um buffer,
    stop() encerra e devolve o audio (np.ndarray float32 mono 16kHz).

    O device e resolvido por NOME (config.mic_device); cai no default so
    se None. MAX_SECONDS e um limite duro aplicado no proprio callback,
    para nao acumular memoria se o atalho ficar preso.
    """

    def __init__(self, device_name: str | None = None) -> None:
        self.device_name = device_name
        self._stream = None
        self._chunks: list[np.ndarray] = []
        self._lock = threading.Lock()
        self._total = 0
        self.truncated = False

    def _callback(self, indata, frames, time_info, status) -> None:  # noqa: ARG002
        with self._lock:
            if self._total >= _MAX_SAMPLES:
                self.truncated = True
                return
            self._chunks.append(indata.copy())
            self._total += frames

    def _close_stream(self) -> None:
        """Encerra e descarta o stream atual, se houver. Idempotente."""
        if self._stream is not None:
            self._stream.stop()
            self._stream.close()
            self._stream = None

    def start(self) -> None:
        import sounddevice as sd

        self._close_stream()  # imune a start() repetido / stream orfao apos erro
        with self._lock:
            self._chunks = []
            self._total = 0
            self.truncated = False
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            device=_resolve_device(self.device_name),
            callback=self._callback,
        )
        self._stream.start()

    def stop(self) -> np.ndarray:
        self._close_stream()
        with self._lock:
            chunks, self._chunks = self._chunks, []
        if not chunks:
            return np.zeros(0, dtype=np.float32)
        audio = np.concatenate(chunks, axis=0).reshape(-1).astype(np.float32)
        return audio[:_MAX_SAMPLES]
