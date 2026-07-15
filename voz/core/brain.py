"""O 'cerebro': texto transcrito -> uma Acao estruturada.

Usa Ollama (API compativel com OpenAI em http://localhost:11434/v1) +
instructor para forcar a saida no schema Pydantic (actions/schema.py).
Sem instructor o modelo inventa formato.
"""
from __future__ import annotations

from voz.actions.schema import Decisao

SYSTEM_PROMPT = (
    "Voce e um assistente pessoal local. Dado o que o usuario falou, "
    "escolha exatamente UMA acao e preencha os campos. Responda apenas "
    "no formato estruturado. Se for so uma pergunta ou conversa, use 'responder'."
)


class Brain:
    """
    TODO(claude-code):
      import instructor
      from openai import OpenAI
      client = instructor.from_openai(
          OpenAI(base_url="http://localhost:11434/v1", api_key="ollama"))
      def decide(texto: str) -> Decisao:
          return client.chat.completions.create(
              model=self.llm,               # ex: "qwen3.5:9b" (do modo)
              messages=[{"role":"system","content":SYSTEM_PROMPT},
                        {"role":"user","content":texto}],
              response_model=Decisao,
              temperature=0.1,
          )
    IMPORTANTE: setar OLLAMA_KEEP_ALIVE para manter o modelo quente e evitar
    5-10s de recarga a cada comando (ver README / instalador).
    """

    def __init__(self, llm: str) -> None:
        self.llm = llm

    def decide(self, texto: str) -> Decisao:
        raise NotImplementedError
