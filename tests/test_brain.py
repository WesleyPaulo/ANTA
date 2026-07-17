"""Testes do Brain sem Ollama: injetamos clients falsos em _client/_raw_client.

Cobrem: strip de <think> e ancoragem no contexto em answer(), fallback quando o
extra_body nao e aceito, e a injecao da janela de conversa no system prompt do decide().
"""
import unittest
import unittest.mock
import urllib.error
from datetime import datetime
from types import SimpleNamespace

import instructor

from anta.actions.schema import Decisao, Responder
from anta.core.brain import Brain, _instructor_mode, _strip_think
from anta.core.prompts import Prompts, now_line

_PROMPTS = Prompts(persona="PERSONA_X", decide="DECIDE_X", answer="ANSWER_X",
                   resumo="RESUMO_X", escrita="ESCRITA_X")


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
    def test_json_schema_json_e_tools(self):
        self.assertEqual(_instructor_mode("json_schema"), instructor.Mode.JSON_SCHEMA)
        self.assertEqual(_instructor_mode("json"), instructor.Mode.JSON)
        self.assertEqual(_instructor_mode("tools"), instructor.Mode.TOOLS)

    def test_default_e_json_schema(self):
        # o default MUDOU de tools p/ json_schema: o Ollama ignora tool_choice, entao
        # tools nunca obriga a chamada e o modelo conversa. Ver _instructor_mode.
        self.assertEqual(_instructor_mode(""), instructor.Mode.JSON_SCHEMA)
        self.assertEqual(_instructor_mode("qualquer-coisa"), instructor.Mode.JSON_SCHEMA)


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


class TestSemRaciocinio(unittest.TestCase):
    """Regressao do bug real: o Ollama LIGA o raciocinio sozinho em modelo que pensa,
    e raciocinio + tools quebrou o tool-calling (qwen3:4b escreveu a chamada como
    texto e o instructor morreu com 'No tool calls found (mode: TOOLS)')."""

    def test_decide_pede_sem_raciocinio(self):
        cap = {}
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._client = _fake_client(capture=cap, canned=Decisao(escolha=Responder(texto="ok")))
        b.decide("oi")
        self.assertEqual(cap["extra_body"], {"reasoning_effort": "none"})

    def test_decide_tem_retry(self):
        cap = {}
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._client = _fake_client(capture=cap, canned=Decisao(escolha=Responder(texto="ok")))
        b.decide("oi")
        self.assertGreater(cap["max_retries"], 1)  # modelo pequeno erra o schema as vezes

    def test_complete_pede_sem_raciocinio(self):
        # e NAO o chat_template_kwargs de antes, que o Ollama descartava em silencio
        cap = {}
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="r", capture=cap)
        b.answer("p", "ctx")
        self.assertEqual(cap["extra_body"], {"reasoning_effort": "none"})
        self.assertNotIn("chat_template_kwargs", cap.get("extra_body", {}))

    def test_complete_cai_no_fallback_se_o_ollama_for_antigo(self):
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="resp", raise_on_extra=True)
        self.assertEqual(b.answer("p", "ctx"), "resp")  # sem extra_body, mas responde


