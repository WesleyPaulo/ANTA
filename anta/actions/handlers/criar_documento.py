"""Handler de CriarDocumento: escreve .md e converte via pandoc se formato != md."""
from __future__ import annotations

import shutil
import subprocess

from anta.actions.context import ExecContext
from anta.actions.helpers import corpo_da_nota, note_body, slug, unique_path
from anta.actions.schema import CriarDocumento


def handle(acao: CriarDocumento, ctx: ExecContext) -> str:
    md_path = unique_path(ctx.vault, slug(acao.titulo), "md")
    md_path.write_text(note_body(acao.titulo, corpo_da_nota(acao, ctx)), encoding="utf-8")
    if acao.formato == "md":
        return f"Documento criado: {md_path.name}"
    if shutil.which("pandoc") is None:
        return f"Documento salvo em .md ({md_path.name}); pandoc não encontrado para {acao.formato}."
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
