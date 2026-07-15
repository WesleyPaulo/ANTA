"""Whitelist de apps para a acao abrir_app — unica fonte de verdade.

Cada app mapeia o nome falado -> argv por SO, para que o mesmo comando de voz
("abre o obsidian") abra o app certo em Linux, macOS e Windows. Isolar a
whitelist aqui mantem o principio de seguranca do CLAUDE.md (abrir_app SEMPRE
valida contra esta lista) auditavel num so lugar.
"""
from __future__ import annotations

import sys

if sys.platform.startswith("win"):
    _OS = "windows"
elif sys.platform == "darwin":
    _OS = "darwin"
else:
    _OS = "linux"

# "Abrir o navegador" sem pagina nao e bem-definido (xdg-open exige um alvo),
# entao abrimos o browser padrao numa pagina neutra. Troque a vontade.
BROWSER_START_URL = "https://duckduckgo.com/"

# nome falado (canonico) -> argv por SO. argv e sempre lista, nunca string.
# Em macOS/Windows usamos os lancadores nativos (`open -a`, `start`) porque sao
# mais robustos que adivinhar o caminho do binario.
_APPS: dict[str, dict[str, list[str]]] = {
    "obsidian": {
        "linux": ["obsidian"],
        "darwin": ["open", "-a", "Obsidian"],
        "windows": ["cmd", "/c", "start", "", "obsidian://"],
    },
    "code": {
        "linux": ["code"],
        "darwin": ["open", "-a", "Visual Studio Code"],
        # code.cmd via cmd: o Popen nao resolve PATHEXT/.cmd sozinho
        "windows": ["cmd", "/c", "start", "", "code"],
    },
    "firefox": {
        "linux": ["firefox"],
        "darwin": ["open", "-a", "Firefox"],
        "windows": ["cmd", "/c", "start", "", "firefox"],
    },
    "navegador": {
        "linux": ["xdg-open", BROWSER_START_URL],
        "darwin": ["open", BROWSER_START_URL],
        "windows": ["cmd", "/c", "start", "", BROWSER_START_URL],
    },
}

# Apelidos que a pessoa/o LLM pode falar -> chave canonica em _APPS.
_ALIASES: dict[str, str] = {
    "vscode": "code",
    "vs code": "code",
    "visual studio code": "code",
    "browser": "navegador",
    "chrome": "navegador",   # sem entrada dedicada: cai no navegador padrao
}


def _canonical(nome: str) -> str | None:
    key = nome.strip().lower()
    if key in _APPS:
        return key
    return _ALIASES.get(key)


def lookup(nome: str) -> list[str] | None:
    """argv permitido para `nome` NESTE SO (case-insensitive + apelidos), ou
    None se estiver fora da whitelist ou sem mapeamento para o SO atual.

    Devolve uma copia defensiva para o chamador nunca mutar a whitelist.
    """
    key = _canonical(nome)
    if key is None:
        return None
    argv = _APPS[key].get(_OS)
    return list(argv) if argv is not None else None


def permitidos() -> str:
    """Nomes de apps aceitos (canonicos + apelidos), para mensagens de feedback."""
    nomes = set(_APPS) | set(_ALIASES)
    return ", ".join(sorted(nomes)) or "(nenhum)"
