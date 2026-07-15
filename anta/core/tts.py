"""Sintese de voz (TTS) via Piper, reproduzida pelo sounddevice.

Isolado do resto do core e importado preguicosamente pelo handler `responder`
so quando ctx.tts esta ligado. Best-effort: se o pacote `piper` ou a voz nao
existirem, e um no-op silencioso (o assistente ainda responde por texto).

Usa a API Python do piper-tts (PiperVoice.synthesize -> AudioChunk) em vez do
CLI: ela carrega o proprio sample_rate junto do audio e evita ambiguidade de
flags entre versoes. O onnxruntime do piper roda na CPU (nao toca a VRAM, que
por principio e exclusiva do LLM) e so e importado quando o TTS e usado. O
playback usa o MESMO backend de audio da captura (sounddevice).
"""
from __future__ import annotations

import shutil
import urllib.request
from pathlib import Path

# Voz PT-BR padrao (repositorio rhasspy/piper-voices no HuggingFace).
DEFAULT_VOICE = "pt_BR-faber-medium"
_VOICE_BASE = (
    "https://huggingface.co/rhasspy/piper-voices/resolve/main/"
    "pt/pt_BR/faber/medium/"
)


def voices_dir() -> Path:
    """Onde as vozes .onnx ficam (ao lado da config, por SO)."""
    from anta.core.config import config_dir

    return config_dir() / "voices"


def default_voice_path() -> Path:
    return voices_dir() / f"{DEFAULT_VOICE}.onnx"


def ensure_voice(name: str = DEFAULT_VOICE, dest_dir: Path | None = None) -> Path:
    """Garante <name>.onnx (+ .onnx.json) localmente; baixa do HuggingFace se
    faltarem. Retorna o caminho do .onnx. Levanta em falha de rede (o chamador
    — o instalador — trata e avisa)."""
    dest = dest_dir or voices_dir()
    dest.mkdir(parents=True, exist_ok=True)
    onnx = dest / f"{name}.onnx"
    cfg = dest / f"{name}.onnx.json"
    for path, url in ((onnx, f"{_VOICE_BASE}{name}.onnx"),
                      (cfg, f"{_VOICE_BASE}{name}.onnx.json")):
        if not path.exists() or path.stat().st_size == 0:
            _download(url, path)
    return onnx


def _download(url: str, dest: Path) -> None:
    """Baixa `url` para `dest` de forma atomica (.part -> rename)."""
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(dest)  # so vira o arquivo final se o download completou


def speak(texto: str, voice_path: str | Path | None = None,
          output_device: str | None = None) -> None:
    """TTS best-effort: sintetiza `texto` com Piper e reproduz. No-op silencioso
    se o piper nao estiver instalado ou a voz nao existir."""
    if not texto:
        return
    voice = Path(voice_path) if voice_path else default_voice_path()
    if not voice.exists():
        return
    try:
        pcm, sample_rate = _synthesize(texto, voice)
    except Exception:  # noqa: BLE001 - piper ausente / voz invalida: nunca derruba o handler
        return
    _play(pcm, sample_rate, output_device)


def _synthesize(texto: str, voice: Path) -> tuple[bytes, int]:
    """Roda o Piper e devolve (PCM 16-bit mono, sample_rate)."""
    from piper import PiperVoice

    v = PiperVoice.load(str(voice))
    pcm = b"".join(chunk.audio_int16_bytes for chunk in v.synthesize(texto))
    return pcm, int(v.config.sample_rate)


def _play(pcm: bytes, sample_rate: int, output_device: str | None = None) -> None:
    """Reproduz PCM 16-bit mono cru pelo sounddevice (backend de audio da captura)."""
    if not pcm:
        return
    try:
        import numpy as np
        import sounddevice as sd

        audio = np.frombuffer(pcm, dtype=np.int16)
        sd.play(audio, samplerate=sample_rate, device=_resolve_output(output_device))
        sd.wait()
    except Exception:  # noqa: BLE001 - sem saida de audio disponivel: no-op
        pass


def _resolve_output(device_name: str | None) -> int | None:
    """Nome do device de SAIDA -> indice. None (default do sistema) se vazio ou
    sumido. Espelha capture._resolve_device, mas filtra por canais de saida."""
    if not device_name:
        return None
    import sounddevice as sd

    target = device_name.strip().lower()
    fallback = None
    for idx, d in enumerate(sd.query_devices()):
        if d.get("max_output_channels", 0) <= 0:
            continue
        name = d["name"].lower()
        if name == target:
            return idx
        if fallback is None and target in name:
            fallback = idx
    return fallback
