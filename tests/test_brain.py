"""Testes do Brain sem Ollama: injetamos clients falsos em _client/_raw_client.

Cobrem: strip de <think> e ancoragem no contexto em answer(), fallback quando o
extra_body nao e aceito, e a injecao da janela de conversa no system prompt do decide().
"""
import unittest
import unittest.mock
import urllib.error
from types import SimpleNamespace

import instructor

from anta.actions.schema import Decisao, Responder
from anta.core.brain import Brain, _instructor_mode, _strip_think
from anta.core.prompts import Prompts

_PROMPTS = Prompts(persona="PERSONA_X", decide="DECIDE_X", answer="ANSWER_X", resumo="RESUMO_X")


def _fake_client(content="resp", capture=None, canned=None, raise_on_extra=False):
    """Client falso com .chat.completions.create. Se `canned` != None, devolve-o
    (caminho decide/response_model); senao devolve um ChatCompletion cru com `content`."""
    def create(**kwargs):
        if capture is not None:
            capture.clear()
            capture.update(kwargs)
        if raise_on_extra and "extra_body" in kwargs:
            raise RuntimeError("extra_body nao suportado por esta versao")
        if canned is not None:
            return canned
        msg = SimpleNamespace(content=content)
        return SimpleNamespace(choices=[SimpleNamespace(message=msg)])
    completions = SimpleNamespace(create=create)
    return SimpleNamespace(chat=SimpleNamespace(completions=completions))


class TestStripThink(unittest.TestCase):
    def test_remove_bloco_think(self):
        self.assertEqual(_strip_think("<think>abc</think>Ola").strip(), "Ola")

    def test_sem_think_inalterado(self):
        self.assertEqual(_strip_think("Ola"), "Ola")


class TestInstructorMode(unittest.TestCase):
    def test_json_e_tools(self):
        self.assertEqual(_instructor_mode("json"), instructor.Mode.JSON)
        self.assertEqual(_instructor_mode("tools"), instructor.Mode.TOOLS)

    def test_default_e_tools(self):
        # qualquer valor desconhecido cai em tools (comportamento atual do Brain)
        self.assertEqual(_instructor_mode(""), instructor.Mode.TOOLS)


class TestAnswer(unittest.TestCase):
    def test_ancora_no_contexto_e_remove_think(self):
        cap = {}
        b = Brain("qwen3:4b", prompts=_PROMPTS)
        b._raw_client = _fake_client(
            content="<think>hmm</think>O prazo e sexta.", capture=cap)
        out = b.answer("qual o prazo?", "o prazo do projeto e sexta")
        self.assertEqual(out, "O prazo e sexta.")
        system = cap["messages"][0]["content"]
        self.assertIn("PERSONA_X", system)   # persona prefixada
        self.assertIn("ANSWER_X", system)    # prompt da tarefa
        user_msg = cap["messages"][-1]["content"]
        self.assertIn("o prazo do projeto e sexta", user_msg)
        self.assertIn("qual o prazo?", user_msg)

    def test_fallback_sem_extra_body(self):
        cap = {}
        b = Brain("qwen3:4b", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="ok", capture=cap, raise_on_extra=True)
        out = b.answer("p", "c")
        self.assertEqual(out, "ok")
        # a chamada que venceu foi a SEM extra_body
        self.assertNotIn("extra_body", cap)


class TestSummarize(unittest.TestCase):
    def test_persona_e_prompt_de_resumo_no_system(self):
        cap = {}
        b = Brain("qwen3:4b", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="<think>x</think>Voce fez X.", capture=cap)
        out = b.summarize("semana", "[nota] fiz X")
        self.assertEqual(out, "Voce fez X.")
        system = cap["messages"][0]["content"]
        self.assertIn("PERSONA_X", system)
        self.assertIn("RESUMO_X", system)
        self.assertIn("[nota] fiz X", cap["messages"][-1]["content"])
        self.assertIn("semana", cap["messages"][-1]["content"])


class TestDecideHistory(unittest.TestCase):
    def test_history_entra_no_system_prompt(self):
        cap = {}
        canned = Decisao(escolha=Responder(texto="ok"))
        b = Brain("qwen3:4b", prompts=_PROMPTS)
        b._client = _fake_client(capture=cap, canned=canned)
        got = b.decide("cria outra igual",
                       history=[("cria uma nota de reuniao", "criar_nota")])
        self.assertIs(got, canned)
        system = cap["messages"][0]["content"]
        self.assertIn("PERSONA_X", system)     # persona prefixada
        self.assertIn("DECIDE_X", system)      # prompt de roteamento
        self.assertIn("Conversa recente", system)
        self.assertIn("criar_nota", system)

    def test_sem_history_prompt_limpo(self):
        cap = {}
        canned = Decisao(escolha=Responder(texto="ok"))
        b = Brain("qwen3:4b", prompts=_PROMPTS)
        b._client = _fake_client(capture=cap, canned=canned)
        b.decide("oi")
        self.assertNotIn("Conversa recente", cap["messages"][0]["content"])


class TestWarm(unittest.TestCase):
    """warm() e best-effort (nunca levanta), mas NAO pode ser mudo: um 404 aqui
    significa que o modelo nao foi puxado e toda fala vai falhar depois. Aconteceu
    no Windows: boot silencioso, 404 so na 1a frase."""

    def _warm_com(self, exc):
        """Roda warm() com um urlopen falso que levanta `exc` (None = sucesso)."""
        import urllib.request

        def fake_urlopen(req, timeout=None):
            if exc is not None:
                raise exc
            return _CtxResp()

        with unittest.mock.patch.object(urllib.request, "urlopen", fake_urlopen):
            return Brain("qwen3:4b", prompts=_PROMPTS).warm()

    def test_sucesso_sem_aviso(self):
        self.assertIsNone(self._warm_com(None))

    def test_404_avisa_com_o_comando_do_pull(self):
        aviso = self._warm_com(urllib.error.HTTPError(
            "http://x/api/generate", 404, "Not Found", {}, None))
        self.assertIn("qwen3:4b", aviso)
        self.assertIn("ollama pull qwen3:4b", aviso)

    def test_ollama_fora_do_ar_avisa_sem_levantar(self):
        aviso = self._warm_com(OSError("connection refused"))
        self.assertIn("Ollama", aviso)
        self.assertIn("connection refused", aviso)

    def test_outro_http_avisa_o_codigo(self):
        aviso = self._warm_com(urllib.error.HTTPError(
            "http://x/api/generate", 500, "Boom", {}, None))
        self.assertIn("500", aviso)


class _CtxResp:
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def read(self): return b"{}"


if __name__ == "__main__":
    unittest.main()
