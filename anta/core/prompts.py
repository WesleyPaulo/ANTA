"""Prompts da ANTA — externalizados e editaveis pelo usuario.

Os padroes vivem aqui (unica fonte de verdade). `load_prompts()` sobrepoe overrides
de `config_dir()/prompts.toml` (se existir), campo a campo — o usuario ajusta tom/regras
sem tocar no codigo Python. `persona` e um preambulo compartilhado, prefixado a cada
prompt de tarefa pelo Brain, entao editar a persona muda a voz da ANTA em tudo.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path

from anta.core.config import config_dir

# Persona/tom compartilhado (prefixado a todos os prompts). Respostas sao FALADAS.
PERSONA = (
    "Voce e a ANTA, assistente pessoal local do usuario. Fale sempre em portugues do "
    "Brasil, de forma curta, direta e cordial. Suas respostas sao FALADAS em voz alta: "
    "use frases curtas, sem markdown, sem listas com marcadores, sem emojis. Nunca invente."
)

# Roteamento de acao (decide) — com exemplos few-shot p/ o modelo pequeno acertar mais.
DECIDE = (
    "Dado o que o usuario falou, escolha EXATAMENTE UMA acao e preencha os campos. "
    "Responda apenas no formato estruturado.\n"
    "Como escolher a acao:\n"
    "- criar_nota: guardar uma anotacao ou ideia curta.\n"
    "- criar_documento: gerar um texto maior para exportar (md, docx ou pdf).\n"
    "- adicionar_tarefa: registrar um afazer/to-do (com prazo opcional).\n"
    "- abrir_app: abrir um aplicativo pelo nome.\n"
    "- lembrar: SOMENTE quando o usuario pede explicitamente para memorizar um fato "
    "('lembre que...', 'anote que...').\n"
    "- consultar: perguntas sobre o que o usuario JA anotou/criou/pediu para lembrar, "
    "INCLUSIVE pedir um resumo das notas dele sobre um ASSUNTO/tema ('o que anotei sobre X', "
    "'qual era o prazo de Y', 'me resume o que tenho sobre o projeto X').\n"
    "- resumir: SOMENTE para um resumo da atividade do usuario num PERIODO DE TEMPO ('o que "
    "fiz hoje', 'resumo da semana', 'o que produzi esse mes'). Regra de desempate: se o "
    "pedido tem um ASSUNTO/tema (um 'sobre o que'), e consultar; se tem so um PERIODO de "
    "tempo, e resumir. Periodo: dia, semana ou mes.\n"
    "- responder: perguntas gerais, conversa, resumo de conhecimento do mundo (nao das suas "
    "notas), ou o que nao se encaixa acima. E o padrao.\n"
    "Campo memoria (opcional, separado da acao): preencha SO com um fato duravel e "
    "reutilizavel sobre o usuario (preferencia, nome, fato pessoal, decisao); senao, null. "
    "Nunca repita o comando, e nunca use memoria junto da acao lembrar.\n"
    "Exemplos:\n"
    "- 'cria uma nota chamada ideias: preciso de um modo offline' -> criar_nota"
    "(titulo='Ideias', conteudo='preciso de um modo offline')\n"
    "- 'lembra que eu prefiro reunioes de manha' -> lembrar(fato='prefere reunioes de manha')\n"
    "- 'o que eu tinha anotado sobre o contrato?' -> consultar(pergunta='o que foi anotado "
    "sobre o contrato?')\n"
    "- 'me faz um resumo do que tenho sobre o projeto X' -> consultar(pergunta='resumo das "
    "notas sobre o projeto X')   [tem assunto -> consultar, nao resumir]\n"
    "- 'me resume o que eu fiz essa semana' -> resumir(periodo='semana')   [so periodo]\n"
    "- 'abre o obsidian' -> abrir_app(nome='obsidian')\n"
    "- 'quanto e 15% de 200?' -> responder(texto='30')"
)

# Resposta ancorada de uma consulta RAG.
ANSWER = (
    "Responda a pergunta do usuario usando SOMENTE o contexto fornecido (trechos das "
    "notas dele). Se o contexto nao contiver a resposta, diga que nao encontrou nas notas "
    "— nao invente. Seja curto e direto."
)

# Sintese de um resumo de atividade.
RESUMO = (
    "Voce recebe a atividade que o usuario registrou num periodo (notas, documentos e "
    "tarefas que ele criou). Faca um resumo curto e util, em 2 a 4 frases, do que a pessoa "
    "fez e produziu nesse periodo. Agrupe por tema quando fizer sentido. Nao invente nada "
    "alem do que esta na atividade."
)

DEFAULTS: dict[str, str] = {
    "persona": PERSONA,
    "decide": DECIDE,
    "answer": ANSWER,
    "resumo": RESUMO,
}


@dataclass
class Prompts:
    persona: str = PERSONA
    decide: str = DECIDE
    answer: str = ANSWER
    resumo: str = RESUMO


def prompts_path() -> Path:
    return config_dir() / "prompts.toml"


def load_prompts(path: str | Path | None = None) -> Prompts:
    """Carrega os prompts, sobrepondo overrides do TOML (campo a campo) sobre os padroes.
    Chaves ausentes ou nao-string caem no padrao. Arquivo invalido/ausente -> padroes."""
    data = dict(DEFAULTS)
    p = Path(path) if path is not None else prompts_path()
    if p.exists():
        try:
            overrides = tomllib.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            overrides = {}
        for key in DEFAULTS:
            val = overrides.get(key)
            if isinstance(val, str) and val.strip():
                data[key] = val.strip()  # whitespace de borda nunca importa num prompt
    return Prompts(**data)


def write_default_prompts(path: str | Path | None = None) -> Path:
    """Escreve os prompts padrao num TOML editavel — SEM sobrescrever edicoes existentes.
    O instalador chama isto para o usuario ter um arquivo pronto para ajustar."""
    p = Path(path) if path is not None else prompts_path()
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Prompts da ANTA — edite para mudar tom/regras sem tocar no codigo.",
        "# Apague uma chave (ou o arquivo todo) para voltar ao padrao interno.",
        "",
    ]
    for key, val in DEFAULTS.items():
        lines.append(f'{key} = """')
        lines.append(val)
        lines.append('"""')
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
