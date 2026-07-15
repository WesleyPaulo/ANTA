"""Testes das pecas que o desacoplamento introduziu: a whitelist isolada e a
exaustividade do registro de handlers."""
import typing
import unittest

from anta.actions import apps, registry
from anta.actions.schema import Acao


class TestWhitelist(unittest.TestCase):
    def test_lookup_case_insensitive(self):
        self.assertEqual(apps.lookup("Obsidian"), ["obsidian"])
        self.assertEqual(apps.lookup("  FIREFOX "), ["firefox"])

    def test_lookup_fora_da_whitelist(self):
        self.assertIsNone(apps.lookup("rm"))

    def test_lookup_devolve_copia_defensiva(self):
        got = apps.lookup("obsidian")
        got.append("--x")
        self.assertEqual(apps.APP_WHITELIST["obsidian"], ["obsidian"])

    def test_permitidos_ordenado(self):
        p = apps.permitidos()
        self.assertIn("obsidian", p)
        nomes = [n.strip() for n in p.split(",")]
        self.assertEqual(nomes, sorted(nomes))


class TestRegistroExaustivo(unittest.TestCase):
    def test_toda_acao_tem_handler(self):
        for tipo in typing.get_args(Acao):
            self.assertIn(tipo, registry.HANDLERS,
                          f"{tipo.__name__} nao tem handler em registry.HANDLERS")

    def test_sem_handler_orfao(self):
        tipos_acao = set(typing.get_args(Acao))
        for tipo in registry.HANDLERS:
            self.assertIn(tipo, tipos_acao,
                          f"{tipo.__name__} em HANDLERS nao existe na uniao Acao")


if __name__ == "__main__":
    unittest.main()
