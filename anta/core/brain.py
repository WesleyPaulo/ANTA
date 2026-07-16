"""O 'cerebro': texto transcrito -> uma Acao estruturada (+ respostas em linguagem natural).

Usa Ollama (API compativel com OpenAI em http://localhost:11434/v1):
- decide(): instructor forca a saida no schema Pydantic (actions/schema.py). Sem
  instructor o modelo inventa formato.
- answer()/summarize(): completions CRUAS (sem response_model) para sintetizar a
  resposta de uma consulta RAG e o resumo de atividade. Usam um client OpenAI separado
  para nao depender da semantica de passthrough do instructor.

Os prompts (persona + regras por tarefa) vem de anta/core/prompts.py, editaveis pelo
usuario em config_dir()/prompts.toml. A persona e prefixada a cada prompt de tarefa.
"""
from __future__ import annotations

import re

from anta.actions.schema import Decisao, Responder
from anta.core.prompts import Prompts, load_prompts, now_line

OLLAMA_BASE_URL = "http://localhost:11434/v1"


def _strip_think(txt: str) -> str:
    """Remove blocos <think>...</think> (qwen3/deepseek-r1 vazam raciocinio no content)."""
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL)


# O Ollama LIGA o raciocinio por padrao em todo modelo que sabe pensar (routes.go:
# `if req.Think == nil { req.Think = true }`), e raciocinio + tools quebra o
# tool-calling (o modelo escreve a chamada como texto). Este e o unico lever que o
# endpoint OpenAI-compat aceita: `think:false` e `chat_template_kwargs` sao
# SILENCIOSAMENTE ignorados (campo desconhecido -> descartado, sem erro).
#
# Seguro nas tres familias: o guard e `req.Think != nil && req.Think.Bool()`, e
# "none" vira ThinkValue{false}, entao modelos sem raciocinio (Gemma, 4b-instruct)
# passam batido em vez de dar 400. Em qwen3:0.6b/1.7b/8b/14b e deepseek-r1 ele
# realmente suprime o <think>. So no qwen3:4b (thinking-2507) e no-op — por isso o
# modes.yaml usa 4b-instruct.
_SEM_RACIOCINIO = {"reasoning_effort": "none"}


def _texto_solto(erro: Exception) -> str | None:
    """Resgata o texto que o modelo escreveu quando ele conversou em vez de chamar a acao.

    O Ollama NAO aceita `tool_choice`, entao a chamada de ferramenta nunca e obrigatoria:
    num 'e ai?' o modelo pequeno so responde ('E ai! Como vai?') e o instructor levanta
    'No tool calls found'. Mas essa resposta E a acao certa — um Responder — so que fora
    do envelope. Perder isso e mostrar um traceback e o pior desfecho possivel.

    Le o `last_completion` do InstructorRetryException. Best-effort: qualquer surpresa na
    forma do erro devolve None e o chamador levanta o erro original.
    """
    comp = getattr(erro, "last_completion", None)
    try:
        conteudo = comp.choices[0].message.content
        if getattr(comp.choices[0].message, "tool_calls", None):
            return None  # houve tool call: a falha foi outra (schema invalido), nao chat
    except (AttributeError, IndexError, TypeError):
        return None
    limpo = _strip_think(conteudo or "").strip()
    if limpo.startswith(("{", "[")):
        return None  # JSON quebrado (modos json/json_schema): falar isso seria pior
    return limpo or None


def _instructor_mode(structured: str):
    """Mapeia o `structured` do modo/familia para o Mode do instructor.

    NAO use 'tools' com Ollama (fica so como escape hatch): o Ollama IGNORA
    `tool_choice` — o campo nem existe no ChatCompletionRequest dele, e campo
    desconhecido e descartado sem erro. Ou seja, a chamada de ferramenta nunca e
    obrigatoria: num "e ai" o modelo so conversa -> 'No tool calls found'. E o
    reask_tools do instructor ainda crasha iterando tool_calls=None, matando o retry.

    - 'json_schema' (DEFAULT): o schema vai no `response_format` e o Ollama repassa pro
      llama.cpp, que compila uma gramatica GBNF. A saida nao PODE ser outra coisa senao
      o schema — e o que o tool_choice faria, so que uma camada abaixo, onde funciona.
    - 'json': gramatica JSON generica + schema no system prompt (o modelo ve as
      descricoes dos campos, mas a conformidade e so por prompt). Fallback conservador
      se algum Ollama antigo nao entender o response_format json_schema.

    Os dois modos JSON re-perguntam via reask_md_json, que e None-safe.
    """
    import instructor

    return {
        "tools": instructor.Mode.TOOLS,
        "json": instructor.Mode.JSON,
    }.get(structured, instructor.Mode.JSON_SCHEMA)


