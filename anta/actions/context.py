"""Contexto e constantes de layout compartilhados pelos handlers de acao.

Folha do grafo de imports de anta.actions: so depende da stdlib, nunca de
handlers/registry/executor. E daqui que executor.py reexporta ExecContext.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # so p/ o type checker: a folha continua stdlib-only em runtime
    from typing import Callable

    from anta.core.rag import RAG

DEFAULT_VAULT = Path.home() / "anta-notas"
TAREFAS_FILE = "tarefas.md"


@dataclass
class ExecContext:
    """Contexto que o executor precisa alem da propria Acao."""
    vault: Path = field(default_factory=lambda: DEFAULT_VAULT)
    tts: bool = False
    tts_voice: str | None = None   # caminho do .onnx; None = voz padrao baixada
    tts_output: str | None = None  # nome do device de saida; None = padrao do sistema
    # Injetados em runtime pelo Pipeline (None quando rag=false ou em testes de
    # handler que nao os exercitam). Anotados sob TYPE_CHECKING p/ nao importar
    # core.rag/Brain nesta folha.
    rag: "RAG | None" = None
    answer: "Callable[[str, str], str] | None" = None       # (pergunta, contexto) -> resposta
    summarize: "Callable[[str, str], str] | None" = None    # (periodo, material) -> resumo
    write: "Callable[[str, str], str] | None" = None        # (titulo, esboco) -> corpo da nota
    web_search: "Callable[[str], list] | None" = None       # (consulta) -> [Result]; None = web off

    @classmethod
    def from_config(cls, obsidian_vault: str | None, tts: bool = False,
                    tts_voice: str | None = None,
                    tts_output: str | None = None) -> "ExecContext":
        vault = Path(obsidian_vault).expanduser() if obsidian_vault else DEFAULT_VAULT
        return cls(vault=vault, tts=tts, tts_voice=tts_voice, tts_output=tts_output)
