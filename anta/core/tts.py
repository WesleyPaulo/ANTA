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
import threading
import urllib.request
from pathlib import Path

# Vozes do repositorio oficial rhasspy/piper-voices (HuggingFace).
DEFAULT_VOICE = "pt_BR-faber-medium"
_REPO = "https://huggingface.co/rhasspy/piper-voices/resolve/main"

# As vozes em portugues do catalogo oficial (voices.json, conferido em 2026-07-16 — sao
# so estas 5, de 165). Lista fixa p/ `anta vozes` funcionar sem rede; NAO e um gate:
# ensure_voice() aceita qualquer nome no padrao do Piper, e import_voice() aceita
# qualquer voz Piper de qualquer origem.
#
# NENHUMA fonte informa o genero das vozes (nem o voices.json, nem os MODEL_CARDs, nem os
# cards dos repos da comunidade) — deduzir pelo nome do speaker e chute. O que da pra
# afirmar e o F0 (frequencia fundamental) MEDIDO das amostras, em 2026-07-16: um dado
# objetivo de registro (grave/agudo). Metodo aferido contra vozes en_US do mesmo catalogo,
# que se espalharam de 86 a 202 Hz — ou seja, ele separa os registros de fato.
# Referencia da literatura: fala adulta masculina ~85-155 Hz, feminina ~165-255 Hz.
# F0 alto NAO prova genero: para decidir, ouca em https://rhasspy.github.io/piper-samples/
VOZES_PT = {
    "pt_BR-faber-medium": "22 kHz, media  | F0 ~170 Hz — padrao da ANTA",
    "pt_BR-cadu-medium": "22 kHz, media  | F0 ~134 Hz (registro grave)",
    "pt_BR-jeff-medium": "22 kHz, media  | F0 ~150 Hz",
    "pt_BR-edresson-low": "16 kHz, baixa  | F0 ~158 Hz — mais rapida e leve",
    "pt_PT-tugão-medium": "22 kHz, media  | F0 ~170 Hz — portugues de PORTUGAL",
}

# Vozes PT fora do repo oficial, conferidas a mao (formato Piper correto, sintetizadas e
# medidas aqui). Precisam de URL: `ensure_voice` so sabe o layout do repo oficial, entao
# sem este mapa `anta vozes pt_BR-dii-high` iria bater 404 no rhasspy/piper-voices.
# ATENCAO: estes repos NAO declaram licenca — ver README/docs antes de uso comercial.
VOZES_COMUNIDADE = {
    "pt_BR-dii-high": (
        "https://huggingface.co/csukuangfj/vits-piper-pt_BR-dii-high/resolve/main/"
        "pt_BR-dii-high.onnx",
        "22 kHz, ALTA  | F0 ~197 Hz (registro agudo) — sem licenca declarada",
    ),
    "pt_BR-miro-high": (
        "https://huggingface.co/csukuangfj/vits-piper-pt_BR-miro-high/resolve/main/"
        "pt_BR-miro-high.onnx",
        "22 kHz, ALTA  | F0 ~118 Hz (registro grave) — sem licenca declarada",
    ),
}
AMOSTRAS_URL = "https://rhasspy.github.io/piper-samples/"


def _voice_url(name: str) -> str:
    """Nome da voz -> URL base no repo oficial.
    'pt_BR-cadu-medium' -> '.../pt/pt_BR/cadu/medium/'.

    O layout do repo e <lingua>/<locale>/<speaker>/<qualidade>/ — tudo derivavel do nome.
    Antes esta base era uma CONSTANTE fixa em faber/medium: `ensure_voice("outra-voz")`
    baixava da URL do faber e dava 404. So a voz padrao funcionava de verdade.
    """
    partes = name.split("-")
    if len(partes) != 3:
        raise ValueError(f"nome de voz invalido: {name!r}. Padrao do Piper: "
                         f"<locale>-<speaker>-<qualidade>, ex.: pt_BR-cadu-medium")
    locale, speaker, qualidade = partes
    return f"{_REPO}/{locale.split('_')[0]}/{locale}/{speaker}/{qualidade}/"


def voices_dir() -> Path:
    """Onde as vozes .onnx ficam (ao lado da config, por SO)."""
    from anta.core.config import config_dir

    return config_dir() / "voices"


def default_voice_path() -> Path:
    return voices_dir() / f"{DEFAULT_VOICE}.onnx"


def _resolve_voice(voice_path: str | Path | None) -> Path:
    """Resolve a voz aceitando CAMINHO completo OU nome do catalogo.

    O Configurador (GUI) salva o NOME (ex.: 'pt_BR-dii-high'); o CLI `anta vozes` e a
    TUI salvam o CAMINHO do .onnx. Sem isso o runtime so aceitava caminho -> TTS mudo
    quando configurado pela GUI ('voz nao encontrada em pt_BR-dii-high')."""
    if not voice_path:
        return default_voice_path()
    p = Path(voice_path)
    if p.exists():
        return p  # caminho completo (CLI/TUI ou voz importada)
    nome = p.name if p.name.endswith(".onnx") else f"{p.name}.onnx"
    return voices_dir() / nome  # nome do catalogo -> voices_dir()/<nome>.onnx


def ensure_voice(name: str = DEFAULT_VOICE, dest_dir: Path | None = None) -> Path:
    """Garante <name>.onnx (+ .onnx.json) localmente; baixa do repo OFICIAL se faltarem.
    Retorna o caminho do .onnx. Levanta em falha de rede (o chamador — o instalador —
    trata e avisa). Para vozes fora do repo oficial, ver import_voice()."""
    dest = dest_dir or voices_dir()
    dest.mkdir(parents=True, exist_ok=True)
    base = _voice_url(name)
    onnx = dest / f"{name}.onnx"
    cfg = dest / f"{name}.onnx.json"
    for path, url in ((onnx, f"{base}{name}.onnx"), (cfg, f"{base}{name}.onnx.json")):
        if not path.exists() or path.stat().st_size == 0:
            _download(url, path)
    return onnx


