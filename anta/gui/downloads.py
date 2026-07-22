"""Download e verificacao dos componentes (LLM/STT/TTS/embedding) para o Configurador.

Os quatro sao a mesma abstracao 4x (guia §4.2): verificar se ja existe (idempotente)
e baixar com progresso. Best-effort: erro vira um resultado {ok: False, ...}, nunca
excecao que derruba a janela. Nada aqui toca a VRAM — STT/embedding rodam na CPU e o
LLM e baixado pelo servidor Ollama (Principio 1).

Idempotencia (guia §4.3): re-baixar nao pode estragar o que ja funciona. `ollama pull`
ja e idempotente/retomavel; STT/embedding delegam integridade ao cache do HuggingFace;
so a voz do Piper baixa arquivo cru (ver ensure_voice). Por isso `download()` pode
rodar de novo sem risco.
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from typing import Callable

# kinds validos
KINDS = ("llm", "stt", "tts_voice", "rag_embedder")

Progress = Callable[[dict], None]  # recebe {kind,key,phase,text?,pct?}

_ANSI = re.compile(r"\x1b\[[0-9;?]*[a-zA-Z]")
_PCT = re.compile(r"(\d{1,3})%")


def _emit(on_progress: Progress | None, **payload) -> None:
    if on_progress is not None:
        try:
            on_progress(payload)
        except Exception:  # noqa: BLE001 - progresso e best-effort, nunca derruba o download
            pass


# --- streaming de subprocesso (ollama pull) ---
def run_stream(cmd: list[str], on_line: Callable[[str], None] | None = None,
               *, popen=subprocess.Popen) -> int:
    """Roda `cmd` e transmite stdout linha a linha (sem ANSI). Retorna o exit code.

    encoding/errors explicitos: no Windows o spinner braille do ollama estoura em
    cp1252 sem isso (bug documentado no instalador Textual)."""
    proc = popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                 text=True, encoding="utf-8", errors="replace", bufsize=1)
    try:
        for raw in proc.stdout:  # type: ignore[union-attr]
            linha = _ANSI.sub("", raw).rstrip()
            if linha and on_line is not None:
                on_line(linha)
    finally:
        proc.stdout and proc.stdout.close()  # type: ignore[union-attr]
        proc.wait()
    return proc.returncode


# --- verificacao (idempotencia) ---
def ollama_installed() -> bool:
    return shutil.which("ollama") is not None


def ollama_running(*, timeout: float = 2.0) -> bool:
    """True se o servidor do Ollama responde em localhost:11434 (nao so instalado)."""
    import urllib.request

    try:
        with urllib.request.urlopen("http://localhost:11434/api/tags", timeout=timeout) as r:
            r.read()
        return True
    except Exception:  # noqa: BLE001 - fora do ar / nao instalado
        return False


def ollama_install_command(platform: str | None = None) -> list[str] | None:
    """Comando de instalacao do Ollama por SO (None = sem automacao p/ este SO).

    Windows: winget (mostra UAC, mas nao pendura num prompt de terminal).
    Linux/mac: o instalador oficial usa `sudo` internamente — rodar dentro da GUI
    penduraria no pedido de senha. Entao NAO auto-rodamos: devolvemos o comando p/
    o usuario colar no terminal (ver install_ollama)."""
    plat = platform if platform is not None else sys.platform
    if plat.startswith("win"):
        return ["winget", "install", "--id", "Ollama.Ollama", "-e",
                "--source", "winget", "--accept-package-agreements",
                "--accept-source-agreements"]
    return None  # Linux/mac -> caminho manual (sudo)


def install_ollama(on_progress: Progress | None = None) -> dict:
    """Instala o Ollama. Best-effort. Retorna {ok, msg, manual?}.

    `manual` (quando presente) = comando p/ o usuario rodar no terminal (Linux/mac,
    onde o instalador pede sudo). Windows tenta via winget e transmite o progresso."""
    if ollama_installed():
        return {"ok": True, "msg": "ja instalado"}
    cmd = ollama_install_command()
    if cmd is None:
        manual = ("curl -fsSL https://ollama.com/install.sh | sh" if sys.platform != "darwin"
                  else "brew install ollama")
        return {"ok": False, "manual": manual,
                "msg": "Rode este comando no terminal (precisa de sudo) ou instale por ollama.com."}
    _emit(on_progress, kind="ollama", key="", phase="start", text="Instalando o Ollama...")
    try:
        rc = run_stream(cmd, lambda line: _emit(on_progress, kind="ollama", key="",
                                                phase="line", text=line))
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "msg": str(e),
                "manual": "instale o Ollama por https://ollama.com"}
    ok = rc == 0
    _emit(on_progress, kind="ollama", key="", phase="done" if ok else "error",
          text="" if ok else f"winget saiu com codigo {rc}")
    return {"ok": ok, "msg": "" if ok else f"winget saiu com codigo {rc} (instale por ollama.com)."}


def llm_installed(tag: str, *, run=subprocess.run) -> bool:
    """True se `ollama list` ja tem esse modelo (evita re-pull desnecessario)."""
    if not ollama_installed():
        return False
    try:
        out = run(["ollama", "list"], capture_output=True, text=True,
                  encoding="utf-8", errors="replace", timeout=15)
    except (OSError, subprocess.SubprocessError):
        return False
    tags = set()
    for line in (out.stdout or "").splitlines()[1:]:  # pula o cabecalho
        first = line.split()[:1]
        if first:
            tags.add(first[0])
    if tag in tags:
        return True
    # 'qwen3:4b' casa com 'qwen3:4b:latest'? ollama usa ':latest' implicito
    if ":" not in tag and any(t.startswith(tag + ":") for t in tags):
        return True
    return f"{tag}:latest" in tags


def voice_installed(name: str) -> bool:
    """True se a voz .onnx ja esta baixada."""
    try:
        from anta.core.tts import voices_dir

        return (voices_dir() / f"{name}.onnx").exists()
    except Exception:  # noqa: BLE001
        return False


def component_status(kind: str, key: str) -> dict:
    """{installed: bool|None} — None = nao da pra saber barato (STT/embedding
    delegam ao cache do HF; o download e idempotente de qualquer jeito)."""
    if kind == "llm":
        return {"kind": kind, "key": key, "installed": llm_installed(key)}
    if kind == "tts_voice":
        return {"kind": kind, "key": key, "installed": voice_installed(key)}
    # stt / rag_embedder: idempotentes via cache HF, status "desconhecido"
    return {"kind": kind, "key": key, "installed": None}


# --- download (dispatch por kind) ---
def download(kind: str, key: str, on_progress: Progress | None = None) -> dict:
    """Baixa o componente. Retorna {ok, kind, key, msg?, path?}. Best-effort."""
    _emit(on_progress, kind=kind, key=key, phase="start", text=f"Baixando {key}...")
    try:
        if kind == "llm":
            result = _download_llm(key, on_progress)
        elif kind == "stt":
            result = _download_stt(key, on_progress)
        elif kind == "rag_embedder":
            result = _download_rag(on_progress)
        elif kind == "tts_voice":
            result = _download_voice(key, on_progress)
        else:
            result = {"ok": False, "msg": f"componente desconhecido: {kind}"}
    except Exception as e:  # noqa: BLE001 - erro vira resultado, nao excecao
        result = {"ok": False, "msg": str(e)}
    result = {"kind": kind, "key": key, **result}
    phase = "done" if result.get("ok") else "error"
    _emit(on_progress, kind=kind, key=key, phase=phase, text=result.get("msg", ""))
    return result


def _download_llm(key: str, on_progress: Progress | None) -> dict:
    if not ollama_installed():
        return {"ok": False, "msg": "Ollama nao encontrado. Instale em ollama.com."}
    if llm_installed(key):
        return {"ok": True, "msg": "ja instalado"}

    def on_line(linha: str) -> None:
        m = _PCT.search(linha)
        _emit(on_progress, kind="llm", key=key, phase="line", text=linha,
              pct=int(m.group(1)) if m else None)

    rc = run_stream(["ollama", "pull", key], on_line)
    return {"ok": rc == 0, "msg": "" if rc == 0 else f"ollama pull saiu com codigo {rc}"}


def _download_stt(key: str, on_progress: Progress | None) -> dict:
    from anta.core.stt import Transcriber

    _emit(on_progress, kind="stt", key=key, phase="line", text="Carregando modelo STT...")
    Transcriber(key).load()  # baixa se faltar, senao le do cache (idempotente)
    return {"ok": True}


def _download_rag(on_progress: Progress | None) -> dict:
    from anta.core.rag import Embedder

    _emit(on_progress, kind="rag_embedder", key="", phase="line",
          text="Carregando modelo de embedding...")
    Embedder().load()
    return {"ok": True}


def _download_voice(key: str, on_progress: Progress | None) -> dict:
    from anta.core.tts import ensure_voice, import_voice

    if voice_installed(key):
        return {"ok": True, "msg": "ja instalada", "path": None}
    # nome no formato locale-speaker-quality -> catalogo oficial; senao URL/arquivo
    if re.fullmatch(r"[a-z]{2}_[A-Z]{2}-[^-]+-[a-z]+", key):
        path = ensure_voice(key)
    else:
        path = import_voice(key)
    return {"ok": True, "path": str(path)}
