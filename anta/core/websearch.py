"""Busca na web — OPT-IN. Rompe o offline da ANTA (a query vai para um buscador),
por isso so roda quando `web=true` na config.

Backends keyless por padrao: DuckDuckGo (via `ddgs`, sem chave) ou SearXNG (JSON,
se o usuario apontar uma instancia). Este modulo so LE resultados (titulo/snippet/url);
a sintese em linguagem natural e do LLM (Brain.answer), fora daqui.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request
from dataclasses import dataclass

DEFAULT_RESULTS = 5


@dataclass
class Result:
    title: str
    snippet: str
    url: str


def search(query: str, engine: str = "duckduckgo", searxng_url: str | None = None,
           max_results: int = DEFAULT_RESULTS, timeout: float = 15.0) -> list[Result]:
    """Top-N resultados da web. Best-effort: qualquer falha (sem rede, backend fora,
    lib ausente, config malformada) devolve [] — o handler reporta que nao conseguiu."""
    try:
        engine = str(engine or "duckduckgo").lower()  # str(): config pode nao ser string
        if engine == "searxng" and searxng_url:
            return _searxng(query, searxng_url, max_results, timeout)
        return _duckduckgo(query, max_results)
    except Exception:  # noqa: BLE001 - best-effort; nunca derruba o pipeline
        return []


def _duckduckgo(query: str, max_results: int) -> list[Result]:
    try:
        from ddgs import DDGS  # pacote novo
    except ImportError:
        from duckduckgo_search import DDGS  # nome antigo, mesma API

    out: list[Result] = []
    with DDGS() as ddgs:
        for r in ddgs.text(query, max_results=max_results):
            out.append(Result(
                title=r.get("title", ""),
                snippet=r.get("body") or r.get("content") or "",
                url=r.get("href") or r.get("url") or "",
            ))
    return out


def _searxng(query: str, base_url: str, max_results: int, timeout: float) -> list[Result]:
    url = base_url.rstrip("/") + "/search?" + urllib.parse.urlencode(
        {"q": query, "format": "json"})
    req = urllib.request.Request(url, headers={"User-Agent": "anta/0.3"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read())
    out: list[Result] = []
    for item in data.get("results", [])[:max_results]:
        out.append(Result(
            title=item.get("title", ""),
            snippet=item.get("content", ""),
            url=item.get("url", ""),
        ))
    return out


def format_context(results: list[Result]) -> str:
    """Resultados -> bloco de contexto para o LLM sintetizar (com a fonte de cada um)."""
    return "\n\n".join(
        f"[{i + 1}] {r.title}\n{r.snippet}\n(fonte: {r.url})"
        for i, r in enumerate(results)
    )


def sources(results: list[Result], limit: int = 3) -> str:
    """Rodape curto com as URLs (mostrado no feedback; nao e falado no TTS)."""
    urls = [r.url for r in results[:limit] if r.url]
    return " | ".join(urls)
