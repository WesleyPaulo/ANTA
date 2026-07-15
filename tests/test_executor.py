import tempfile
import unittest
from pathlib import Path

from anta.actions.executor import ExecContext, execute
from anta.actions.schema import (
    AbrirApp, AdicionarTarefa, CriarDocumento, CriarNota, Decisao, Responder,
)


def _dec(acao):
    return Decisao(escolha=acao)


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


if __name__ == "__main__":
    unittest.main()
