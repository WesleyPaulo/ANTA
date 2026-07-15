"""Handler de AdicionarTarefa: anexa uma linha de checkbox em tarefas.md."""
from __future__ import annotations

from datetime import datetime

from anta.actions.context import TAREFAS_FILE, ExecContext
from anta.actions.schema import AdicionarTarefa


def handle(acao: AdicionarTarefa, ctx: ExecContext) -> str:
    ctx.vault.mkdir(parents=True, exist_ok=True)
    linha = f"- [ ] {acao.texto}"
    if acao.prazo:
        linha += f"  (prazo: {acao.prazo})"
    stamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    with (ctx.vault / TAREFAS_FILE).open("a", encoding="utf-8") as f:
        f.write(f"{linha}  <!-- {stamp} -->\n")
    return f"Tarefa adicionada: {acao.texto}"
