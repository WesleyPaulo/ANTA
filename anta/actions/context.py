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

    @classmethod
    def from_config(cls, obsidian_vault: str | None, tts: bool = False) -> "ExecContext":
        vault = Path(obsidian_vault).expanduser() if obsidian_vault else DEFAULT_VAULT
        return cls(vault=vault, tts=tts)
