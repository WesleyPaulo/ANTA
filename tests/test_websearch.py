"""Busca na web SEM rede: DDG via modulo `ddgs` falso; SearXNG via urlopen mockado."""
import json
import sys
import types
import unittest
from unittest import mock

from anta.core import websearch


def _fake_ddgs(results):
    mod = types.ModuleType("ddgs")

    class DDGS:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def text(self, query, max_results=5):
            return iter(results[:max_results])

    mod.DDGS = DDGS
    return mock.patch.dict(sys.modules, {"ddgs": mod})


class _Resp:
    def __init__(self, data):
        self._d = data

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def read(self):
        return self._d


class TestDuckDuckGo(unittest.TestCase):
    def test_mapeia_campos(self):
        with _fake_ddgs([{"title": "T", "body": "B", "href": "http://x"}]):
            res = websearch.search("qualquer coisa")
        self.assertEqual(len(res), 1)
        self.assertEqual((res[0].title, res[0].snippet, res[0].url), ("T", "B", "http://x"))

    def test_aceita_chaves_alternativas(self):
        with _fake_ddgs([{"title": "T", "content": "C", "url": "http://u"}]):
            res = websearch.search("q")
        self.assertEqual((res[0].snippet, res[0].url), ("C", "http://u"))

    def test_backend_indisponivel_best_effort(self):
        # ddgs e duckduckgo_search ausentes -> ImportError engolido -> []
        with mock.patch.dict(sys.modules, {"ddgs": None, "duckduckgo_search": None}):
            self.assertEqual(websearch.search("q"), [])

    def test_engine_nao_string_nao_quebra(self):
        # config malformada (web_engine = true -> bool): str() normaliza, sem AttributeError
        with _fake_ddgs([{"title": "T", "body": "B", "href": "http://x"}]):
            res = websearch.search("q", engine=True)  # bool no lugar de str
        self.assertEqual(res[0].title, "T")  # caiu no DDG (padrao), sem levantar


class TestSearxng(unittest.TestCase):
    def test_parse_json(self):
        payload = json.dumps({"results": [
            {"title": "T", "content": "C", "url": "http://u"},
            {"title": "T2", "content": "C2", "url": "http://u2"},
        ]}).encode()
        with mock.patch("urllib.request.urlopen", return_value=_Resp(payload)):
            res = websearch.search("q", engine="searxng", searxng_url="http://searx.local",
                                   max_results=1)
        self.assertEqual(len(res), 1)  # respeita max_results
        self.assertEqual(res[0].snippet, "C")

    def test_erro_de_rede_best_effort(self):
        with mock.patch("urllib.request.urlopen", side_effect=OSError("sem rede")):
            self.assertEqual(
                websearch.search("q", engine="searxng", searxng_url="http://x"), [])

    def test_searxng_sem_url_cai_no_duckduckgo(self):
        # engine=searxng mas sem url -> usa DDG (fallback)
        with _fake_ddgs([{"title": "T", "body": "B", "href": "http://x"}]):
            res = websearch.search("q", engine="searxng", searxng_url=None)
        self.assertEqual(res[0].title, "T")


class TestFormat(unittest.TestCase):
    def _res(self):
        return [websearch.Result("T1", "S1", "http://a"),
                websearch.Result("T2", "S2", "http://b")]

    def test_context_inclui_fonte(self):
        ctx = websearch.format_context(self._res())
        self.assertIn("T1", ctx)
        self.assertIn("fonte: http://a", ctx)

    def test_sources_limita_e_junta(self):
        self.assertEqual(websearch.sources(self._res(), limit=1), "http://a")


if __name__ == "__main__":
    unittest.main()
