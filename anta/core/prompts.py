"""Prompts da ANTA — externalizados e editaveis pelo usuario.

Os padroes vivem aqui (unica fonte de verdade). `load_prompts()` sobrepoe overrides
de `config_dir()/prompts.toml` (se existir), campo a campo — o usuario ajusta tom/regras
sem tocar no codigo Python. `persona` e um preambulo compartilhado, prefixado a cada
prompt de tarefa pelo Brain, entao editar a persona muda a voz da ANTA em tudo.
"""
from __future__ import annotations

import tomllib
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from anta.core.config import config_dir

# Persona/tom compartilhado (prefixado a todos os prompts). Respostas sao FALADAS.
PERSONA = (
    "Voce e a ANTA, assistente pessoal local do usuario. Fale sempre em portugues do "
    "Brasil, de forma curta, direta e cordial. Suas respostas sao FALADAS em voz alta: "
    "use frases curtas, sem markdown, sem listas com marcadores, sem emojis. Nunca invente."
)

_DIAS = ("segunda-feira", "terca-feira", "quarta-feira", "quinta-feira",
         "sexta-feira", "sabado", "domingo")
_MESES = ("janeiro", "fevereiro", "marco", "abril", "maio", "junho", "julho",
          "agosto", "setembro", "outubro", "novembro", "dezembro")


def now_line(agora: datetime | None = None) -> str:
    """Contexto de tempo, injetado em TODO system prompt (nao e editavel: e fato, nao tom).

    Sem isso o modelo nao tem como saber a data, e a persona manda 'nunca invente' —
    entao 'que dia e hoje?' virava buscar_web (com a web off, um beco sem saida).
    Formatamos na mao de proposito: strftime('%A') depende do locale do processo, que
    no Windows quase nunca e pt_BR.
    """
    agora = agora or datetime.now()
    return (f"Contexto de tempo (fonte da verdade, use sempre que precisar da data ou "
            f"da hora): agora sao {agora:%H:%M} de {_DIAS[agora.weekday()]}, "
            f"{agora.day} de {_MESES[agora.month - 1]} de {agora.year}.")


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
    "- consultar: SOMENTE quando o usuario se refere ao MATERIAL DELE — o que ele anotou, "
    "criou, salvou ou pediu para lembrar. Quase sempre ha uma marca disso na frase: 'eu "
    "anotei', 'minhas notas', 'que eu salvei', 'meu projeto', 'o que tenho sobre'. "
    "Ex.: 'o que anotei sobre X', 'qual era o prazo de Y', 'me resume o que tenho sobre o "
    "projeto X'. Se a pergunta e sobre um assunto do MUNDO (historia, ciencia, idiomas, "
    "definicoes, como algo funciona) e NAO cita as notas do usuario, e responder — NAO "
    "consultar. Na duvida entre consultar e responder, escolha responder: as notas dele "
    "nao tem a Revolucao Industrial dentro.\n"
    "- resumir: SOMENTE para um resumo da atividade do usuario num PERIODO DE TEMPO ('o que "
    "fiz hoje', 'resumo da semana', 'o que produzi esse mes'). Regra de desempate: se o "
    "pedido tem um ASSUNTO/tema (um 'sobre o que'), e consultar; se tem so um PERIODO de "
    "tempo, e resumir. Periodo: dia, semana ou mes.\n"
    "- buscar_web: SOMENTE quando o usuario pede busca na internet ('pesquisa na web', "
    "'procura na internet', 'busca online') ou pergunta algo atual que exige a internet "
    "(noticias de hoje, cotacao, placar). Conhecimento geral que voce ja sabe -> responder. "
    "Data e hora NAO exigem a internet: voce ja tem no contexto de tempo acima.\n"
    "- responder: perguntas gerais, conversa e conhecimento do mundo que voce ja sabe — "
    "historia, ciencia, traducao, definicoes, explicacoes ('me fala sobre a Revolucao "
    "Industrial', 'como se fala X em ingles'). Inclui data e hora atuais ('que dia e hoje?', "
    "'que horas sao?') — leia do contexto de tempo acima. E o PADRAO: se nenhuma outra acao "
    "se encaixa claramente, use responder.\n"
    "Campo memoria (opcional, separado da acao): preencha SO com um fato duravel e "
    "reutilizavel sobre o usuario (preferencia, nome, fato pessoal, decisao); senao, null. "
    "Nunca repita o comando, e nunca use memoria junto da acao lembrar.\n"
    "Exemplos:\n"
    "- 'cria uma nota chamada ideias: preciso de um modo offline' -> criar_nota"
    "(titulo='Ideias', conteudo='preciso de um modo offline')\n"
    "- 'lembra que eu prefiro reunioes de manha' -> lembrar(fato='prefere reunioes de manha')\n"
    "- 'o que eu tinha anotado sobre o contrato?' -> consultar(pergunta='o que foi anotado "
    "sobre o contrato?')   [cita as notas DELE]\n"
    "- 'me faz um resumo do que tenho sobre o projeto X' -> consultar(pergunta='resumo das "
    "notas sobre o projeto X')   [tem assunto -> consultar, nao resumir]\n"
    "- 'voce poderia falar mais sobre a Revolucao Industrial?' -> responder(texto='...')   "
    "[assunto do mundo, NAO cita as notas -> responder, nao consultar]\n"
    "- 'como se fala perspicaz em ingles?' -> responder(texto='...')   [conhecimento geral]\n"
    "- 'me resume o que eu fiz essa semana' -> resumir(periodo='semana')   [so periodo]\n"
    "- 'pesquisa na web quem ganhou o jogo ontem' -> buscar_web(consulta='quem ganhou o "
    "jogo ontem')\n"
    "- 'abre o obsidian' -> abrir_app(nome='obsidian')\n"
    "- 'quanto e 15% de 200?' -> responder(texto='30')"
)

# Resposta ancorada (consulta RAG nas notas OU busca na web).
ANSWER = (
    "Responda a pergunta do usuario usando SOMENTE o contexto fornecido (trechos das notas "
    "dele ou resultados de uma busca). Se o contexto nao contiver a resposta, diga que nao "
    "encontrou — nao invente. Seja curto e direto."
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
    """Escreve o TOML de prompts com todos os campos COMENTADOS — SEM sobrescrever edicoes.

    Comentado de proposito. Antes o arquivo saia com uma COPIA dos padroes, e como
    `load_prompts()` sobrepoe o TOML por cima do codigo, o snapshot da instalacao passava
    a ganhar para sempre: toda melhoria posterior no roteamento (o `decide` e afiado a
    cada bug de roteamento encontrado) simplesmente nunca chegava em quem ja tinha
    instalado — e nada avisava. Comentado, o padrao do codigo vale ate o usuario decidir
    o contrario, e o arquivo segue servindo de referencia do que da pra editar.
    """
    p = Path(path) if path is not None else prompts_path()
    if p.exists():
        return p
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Prompts da ANTA — descomente um bloco para SUBSTITUIR o padrao daquele campo.",
        "#",
        "# Enquanto um campo esta comentado, vale o padrao do codigo (que melhora a cada",
        "# versao). Ao descomentar, aquele campo CONGELA no que estiver aqui: e sua",
        "# responsabilidade, e as melhorias futuras da ANTA nao chegam nele.",
        "# Para voltar ao padrao: comente de novo (ou apague o bloco).",
        "",
    ]
    for key, val in DEFAULTS.items():
        lines.append(f'# {key} = """')
        lines.extend(f"# {linha}" if linha else "#" for linha in val.split("\n"))
        lines.append('# """')
        lines.append("")
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