def import_voice(onnx: str | Path, config: str | Path | None = None,
                 nome: str | None = None, dest_dir: Path | None = None) -> Path:
    """Importa uma voz Piper de QUALQUER origem (arquivo local ou URL) para voices_dir().

    O Piper so precisa do par `<voz>.onnx` + `<voz>.onnx.json` — nao importa se veio do
    repo oficial, de outro repo do HuggingFace, ou de um treino seu. Nao existe catalogo
    fechado: o `speak()` recebe um CAMINHO, nao um nome.

    `config` default: o proprio onnx + '.json' (o par sempre anda junto). Levanta se o
    .json faltar — sem ele o Piper nao carrega a voz (traz fonemas, sample_rate e
    inferencia), e uma voz meia-boca ia falhar so na hora de falar.
    """
    dest = dest_dir or voices_dir()
    dest.mkdir(parents=True, exist_ok=True)
    origem_onnx = str(onnx)
    origem_cfg = str(config) if config else f"{origem_onnx}.json"
    nome = nome or Path(origem_onnx).name.removesuffix(".onnx")

    destino_onnx = dest / f"{nome}.onnx"
    destino_cfg = dest / f"{nome}.onnx.json"
    _fetch(origem_onnx, destino_onnx)
    try:
        _fetch(origem_cfg, destino_cfg)
    except Exception:
        destino_onnx.unlink(missing_ok=True)  # nao deixa voz pela metade em voices_dir()
        raise
    return destino_onnx


def _fetch(origem: str, dest: Path) -> None:
    """Copia `origem` (URL http(s) ou caminho local) para `dest`."""
    if origem.startswith(("http://", "https://")):
        _download(origem, dest)
        return
    src = Path(origem).expanduser()
    if not src.is_file():
        raise FileNotFoundError(f"arquivo de voz nao encontrado: {src}")
    shutil.copyfile(src, dest)


def _download(url: str, dest: Path) -> None:
    """Baixa `url` para `dest` de forma atomica (.part -> rename)."""
    tmp = dest.with_name(dest.name + ".part")
    with urllib.request.urlopen(url, timeout=120) as r, open(tmp, "wb") as f:
        shutil.copyfileobj(r, f)
    tmp.replace(dest)  # so vira o arquivo final se o download completou


def _tts_warn(msg: str, *, exc: bool = False) -> None:
    """Loga a falha do TTS (best-effort) em vez de engolir em silencio. No app de
    janela o stderr vai pro anta.log — sem isso, TTS mudo por bundle incompleto
    (piper/onnxruntime/espeak-ng) fica invisivel."""
    import sys

    print(f"[anta][tts] {msg}", file=sys.stderr)
    if exc:
        import traceback

        traceback.print_exc()


# Interrupcao da fala (botao "Parar" do HUD / mesma tecla do atalho). Modulo-nivel
# porque `speak()` e chamada la no fundo (handler -> executor -> pipeline) e quem
# cancela esta noutra thread (a GUI). O `Pipeline.run` chama `reset()` no inicio de
# cada turno; `Pipeline.cancel` chama `stop()`.
_CANCEL = threading.Event()


def stop() -> None:
    """Interrompe a fala em andamento e marca o turno como cancelado.

    Duas metades, ambas necessarias: `sd.stop()` corta o audio que JA esta tocando
    (o `sd.wait()` do `_play` retorna na hora), e o Event impede que uma sintese
    ainda em curso comece a tocar depois — sem ele, cancelar durante o Piper so
    adiava a fala em vez de mata-la."""
    _CANCEL.set()
    try:
        import sounddevice as sd

        sd.stop()
    except Exception:  # noqa: BLE001 - sem audio/sounddevice: o Event ja basta
        pass


def reset() -> None:
    """Limpa a marca de cancelamento (inicio de um novo turno)."""
    _CANCEL.clear()


def cancelled() -> bool:
    return _CANCEL.is_set()


def speak(texto: str, voice_path: str | Path | None = None,
          output_device: str | None = None) -> None:
    """TTS best-effort: sintetiza `texto` com Piper e reproduz. No-op se o piper
    nao estiver instalado ou a voz nao existir — mas LOGA o motivo (o handler nunca
    cai, mas a falha nao fica silenciosa). No-op tambem se o turno foi cancelado."""
    if not texto or cancelled():
        return
    voice = _resolve_voice(voice_path)
    if not voice.exists():
        _tts_warn(f"voz nao encontrada em {voice} (voice_path={voice_path!r})")
        return
    try:
        pcm, sample_rate = _synthesize(texto, voice)
    except Exception as e:  # noqa: BLE001 - piper ausente / voz invalida / bundle incompleto
        _tts_warn(f"falha ao sintetizar ({e.__class__.__name__}: {e})", exc=True)
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
    if not pcm or cancelled():  # cancelou durante a sintese: nao comeca a tocar
        return
    try:
        import numpy as np
        import sounddevice as sd

        audio = np.frombuffer(pcm, dtype=np.int16)
        sd.play(audio, samplerate=sample_rate, device=_resolve_output(output_device))
        sd.wait()
    except Exception as e:  # noqa: BLE001 - sem saida de audio disponivel
        _tts_warn(f"falha ao reproduzir ({e.__class__.__name__}: {e})", exc=True)


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
