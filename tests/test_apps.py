"""Testes das pecas que o desacoplamento introduziu: a whitelist (agora
cross-platform) e a exaustividade do registro de handlers."""
import typing
import unittest

from anta.actions import apps, registry
from anta.actions.schema import Acao


class TestWhitelist(unittest.TestCase):
    def test_lookup_case_insensitive_e_espacos(self):
        self.assertIsNotNone(apps.lookup("Obsidian"))
        self.assertEqual(apps.lookup("  OBSIDIAN "), apps.lookup("obsidian"))

    def test_apelido_resolve_para_o_canonico(self):
        self.assertEqual(apps.lookup("vscode"), apps.lookup("code"))
        self.assertEqual(apps.lookup("browser"), apps.lookup("navegador"))

    def test_lookup_fora_da_whitelist(self):
        self.assertIsNone(apps.lookup("rm"))
        self.assertIsNone(apps.lookup("qualquer coisa"))

    def test_lookup_devolve_copia_defensiva(self):
        a = apps.lookup("obsidian")
        a.append("--malicioso")
        self.assertNotIn("--malicioso", apps.lookup("obsidian"))

    def test_permitidos_ordenado_e_com_apelidos(self):
        p = apps.permitidos()
        self.assertIn("obsidian", p)
        self.assertIn("vscode", p)  # apelido tambem aparece
        nomes = [n.strip() for n in p.split(",")]
        self.assertEqual(nomes, sorted(nomes))


class TestResolucaoWhitelist(unittest.TestCase):
    """Toda entrada tem que resolver para um argv bem-formado NESTE SO."""

    def test_todo_app_tem_argv_no_so_atual(self):
        for nome in apps._APPS:
            argv = apps.lookup(nome)
            self.assertIsInstance(argv, list, f"{nome} sem argv no SO atual")
            self.assertTrue(argv and isinstance(argv[0], str),
                            f"{nome}: argv malformado ({argv!r})")

    def test_apelidos_apontam_para_apps_existentes(self):
        for alias, canonico in apps._ALIASES.items():
            self.assertIn(canonico, apps._APPS,
                          f"apelido '{alias}' aponta para '{canonico}' inexistente")

    def test_todo_app_cobre_os_tres_sos(self):
        for nome, por_so in apps._APPS.items():
            self.assertEqual(set(por_so), {"linux", "darwin", "windows"},
                             f"{nome} nao cobre os 3 SOs")


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
