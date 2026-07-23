"""Handler de AbrirApp: abre um app SE estiver na whitelist (anta/actions/apps.py).

Invariante de seguranca do CLAUDE.md: valida contra a whitelist antes de
qualquer subprocess. O LLM nunca gera shell — so escolhe um nome.
"""
from __future__ import annotations

import shutil
import subprocess

from anta.actions import apps
from anta.actions.context import ExecContext
from anta.actions.schema import AbrirApp


def handle(acao: AbrirApp, ctx: ExecContext) -> str:  # ctx: assinatura uniforme (nao usado)
    argv = apps.lookup(acao.nome)
    if argv is None:
        return f"App '{acao.nome}' não está na whitelist. Permitidos: {apps.permitidos()}"
    if shutil.which(argv[0]) is None:
        return f"App '{acao.nome}' na whitelist, mas '{argv[0]}' não está instalado."
    try:
        subprocess.Popen(argv, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        return f"Não consegui abrir '{acao.nome}': {e}"
    return f"Abrindo {acao.nome}."
