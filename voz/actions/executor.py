"""Executa uma Acao validada. Este e o unico lugar que 'faz coisas'.

Seguranca: nada de shell arbitrario. `abrir_app` valida contra uma whitelist.
Documentos sao gerados com pandoc a partir de Markdown.
"""
from __future__ import annotations

from voz.actions.schema import (
    AbrirApp, AdicionarTarefa, CriarDocumento, CriarNota, Decisao, Responder,
)

# Apps permitidos em abrir_app. Ajustar por usuario na config.
APP_WHITELIST: dict[str, list[str]] = {
    # "obsidian": ["obsidian"],
    # "code": ["code"],
}


def execute(decisao: Decisao) -> str:
    """Roda a acao e devolve uma mensagem curta de feedback (notify-send/tray).

    TODO(claude-code): implementar cada ramo:
      CriarNota        -> escreve .md no vault do Obsidian
      CriarDocumento   -> .md e, se formato!=md, converte via `pandoc`
      AdicionarTarefa  -> anexa a um arquivo de tarefas (ou API do task mgr)
      AbrirApp         -> subprocess.run(APP_WHITELIST[nome]) se estiver na lista
      Responder        -> so retorna o texto (opcional: Piper TTS)
    """
    acao = decisao.escolha
    match acao:
        case CriarNota():
            raise NotImplementedError
        case CriarDocumento():
            raise NotImplementedError
        case AdicionarTarefa():
            raise NotImplementedError
        case AbrirApp():
            raise NotImplementedError
        case Responder():
            return acao.texto
    raise ValueError("acao desconhecida")
