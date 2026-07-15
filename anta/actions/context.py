"""Contexto e constantes de layout compartilhados pelos handlers de acao.

Folha do grafo de imports de anta.actions: so depende da stdlib, nunca de
handlers/registry/executor. E daqui que executor.py reexporta ExecContext.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_VAULT = Path.home() / "anta-notas"
TAREFAS_FILE = "tarefas.md"


@dataclass
class ExecContext:
    """Contexto que o executor precisa alem da propria Acao."""
    vault: Path = field(default_factory=lambda: DEFAULT_VAULT)
    tts: bool = False
    tts_voice: str | None = None   # caminho do .onnx; None = voz padrao baixada
    tts_output: str | None = None  # nome do device de saida; None = padrao do sistema

    @classmethod
    def from_config(cls, obsidian_vault: str | None, tts: bool = False,
                    tts_voice: str | None = None,
                    tts_output: str | None = None) -> "ExecContext":
        vault = Path(obsidian_vault).expanduser() if obsidian_vault else DEFAULT_VAULT
        return cls(vault=vault, tts=tts, tts_voice=tts_voice, tts_output=tts_output)
