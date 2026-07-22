"""Captura de audio do MICROFONE. Cross-platform via sounddevice.

MVP: SO microfone. Nada de audio do sistema, sink virtual ou loopback.
Isso mantem um unico caminho de codigo em Windows e Linux e elimina o
risco de feedback loop (gravar o proprio TTS).
"""
from __future__ import annotations

import os
import threading

import numpy as np

# Dependencias: sounddevice, numpy

SAMPLE_RATE = 16000       # Whisper espera 16kHz mono
MAX_SECONDS = 60          # corte de seguranca: atalho esquecido apertado
_MAX_SAMPLES = SAMPLE_RATE * MAX_SECONDS
# Piso: abaixo disso nao ha fala, e o Whisper ALUCINA em audio curto/silencio (devolve
# frases plausiveis que nunca foram ditas). Melhor dizer "curto demais" do que mandar
# uma alucinacao pro LLM e responder qualquer coisa com confianca.
MIN_SECONDS = 0.4
# Pico minimo (float32 em [-1,1]) para considerar que ha FALA. Fala real chega
# facil a 0.1+; ruido de sala fica na casa de 0.001-0.01; mic bloqueado/mudo da 0.0
# exato. Mesma razao do MIN_SECONDS: silencio faz o Whisper inventar ("E ai", "Obrigado").
SILENCE_PEAK = 0.01


def audio_level(audio) -> tuple[float, float]:
    """(pico, rms) do audio. Usado pro guard de silencio e pelo `anta mic`."""
    import numpy as np

    if audio is None or len(audio) == 0:
        return 0.0, 0.0
    return float(np.abs(audio).max()), float(np.sqrt(np.mean(np.square(audio))))


def _preferred_hostapi() -> int | None:
    """No Windows, prefere o host API WASAPI; fora dele, None (sem filtro).

    O PortAudio lista CADA device uma vez POR host API (MME, DirectSound, WASAPI,
    WDM-KS): o mesmo microfone aparece 3-4x, e o MME ainda TRUNCA o nome em 31 chars
    ('...WCI108' vs '...WCI1080P'). Filtrar pelo WASAPI da uma lista limpa (nomes
    completos, cada device uma vez)."""
    if os.name != "nt":
        return None
    try:
        import sounddevice as sd

        for i, ha in enumerate(sd.query_hostapis()):
            if "WASAPI" in ha.get("name", ""):
                return i
    except Exception:  # noqa: BLE001 - sem WASAPI/host apis -> cai no fallback
        pass
    return None


def _list_devices(channels_key: str) -> list[dict]:
    """Devices com `channels_key > 0`, DEDUPLICADOS por nome. No Windows prefere o
    WASAPI (ver _preferred_hostapi); fora dele, deduplica por nome (Linux/mac raramente
    repetem, mas o dedup e inofensivo)."""
    import sounddevice as sd

    devices = list(sd.query_devices())
    prefer = _preferred_hostapi()
    seen: set[str] = set()
    out: list[dict] = []

    def collect(items) -> None:
        for d in items:
            if d.get(channels_key, 0) <= 0:
                continue
            key = d["name"].strip().lower()
            if key in seen:
                continue
            seen.add(key)
            out.append(dict(d))

    if prefer is not None:
        collect(d for d in devices if d.get("hostapi") == prefer)
    if not out:  # fora do Windows, ou WASAPI vazio: todos, deduplicados por nome
        collect(devices)
    return out


def list_input_devices() -> list[dict]:
    """Microfones para o usuario escolher (deduplicados). Guardar o NOME na config
    (nao o indice/default), para nao quebrar quando um headset USB mudar o default."""
    return _list_devices("max_input_channels")


def list_output_devices() -> list[dict]:
    """Devices de SAIDA (deduplicados) para a saida do TTS. Mesmo motivo do de entrada:
    guardar o NOME. A resolucao nome->indice ja existe em tts._resolve_output."""
    return _list_devices("max_output_channels")


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
