"""O 'cerebro': texto transcrito -> uma Acao estruturada.

Usa Ollama (API compativel com OpenAI em http://localhost:11434/v1) +
instructor para forcar a saida no schema Pydantic (actions/schema.py).
Sem instructor o modelo inventa formato.
"""
from __future__ import annotations

from anta.actions.schema import Decisao

SYSTEM_PROMPT = (
    "Voce e um assistente pessoal local. Dado o que o usuario falou, "
    "escolha exatamente UMA acao e preencha os campos. Responda apenas "
    "no formato estruturado. Se for so uma pergunta ou conversa, use 'responder'."
)

OLLAMA_BASE_URL = "http://localhost:11434/v1"


class Brain:
    """Decide a Acao a partir do texto. O cliente e construido preguicosamente
    para nao exigir Ollama de pe apenas para importar/instanciar.

    IMPORTANTE: setar OLLAMA_KEEP_ALIVE para manter o modelo quente e evitar
    5-10s de recarga a cada comando (ver README / instalador).
    """

    def __init__(self, llm: str, base_url: str = OLLAMA_BASE_URL,
                 timeout: float = 60.0) -> None:
        self.llm = llm
        self.base_url = base_url
        self.timeout = timeout  # evita o daemon single-thread travar se o Ollama pendurar
        self._client = None

    def _get_client(self):
        if self._client is None:
            import instructor
            from openai import OpenAI

            self._client = instructor.from_openai(
                OpenAI(base_url=self.base_url, api_key="ollama", timeout=self.timeout)
            )
        return self._client

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

    def decide(self, texto: str) -> Decisao:
        return self._get_client().chat.completions.create(
            model=self.llm,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": texto},
            ],
            response_model=Decisao,
            temperature=0.1,
        )
