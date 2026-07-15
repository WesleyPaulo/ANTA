"""O schema e a fronteira que o instructor forca no LLM. Aqui garantimos que a
uniao discriminada 'Decisao' desserializa cada tipo de acao corretamente."""
import unittest

from anta.actions.schema import (
    AbrirApp, AdicionarTarefa, CriarDocumento, CriarNota, Decisao, Responder,
)


class TestDecisaoDiscriminada(unittest.TestCase):
    def test_criar_nota(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "criar_nota", "titulo": "T", "conteudo": "C"}})
        self.assertIsInstance(d.escolha, CriarNota)
        self.assertEqual(d.escolha.titulo, "T")

    def test_criar_documento_formato_default_md(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "criar_documento", "titulo": "T", "conteudo": "C"}})
        self.assertIsInstance(d.escolha, CriarDocumento)
        self.assertEqual(d.escolha.formato, "md")

    def test_adicionar_tarefa_prazo_opcional(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "adicionar_tarefa", "texto": "comprar cafe"}})
        self.assertIsInstance(d.escolha, AdicionarTarefa)
        self.assertIsNone(d.escolha.prazo)

    def test_abrir_app(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "abrir_app", "nome": "obsidian"}})
        self.assertIsInstance(d.escolha, AbrirApp)

    def test_responder(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "responder", "texto": "oi"}})
        self.assertIsInstance(d.escolha, Responder)

    def test_acao_invalida_rejeitada(self):
        with self.assertRaises(Exception):
            Decisao.model_validate({"escolha": {"acao": "rm_rf", "alvo": "/"}})


if __name__ == "__main__":
    unittest.main()
