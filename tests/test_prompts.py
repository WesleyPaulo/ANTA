"""Prompts externalizados: padroes no codigo, overrides via prompts.toml (campo a campo)."""
import tempfile
import unittest
from pathlib import Path

from anta.core import prompts
from anta.core.prompts import DECIDE


class TestLoadPrompts(unittest.TestCase):
    def test_padroes_quando_ausente(self):
        with tempfile.TemporaryDirectory() as d:
            p = prompts.load_prompts(Path(d) / "nao-existe.toml")
        self.assertEqual(p.persona, prompts.PERSONA)
        self.assertEqual(p.decide, prompts.DECIDE)

    def test_override_por_campo(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            f.write_text('persona = "Seja um pirata."\n', encoding="utf-8")
            p = prompts.load_prompts(f)
        self.assertEqual(p.persona, "Seja um pirata.")   # sobrescrito
        self.assertEqual(p.answer, prompts.ANSWER)        # os outros caem no padrao

    def test_chave_vazia_ou_invalida_cai_no_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            f.write_text('persona = "   "\nresumo = 42\n', encoding="utf-8")
            p = prompts.load_prompts(f)
        self.assertEqual(p.persona, prompts.PERSONA)  # string vazia ignorada
        self.assertEqual(p.resumo, prompts.RESUMO)    # tipo errado ignorado

    def test_toml_invalido_cai_no_padrao(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            f.write_text("isso ] nao [ e toml", encoding="utf-8")
            p = prompts.load_prompts(f)
        self.assertEqual(p.persona, prompts.PERSONA)


class TestFronteiraConsultarResponder(unittest.TestCase):
    """Caso real: 'Voce poderia falar mais sobre a Revolucao Industrial?' foi roteado pra
    `consultar` e morreu num 'nao encontrei nas suas notas'. O prompt dizia o que consultar
    E, mas nao o que ela NAO e — e um 4B le 'fale sobre X' como 'busque X'.

    Nao da pra testar a decisao do LLM sem hardware; travamos as instrucoes que a guiam.
    """

    def test_consultar_exige_referencia_ao_material_do_usuario(self):
        self.assertIn("minhas notas", DECIDE)
        self.assertIn("eu anotei", DECIDE)

    def test_consultar_exclui_assunto_do_mundo(self):
        self.assertIn("assunto do MUNDO", DECIDE)
        self.assertIn("NAO consultar", DECIDE)

    def test_desempate_favorece_responder(self):
        # o custo dos erros e assimetrico: responder errado ainda responde algo util;
        # consultar errado da um beco sem saida ("nao encontrei nas suas notas")
        self.assertIn("Na duvida entre consultar e responder, escolha responder", DECIDE)

    def test_few_shot_cobre_os_dois_casos_reais(self):
        self.assertIn("Revolucao Industrial", DECIDE)      # mundo -> responder
        self.assertIn("perspicaz em ingles", DECIDE)       # traducao -> responder
        self.assertIn("o que eu tinha anotado sobre o contrato", DECIDE)  # notas -> consultar


class TestWriteDefaultPrompts(unittest.TestCase):
    def test_escreve_e_rele(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            prompts.write_default_prompts(f)
            self.assertTrue(f.exists())
            p = prompts.load_prompts(f)          # round-trip pelos padroes
            self.assertEqual(p.decide, prompts.DECIDE)
            self.assertEqual(p.persona, prompts.PERSONA)

    def test_sai_todo_comentado_e_nao_congela_o_padrao(self):
        """Regressao: o arquivo saia com uma COPIA dos padroes e, como o TOML sobrepoe o
        codigo, o snapshot da instalacao ganhava PARA SEMPRE — melhorias no roteamento
        nunca chegavam em quem ja tinha instalado, sem nenhum aviso."""
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            prompts.write_default_prompts(f)
            texto = f.read_text(encoding="utf-8")
            # nenhuma linha ativa: toda linha nao-vazia e comentario
            ativas = [ln for ln in texto.splitlines() if ln.strip() and not ln.startswith("#")]
            self.assertEqual(ativas, [], f"prompts.toml tem chave ativa: {ativas}")
            # e o TOML nao sobrepoe nada -> o padrao do codigo vale
            self.assertEqual(prompts.load_prompts(f), prompts.Prompts())

    def test_padroes_ficam_visiveis_como_referencia(self):
        # comentado, mas o usuario tem que conseguir ler o que da pra editar
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            prompts.write_default_prompts(f)
            texto = f.read_text(encoding="utf-8")
            for chave in ("persona", "decide", "answer", "resumo"):
                self.assertIn(f"# {chave} =", texto)
            self.assertIn("Revolucao Industrial", texto)  # o corpo do decide esta la

    def test_descomentar_um_campo_ainda_sobrepoe(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            prompts.write_default_prompts(f)
            f.write_text(f.read_text(encoding="utf-8") + '\npersona = "sou brusca"\n',
                         encoding="utf-8")
            p = prompts.load_prompts(f)
            self.assertEqual(p.persona, "sou brusca")   # o que o usuario escolheu
            self.assertEqual(p.decide, prompts.DECIDE)  # o resto segue o codigo

    def test_nao_sobrescreve_edicao(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            f.write_text('persona = "meu texto"\n', encoding="utf-8")
            prompts.write_default_prompts(f)      # nao deve clobberar
            self.assertEqual(prompts.load_prompts(f).persona, "meu texto")


if __name__ == "__main__":
    unittest.main()