class Brain:
    """Decide a Acao a partir do texto e sintetiza respostas/resumos. Os clients sao
    construidos preguicosamente para nao exigir Ollama de pe apenas para importar.

    IMPORTANTE: setar OLLAMA_KEEP_ALIVE para manter o modelo quente e evitar
    5-10s de recarga a cada comando (ver README / instalador).
    """

    def __init__(self, llm: str, base_url: str = OLLAMA_BASE_URL,
                 timeout: float = 60.0, prompts: Prompts | None = None,
                 structured: str = "tools") -> None:
        self.llm = llm
        self.base_url = base_url
        self.timeout = timeout  # evita o daemon single-thread travar se o Ollama pendurar
        self.prompts = prompts or load_prompts()
        self.structured = structured  # tools | json (vem do modo/familia)
        self._client = None      # instructor-patched (decide)
        self._raw_client = None  # OpenAI cru (answer/summarize)

    def _get_client(self):
        if self._client is None:
            import instructor
            from openai import OpenAI

            self._client = instructor.from_openai(
                OpenAI(base_url=self.base_url, api_key="ollama", timeout=self.timeout),
                mode=_instructor_mode(self.structured),
            )
        return self._client

    def _get_raw_client(self):
        if self._raw_client is None:
            from openai import OpenAI

            self._raw_client = OpenAI(base_url=self.base_url, api_key="ollama",
                                      timeout=self.timeout)
        return self._raw_client

    def _sys(self, task: str) -> str:
        """Persona compartilhada + contexto de tempo + o prompt da tarefa.

        A data entra aqui (e nao no Prompts) porque e fato, nao tom: nao faz sentido
        o usuario editar no prompts.toml, e precisa ser recalculada a cada chamada —
        o daemon fica ligado dias."""
        return f"{self.prompts.persona}\n\n{now_line()}\n\n{task}"

    def warm(self) -> str | None:
        """Fixa o modelo na VRAM com um preload keep_alive=-1 no endpoint NATIVO
        do Ollama (/api/generate sem prompt so carrega e mantem o modelo). Cumpre
        o principio 'modelo sempre quente' no nivel do app — o endpoint
        OpenAI-compat nao aceita keep_alive. Best-effort: nunca levanta, nao
        derruba o boot.

        Devolve None se o modelo ficou quente, ou uma mensagem de diagnostico se
        nao. O chamador DEVE mostrar essa mensagem: um 404 aqui significa que o
        modelo nao foi puxado, e entao TODA fala vai falhar — melhor dizer no
        boot do que deixar o usuario descobrir na primeira frase."""
        import json
        import urllib.error
        import urllib.request

        base = self.base_url.rsplit("/v1", 1)[0]  # http://host:11434/v1 -> raiz nativa
        payload = json.dumps({"model": self.llm, "keep_alive": -1}).encode("utf-8")
        req = urllib.request.Request(
            f"{base}/api/generate", data=payload,
            headers={"Content-Type": "application/json"},
        )
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                r.read()
            return None
        except urllib.error.HTTPError as e:  # antes de OSError: HTTPError herda dele
            if e.code == 404:  # modelo ausente no Ollama: erro de config, nao de rede
                return (f"o modelo '{self.llm}' nao esta instalado no Ollama. "
                        f"Rode: ollama pull {self.llm}")
            return f"o Ollama recusou o preload de '{self.llm}' (HTTP {e.code})."
        except (OSError, ValueError) as e:  # noqa: BLE001 - Ollama fora do ar/URL ruim
            return f"nao consegui falar com o Ollama em {self.base_url} ({e})."

    def decide(self, texto: str, history: list[tuple[str, str]] | None = None) -> Decisao:
        """Escolhe a acao. `history` = janela de conversa recente [(fala, rotulo)] para
        resolver referencias ('cria outra igual', 'e o prazo disso?')."""
        system = self._sys(self.prompts.decide)
        if history:
            linhas = "\n".join(f'- Voce disse: "{fala}" -> {rotulo}' for fala, rotulo in history)
            system = (f"{system}\n\nConversa recente (mais antigo -> mais novo), use "
                      f"para resolver referencias como 'isso'/'aquele'/'outra igual':\n{linhas}")
        try:
            return self._get_client().chat.completions.create(
                model=self.llm,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": texto},
                ],
                response_model=Decisao,
                temperature=0.1,
                # 2 tentativas: o instructor re-prompta com o erro de schema. Modelo
                # pequeno erra o formato de vez em quando e a 2a costuma acertar; mais
                # que isso so faz o usuario esperar em silencio.
                max_retries=2,
                extra_body=dict(_SEM_RACIOCINIO),
            )
        except Exception as e:  # noqa: BLE001 - ver _texto_solto
            resgatado = _texto_solto(e)
            if resgatado is None:
                raise
            return Decisao(escolha=Responder(texto=resgatado))

    def _complete(self, system: str, user: str, temperature: float) -> str:
        """Completion crua (sem response_model). Pede sem raciocinio (ver
        _SEM_RACIOCINIO) — economiza tokens e latencia; ha fallback porque um Ollama
        antigo pode nao conhecer o parametro. Sempre remove <think>: o deepseek-r1
        pode ignorar o pedido, e ai o raciocinio vaza no content."""
        client = self._get_raw_client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            resp = client.chat.completions.create(
                model=self.llm, messages=messages, temperature=temperature,
                extra_body=dict(_SEM_RACIOCINIO),
            )
        except Exception:  # noqa: BLE001 - fallback sem o extra_body
            resp = client.chat.completions.create(
                model=self.llm, messages=messages, temperature=temperature,
            )
        return _strip_think(resp.choices[0].message.content or "").strip()

    def answer(self, pergunta: str, contexto: str) -> str:
        """Sintetiza a resposta de uma consulta RAG ancorada em `contexto` (trechos das
        notas). Nenhuma escolha de acao aqui."""
        return self._complete(
            self._sys(self.prompts.answer),
            f"Contexto:\n{contexto}\n\nPergunta: {pergunta}",
            temperature=0.2,
        )

    def summarize(self, periodo: str, material: str) -> str:
        """Sintetiza um resumo da atividade do usuario no periodo (dia/semana/mes)."""
        return self._complete(
            self._sys(self.prompts.resumo),
            f"Periodo: {periodo}. Atividade registrada:\n{material}\n\nFaca o resumo.",
            temperature=0.3,
        )
