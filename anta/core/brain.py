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

from anta.actions.schema import Decisao
from anta.core.prompts import Prompts, load_prompts

OLLAMA_BASE_URL = "http://localhost:11434/v1"


def _strip_think(txt: str) -> str:
    """Remove blocos <think>...</think> (qwen3 pode vazar raciocinio no content)."""
    return re.sub(r"<think>.*?</think>", "", txt, flags=re.DOTALL)


class Brain:
    """Decide a Acao a partir do texto e sintetiza respostas/resumos. Os clients sao
    construidos preguicosamente para nao exigir Ollama de pe apenas para importar.

    IMPORTANTE: setar OLLAMA_KEEP_ALIVE para manter o modelo quente e evitar
    5-10s de recarga a cada comando (ver README / instalador).
    """

    def __init__(self, llm: str, base_url: str = OLLAMA_BASE_URL,
                 timeout: float = 60.0, prompts: Prompts | None = None) -> None:
        self.llm = llm
        self.base_url = base_url
        self.timeout = timeout  # evita o daemon single-thread travar se o Ollama pendurar
        self.prompts = prompts or load_prompts()
        self._client = None      # instructor-patched (decide)
        self._raw_client = None  # OpenAI cru (answer/summarize)

    def _get_client(self):
        if self._client is None:
            import instructor
            from openai import OpenAI

            self._client = instructor.from_openai(
                OpenAI(base_url=self.base_url, api_key="ollama", timeout=self.timeout)
            )
        return self._client

    def _get_raw_client(self):
        if self._raw_client is None:
            from openai import OpenAI

            self._raw_client = OpenAI(base_url=self.base_url, api_key="ollama",
                                      timeout=self.timeout)
        return self._raw_client

    def _sys(self, task: str) -> str:
        """Persona compartilhada + o prompt da tarefa."""
        return f"{self.prompts.persona}\n\n{task}"

    def warm(self) -> None:
        """Fixa o modelo na VRAM com um preload keep_alive=-1 no endpoint NATIVO
        do Ollama (/api/generate sem prompt so carrega e mantem o modelo). Cumpre
        o principio 'modelo sempre quente' no nivel do app — o endpoint
        OpenAI-compat nao aceita keep_alive. Best-effort: se o Ollama nao estiver
        de pe, nao derruba o boot (o chamador ja envolve warm() em try/except)."""
        import json
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
        except (OSError, ValueError):
            pass

    def decide(self, texto: str, history: list[tuple[str, str]] | None = None) -> Decisao:
        """Escolhe a acao. `history` = janela de conversa recente [(fala, rotulo)] para
        resolver referencias ('cria outra igual', 'e o prazo disso?')."""
        system = self._sys(self.prompts.decide)
        if history:
            linhas = "\n".join(f'- Voce disse: "{fala}" -> {rotulo}' for fala, rotulo in history)
            system = (f"{system}\n\nConversa recente (mais antigo -> mais novo), use "
                      f"para resolver referencias como 'isso'/'aquele'/'outra igual':\n{linhas}")
        return self._get_client().chat.completions.create(
            model=self.llm,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": texto},
            ],
            response_model=Decisao,
            temperature=0.1,
        )

    def _complete(self, system: str, user: str, temperature: float) -> str:
        """Completion crua (sem response_model). enable_thinking=False economiza tokens
        no qwen3; nem toda versao aceita, entao ha fallback. Sempre remove <think>."""
        client = self._get_raw_client()
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ]
        try:
            resp = client.chat.completions.create(
                model=self.llm, messages=messages, temperature=temperature,
                extra_body={"chat_template_kwargs": {"enable_thinking": False}},
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
