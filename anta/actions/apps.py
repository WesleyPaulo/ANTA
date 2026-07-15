"""Whitelist de apps para a acao abrir_app — unica fonte de verdade.

Isolar a whitelist aqui mantem o principio de seguranca do CLAUDE.md
(abrir_app SEMPRE valida contra esta lista) auditavel num so lugar, e da
um ponto natural para override por config/instalador no futuro.
"""
from __future__ import annotations

# Chave = nome falado (case-insensitive); valor = argv (lista, nunca string).
APP_WHITELIST: dict[str, list[str]] = {
    "obsidian": ["obsidian"],
    "code": ["code"],
    "vscode": ["code"],
    "firefox": ["firefox"],
    "navegador": ["xdg-open", "https://"],
}


def lookup(nome: str) -> list[str] | None:
    """argv permitido para `nome` (case-insensitive), ou None se fora da lista.

    Devolve uma copia defensiva para o chamador nunca mutar a whitelist.
    """
    argv = APP_WHITELIST.get(nome.strip().lower())
    return list(argv) if argv is not None else None


def permitidos() -> str:
    """Lista legivel dos apps permitidos, para mensagens de feedback."""
    return ", ".join(sorted(APP_WHITELIST)) or "(nenhum)"
