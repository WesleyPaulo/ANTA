"""Prompts externalizados: padroes no codigo, overrides via prompts.toml (campo a campo)."""
import tempfile
import unittest
from pathlib import Path

from anta.core import prompts


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


class TestWriteDefaultPrompts(unittest.TestCase):
    def test_escreve_e_rele(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            prompts.write_default_prompts(f)
            self.assertTrue(f.exists())
            p = prompts.load_prompts(f)          # round-trip pelos padroes
            self.assertEqual(p.decide, prompts.DECIDE)
            self.assertEqual(p.persona, prompts.PERSONA)

    def test_nao_sobrescreve_edicao(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "prompts.toml"
            f.write_text('persona = "meu texto"\n', encoding="utf-8")
            prompts.write_default_prompts(f)      # nao deve clobberar
            self.assertEqual(prompts.load_prompts(f).persona, "meu texto")


if __name__ == "__main__":
    unittest.main()