class TestConversaViraResponder(unittest.TestCase):
    """Regressao real: 'e ai' -> o modelo respondeu 'E ai! Como vai?' em texto, sem
    tool call (o Ollama nao aceita tool_choice, entao a ferramenta nunca e obrigatoria).
    O instructor levantava, e ainda por cima o reask_tools dele crashava iterando
    tool_calls=None. A resposta certa existia; era so resgatar do envelope errado."""

    def _erro(self, content, tool_calls=None):
        msg = SimpleNamespace(content=content, tool_calls=tool_calls)
        comp = SimpleNamespace(choices=[SimpleNamespace(message=msg)])
        e = RuntimeError("No tool calls or function call found in response (mode: TOOLS)")
        e.last_completion = comp
        return e

    def _brain_que_falha(self, erro):
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        def create(**kwargs):
            raise erro
        b._client = SimpleNamespace(
            chat=SimpleNamespace(completions=SimpleNamespace(create=create)))
        return b

    def test_texto_solto_vira_responder(self):
        b = self._brain_que_falha(self._erro("E ai! Como vai?"))
        d = b.decide("e ai")
        self.assertIsInstance(d.escolha, Responder)
        self.assertEqual(d.escolha.texto, "E ai! Como vai?")

    def test_think_e_removido_do_resgate(self):
        b = self._brain_que_falha(self._erro("<think>hmm</think>Ola!"))
        self.assertEqual(b.decide("oi").escolha.texto, "Ola!")

    def test_falha_com_tool_call_nao_e_resgatada(self):
        # houve tool call: o erro foi schema invalido, nao conversa -> levanta
        erro = self._erro("texto qualquer", tool_calls=[SimpleNamespace(id="1")])
        with self.assertRaises(RuntimeError):
            self._brain_que_falha(erro).decide("oi")

    def test_erro_sem_completion_levanta(self):
        with self.assertRaises(RuntimeError):
            self._brain_que_falha(RuntimeError("ollama fora do ar")).decide("oi")

    def test_content_vazio_levanta(self):
        with self.assertRaises(RuntimeError):
            self._brain_que_falha(self._erro("   ")).decide("oi")

    def test_json_quebrado_nao_e_falado(self):
        # nos modos json/json_schema o content e JSON; se falhou, ta malformado.
        # Falar '{"escolha": {"acao"' em voz alta e pior que reportar o erro.
        with self.assertRaises(RuntimeError):
            self._brain_que_falha(self._erro('{"escolha": {"acao"')).decide("oi")


class TestContextoDeTempo(unittest.TestCase):
    """'que dia e hoje?' caia em buscar_web: o modelo nao tinha a data e a persona
    manda 'nunca invente'. Com a web off, era um beco sem saida."""

    def test_now_line_em_portugues_sem_depender_de_locale(self):
        linha = now_line(datetime(2026, 7, 16, 14, 32))
        self.assertIn("14:32", linha)
        self.assertIn("quinta-feira", linha)
        self.assertIn("16 de julho de 2026", linha)

    def test_decide_injeta_a_data_no_system(self):
        cap = {}
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._client = _fake_client(capture=cap, canned=Decisao(escolha=Responder(texto="ok")))
        b.decide("que dia e hoje")
        self.assertIn("Contexto de tempo", cap["messages"][0]["content"])

    def test_answer_tambem_recebe_a_data(self):
        cap = {}
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="r", capture=cap)
        b.answer("p", "ctx")
        self.assertIn("Contexto de tempo", cap["messages"][0]["content"])


class TestWrite(unittest.TestCase):
    """A nota do Fordismo saiu rasa porque a PERSONA ('respostas FALADAS: frases curtas,
    sem markdown, sem listas') era prefixada em tudo — inclusive ao escrever uma nota, que
    e LIDA. O modelo obedeceu. write() e a chamada de redacao, sem essa persona."""

    def _brain(self, cap):
        b = Brain("qwen3:4b-instruct", prompts=_PROMPTS)
        b._raw_client = _fake_client(content="corpo redigido", capture=cap)
        return b

    def test_nao_leva_a_persona_de_voz(self):
        cap = {}
        self._brain(cap).write("Fordismo", "esboco")
        system = cap["messages"][0]["content"]
        self.assertNotIn("PERSONA_X", system)   # <- o bug: a persona de fala vazava aqui
        self.assertIn("ESCRITA_X", system)

    def test_titulo_e_esboco_chegam_no_pedido(self):
        cap = {}
        self._brain(cap).write("Fordismo", "origem e consequencias")
        user = cap["messages"][-1]["content"]
        self.assertIn("Fordismo", user)
        self.assertIn("origem e consequencias", user)

    def test_historico_da_conversa_entra(self):
        # "anota ISSO numa nota" so faz sentido se a redacao ve o que se conversava
        cap = {}
        self._brain(cap).write("Fordismo", "esboco",
                               history=[("O que foi o Fordismo?", "responder")])
        self.assertIn("O que foi o Fordismo?", cap["messages"][0]["content"])

    def test_temperatura_maior_que_a_do_roteamento(self):
        # redacao != classificacao: 0.1 e otimo pra rotear e pessimo pra escrever
        cap = {}
        self._brain(cap).write("X", "y")
        self.assertGreater(cap["temperature"], 0.1)

    def test_esboco_vazio_nao_gera_secao_de_rascunho(self):
        cap = {}
        self._brain(cap).write("X", "   ")
        self.assertNotIn("Rascunho", cap["messages"][-1]["content"])


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
