"""O schema e a fronteira que o instructor forca no LLM. Aqui garantimos que a
uniao discriminada 'Decisao' desserializa cada tipo de acao corretamente."""
import unittest

from anta.actions.schema import (
    AbrirApp, AdicionarTarefa, BuscarWeb, Consultar, CriarDocumento, CriarNota,
    Decisao, Lembrar, Responder, Resumir,
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

    def test_lembrar(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "lembrar", "fato": "prefiro docx"}})
        self.assertIsInstance(d.escolha, Lembrar)
        self.assertEqual(d.escolha.fato, "prefiro docx")

    def test_consultar(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "consultar", "pergunta": "qual o prazo do projeto?"}})
        self.assertIsInstance(d.escolha, Consultar)

    def test_resumir_periodo(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "resumir", "periodo": "semana"}})
        self.assertIsInstance(d.escolha, Resumir)
        self.assertEqual(d.escolha.periodo, "semana")

    def test_resumir_periodo_default_dia(self):
        d = Decisao.model_validate({"escolha": {"acao": "resumir"}})
        self.assertEqual(d.escolha.periodo, "dia")

    def test_resumir_periodo_invalido_rejeitado(self):
        with self.assertRaises(Exception):
            Decisao.model_validate({"escolha": {"acao": "resumir", "periodo": "ano"}})

    def test_buscar_web(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "buscar_web", "consulta": "noticias de hoje"}})
        self.assertIsInstance(d.escolha, BuscarWeb)
        self.assertEqual(d.escolha.consulta, "noticias de hoje")

    def test_acao_invalida_rejeitada(self):
        with self.assertRaises(Exception):
            Decisao.model_validate({"escolha": {"acao": "rm_rf", "alvo": "/"}})


class TestCanalMemoria(unittest.TestCase):
    def test_memoria_default_none(self):
        d = Decisao.model_validate(
            {"escolha": {"acao": "responder", "texto": "oi"}})
        self.assertIsNone(d.memoria)

    def test_memoria_preenchida_convive_com_a_acao(self):
        d = Decisao.model_validate({
            "escolha": {"acao": "criar_documento", "titulo": "Contrato", "conteudo": "..."},
            "memoria": "cliente: Ricardo",
        })
        self.assertIsInstance(d.escolha, CriarDocumento)
        self.assertEqual(d.memoria, "cliente: Ricardo")


class TestSchemaParaGramatica(unittest.TestCase):
    """O schema vira gramatica GBNF no Ollama (structured='json_schema'), e campo fora de
    `required` vira OPCIONAL na gramatica. Como todo `acao` tem default, o pydantic o
    deixava fora de required: o modelo podia omitir o discriminador, e `Resumir` (todos os
    campos com default) degenerava no valido-e-inutil {"escolha": {}}."""

    def test_acao_e_obrigatorio_em_todas_as_acoes(self):
        defs = Decisao.model_json_schema()["$defs"]
        self.assertEqual(len(defs), 9)
        for nome, d in defs.items():
            self.assertIn("acao", d.get("required", []), f"{nome}: 'acao' pode ser omitido")

    def test_resumir_nao_aceita_objeto_vazio(self):
        req = Decisao.model_json_schema()["$defs"]["Resumir"]["required"]
        self.assertEqual(req, ["acao"])  # antes: [] -> {"escolha": {}} passava na gramatica

    def test_default_em_python_continua_funcionando(self):
        # o fix e so no schema: nao queremos poluir o codigo com acao='responder'
        self.assertEqual(Responder(texto="oi").acao, "responder")
        self.assertEqual(Resumir().periodo, "dia")

    def test_campos_realmente_opcionais_seguem_opcionais(self):
        # so o discriminador e forcado; formato/periodo tem default de verdade
        defs = Decisao.model_json_schema()["$defs"]
        self.assertNotIn("formato", defs["CriarDocumento"]["required"])
        self.assertNotIn("periodo", defs["Resumir"]["required"])


if __name__ == "__main__":
    unittest.main()
