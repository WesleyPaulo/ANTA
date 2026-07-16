import tempfile
import unittest
from pathlib import Path

from anta.actions.executor import ExecContext, execute
from anta.actions.schema import (
    AbrirApp, AdicionarTarefa, BuscarWeb, Consultar, CriarDocumento, CriarNota,
    Decisao, Lembrar, Responder, Resumir,
)
from anta.core.websearch import Result


def _dec(acao):
    return Decisao(escolha=acao)


class _Chunk:
    def __init__(self, texto):
        self.texto = texto


class _FakeRag:
    """Fake do RAG p/ handlers: devolve chunks fixos na consulta."""
    def __init__(self, chunks=None):
        self._chunks = chunks or []

    def query(self, pergunta, k=5):
        return list(self._chunks)


class TestExecutor(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.ctx = ExecContext(vault=Path(self._tmp.name), tts=False)

    def tearDown(self):
        self._tmp.cleanup()

    def test_criar_nota_escreve_md(self):
        msg = execute(_dec(CriarNota(titulo="Minha Ideia", conteudo="corpo")), self.ctx)
        arquivos = list(Path(self._tmp.name).glob("*.md"))
        self.assertEqual(len(arquivos), 1)
        texto = arquivos[0].read_text(encoding="utf-8")
        self.assertIn("Minha Ideia", texto)
        self.assertIn("corpo", texto)
        self.assertIn("Nota criada", msg)

    def test_criar_nota_nao_sobrescreve(self):
        execute(_dec(CriarNota(titulo="dup", conteudo="a")), self.ctx)
        execute(_dec(CriarNota(titulo="dup", conteudo="b")), self.ctx)
        self.assertEqual(len(list(Path(self._tmp.name).glob("*.md"))), 2)

    def test_criar_documento_md(self):
        msg = execute(_dec(CriarDocumento(titulo="Doc", conteudo="x", formato="md")),
                      self.ctx)
        self.assertIn("Documento criado", msg)

    def test_adicionar_tarefa_anexa(self):
        execute(_dec(AdicionarTarefa(texto="comprar cafe", prazo="amanha")), self.ctx)
        tarefas = (Path(self._tmp.name) / "tarefas.md").read_text(encoding="utf-8")
        self.assertIn("- [ ] comprar cafe", tarefas)
        self.assertIn("amanha", tarefas)

    def test_abrir_app_fora_da_whitelist(self):
        msg = execute(_dec(AbrirApp(nome="rm")), self.ctx)
        self.assertIn("whitelist", msg.lower())

    def test_responder_retorna_texto(self):
        msg = execute(_dec(Responder(texto="ola mundo")), self.ctx)
        self.assertEqual(msg, "ola mundo")

    def test_lembrar_escreve_em_memoria(self):
        # indexacao e no query (RAG.query reconcilia), nao no handler
        ctx = ExecContext(vault=Path(self._tmp.name), tts=False, rag=_FakeRag())
        msg = execute(_dec(Lembrar(fato="prefiro documentos em docx")), ctx)
        notas = list((Path(self._tmp.name) / "memoria").glob("*.md"))
        self.assertEqual(len(notas), 1)
        self.assertIn("prefiro documentos em docx", notas[0].read_text(encoding="utf-8"))
        self.assertIn("Vou lembrar", msg)

    def test_lembrar_sem_rag_ainda_grava(self):
        ctx = ExecContext(vault=Path(self._tmp.name), tts=False, rag=None)
        execute(_dec(Lembrar(fato="fato solto")), ctx)
        self.assertEqual(len(list((Path(self._tmp.name) / "memoria").glob("*.md"))), 1)

    def test_consultar_recupera_e_sintetiza(self):
        rag = _FakeRag([_Chunk("o prazo do projeto e sexta")])
        captura = {}

        def fake_answer(pergunta, contexto):
            captura["pergunta"] = pergunta
            captura["contexto"] = contexto
            return "O prazo e sexta."

        ctx = ExecContext(vault=Path(self._tmp.name), rag=rag, answer=fake_answer)
        msg = execute(_dec(Consultar(pergunta="qual o prazo?")), ctx)
        self.assertEqual(msg, "O prazo e sexta.")
        self.assertIn("prazo do projeto", captura["contexto"])
        self.assertEqual(captura["pergunta"], "qual o prazo?")

    def test_consultar_sem_resultado_nao_chama_llm(self):
        chamou = []
        ctx = ExecContext(vault=Path(self._tmp.name), rag=_FakeRag([]),
                          answer=lambda p, c: chamou.append(1) or "x")
        msg = execute(_dec(Consultar(pergunta="nada")), ctx)
        self.assertIn("Nao encontrei", msg)
        self.assertEqual(chamou, [])  # sem contexto => nem chama o LLM

    def test_consultar_rag_desativado(self):
        ctx = ExecContext(vault=Path(self._tmp.name), rag=None)
        msg = execute(_dec(Consultar(pergunta="x")), ctx)
        self.assertIn("desativada", msg.lower())

    def test_resumir_sintetiza_e_salva_em_resumos(self):
        vault = Path(self._tmp.name)
        (vault / "hoje.md").write_text("# Hoje\n\nescrevi a proposta", encoding="utf-8")
        captura = {}

        def fake_summarize(periodo, material):
            captura["periodo"] = periodo
            captura["material"] = material
            return "Hoje voce escreveu a proposta."

        ctx = ExecContext(vault=vault, summarize=fake_summarize)
        msg = execute(_dec(Resumir(periodo="dia")), ctx)
        self.assertEqual(msg, "Hoje voce escreveu a proposta.")
        self.assertIn("escrevi a proposta", captura["material"])
        self.assertEqual(captura["periodo"], "dia")
        resumos = list((vault / "resumos").glob("*.md"))
        self.assertEqual(len(resumos), 1)
        self.assertIn("Hoje voce escreveu a proposta.", resumos[0].read_text(encoding="utf-8"))

    def test_resumir_periodo_vazio_nao_chama_llm_nem_salva(self):
        chamou = []
        ctx = ExecContext(vault=Path(self._tmp.name),
                          summarize=lambda p, m: chamou.append(1) or "x")
        msg = execute(_dec(Resumir(periodo="dia")), ctx)  # vault vazio
        self.assertIn("Nao ha nada registrado", msg)
        self.assertEqual(chamou, [])
        self.assertFalse((Path(self._tmp.name) / "resumos").exists())

    def test_buscar_web_desativado(self):
        ctx = ExecContext(vault=Path(self._tmp.name), web_search=None)  # web off
        msg = execute(_dec(BuscarWeb(consulta="x")), ctx)
        self.assertIn("desativada", msg.lower())

    def test_buscar_web_sem_resultado(self):
        chamou = []
        ctx = ExecContext(vault=Path(self._tmp.name), web_search=lambda q: [],
                          answer=lambda p, c: chamou.append(1) or "x")
        msg = execute(_dec(BuscarWeb(consulta="nada")), ctx)
        self.assertIn("Nao consegui buscar", msg)
        self.assertEqual(chamou, [])  # sem resultado => nem chama o LLM

    def test_buscar_web_sintetiza_com_fontes(self):
        resultados = [Result("Titulo", "trecho relevante", "http://exemplo.com/a"),
                      Result("T2", "outro", "http://exemplo.com/b")]
        captura = {}

        def fake_answer(pergunta, contexto):
            captura["contexto"] = contexto
            return "A resposta sintetizada."

        ctx = ExecContext(vault=Path(self._tmp.name),
                          web_search=lambda q: resultados, answer=fake_answer)
        msg = execute(_dec(BuscarWeb(consulta="pergunta")), ctx)
        self.assertIn("A resposta sintetizada.", msg)
        self.assertIn("Fontes: http://exemplo.com/a", msg)   # rodape com as URLs
        self.assertIn("trecho relevante", captura["contexto"])  # contexto = resultados


if __name__ == "__main__":
    unittest.main()
