"""Executa uma Acao validada. Este e o unico lugar que 'faz coisas'.

Seguranca: nada de shell arbitrario. `abrir_app` valida contra uma whitelist.
Documentos sao gerados com pandoc a partir de Markdown.
"""
from __future__ import annotations

import re
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from anta.actions.schema import (
    AbrirApp, AdicionarTarefa, CriarDocumento, CriarNota, Decisao, Responder,
)

# Apps permitidos em abrir_app. Ajustar por usuario na config.
# Chave = nome falado (case-insensitive); valor = argv (lista, nunca string).
APP_WHITELIST: dict[str, list[str]] = {
    "obsidian": ["obsidian"],
    "code": ["code"],
    "vscode": ["code"],
    "firefox": ["firefox"],
    "navegador": ["xdg-open", "https://"],
}

DEFAULT_VAULT = Path.home() / "voz-notas"
TAREFAS_FILE = "tarefas.md"


@dataclass
class ExecContext:
    """Contexto que o executor precisa alem da propria Acao."""
    vault: Path = field(default_factory=lambda: DEFAULT_VAULT)
    tts: bool = False

    @classmethod
    def from_config(cls, obsidian_vault: str | None, tts: bool = False) -> "ExecContext":
        vault = Path(obsidian_vault).expanduser() if obsidian_vault else DEFAULT_VAULT
        return cls(vault=vault, tts=tts)


def _slug(texto: str) -> str:
    """Titulo -> nome de arquivo seguro."""
    s = re.sub(r"[^\w\s-]", "", texto, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[\s_-]+", "-", s)
    return s or "nota"


def _unique_path(directory: Path, stem: str, ext: str) -> Path:
    """Evita sobrescrever: nota.md, nota-2.md, ..."""
    directory.mkdir(parents=True, exist_ok=True)
    p = directory / f"{stem}.{ext}"
    n = 2
    while p.exists():
        p = directory / f"{stem}-{n}.{ext}"
        n += 1
    return p


def _speak(texto: str) -> None:
    """TTS best-effort via Piper. No-op silencioso se Piper nao existir."""
    if shutil.which("piper") is None:
        return
    try:
        subprocess.run(["piper", "--output_file", "-"], input=texto.encode(),
                       capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.SubprocessError):
        pass


def execute(decisao: Decisao, ctx: ExecContext | None = None) -> str:
    """Roda a acao e devolve uma mensagem curta de feedback (notify-send/tray)."""
    ctx = ctx or ExecContext()
    acao = decisao.escolha
    match acao:
        case CriarNota():
            path = _unique_path(ctx.vault, _slug(acao.titulo), "md")
            path.write_text(f"# {acao.titulo}\n\n{acao.conteudo}\n", encoding="utf-8")
            return f"Nota criada: {path.name}"

        case CriarDocumento():
            md_path = _unique_path(ctx.vault, _slug(acao.titulo), "md")
            md_path.write_text(f"# {acao.titulo}\n\n{acao.conteudo}\n", encoding="utf-8")
            if acao.formato == "md":
                return f"Documento criado: {md_path.name}"
            if shutil.which("pandoc") is None:
                return f"Documento salvo em .md ({md_path.name}); pandoc nao encontrado para {acao.formato}."
            out_path = md_path.with_suffix(f".{acao.formato}")
            try:
                subprocess.run(["pandoc", str(md_path), "-o", str(out_path)],
                               capture_output=True, timeout=60, check=True)
            except subprocess.CalledProcessError as e:
                err = e.stderr.decode(errors="replace")[:200] if e.stderr else ""
                return f"Falha ao converter para {acao.formato} (salvo em .md). {err}".strip()
            except (OSError, subprocess.SubprocessError):
                return f"Falha ao converter para {acao.formato} (salvo em .md)."
            return f"Documento criado: {out_path.name}"

        case AdicionarTarefa():
            ctx.vault.mkdir(parents=True, exist_ok=True)
            linha = f"- [ ] {acao.texto}"
            if acao.prazo:
                linha += f"  (prazo: {acao.prazo})"
            stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
            with (ctx.vault / TAREFAS_FILE).open("a", encoding="utf-8") as f:
                f.write(f"{linha}  <!-- {stamp} -->\n")
            return f"Tarefa adicionada: {acao.texto}"

        case AbrirApp():
            argv = APP_WHITELIST.get(acao.nome.strip().lower())
            if argv is None:
                permitidos = ", ".join(sorted(APP_WHITELIST)) or "(nenhum)"
                return f"App '{acao.nome}' nao esta na whitelist. Permitidos: {permitidos}"
            if shutil.which(argv[0]) is None:
                return f"App '{acao.nome}' na whitelist, mas '{argv[0]}' nao esta instalado."
            try:
                subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError as e:
                return f"Nao consegui abrir '{acao.nome}': {e}"
            return f"Abrindo {acao.nome}."

        case Responder():
            if ctx.tts:
                _speak(acao.texto)
            return acao.texto

    raise ValueError("acao desconhecida")
