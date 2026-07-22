"""Testes do launcher do exe empacotado (anta.gui.launcher).

Roteamento sem argv: 1a vez -> Configurador; ja configurado -> HUD. Com argv,
delega ao dispatch normal (o exe age como CLI).
"""
import sys
import unittest
from unittest import mock

from anta.gui import launcher


class TestChooseDefault(unittest.TestCase):
    def test_nao_configurado_abre_config(self):
        cfg = mock.Mock(configured=False)
        with mock.patch("anta.core.config.load_user_config", return_value=cfg):
            self.assertEqual(launcher.choose_default(), "config")

    def test_configurado_abre_app(self):
        cfg = mock.Mock(configured=True)
        with mock.patch("anta.core.config.load_user_config", return_value=cfg):
            self.assertEqual(launcher.choose_default(), "app")


class TestMain(unittest.TestCase):
    def setUp(self):
        self._argv = sys.argv[:]

    def tearDown(self):
        sys.argv = self._argv

    def test_sem_argv_injeta_o_default(self):
        sys.argv = ["anta-exe"]
        with mock.patch.object(launcher, "choose_default", return_value="config"), \
             mock.patch("anta.__main__.main") as dispatch:
            launcher.main()
        self.assertEqual(sys.argv, ["anta-exe", "config"])  # injetou o subcomando
        dispatch.assert_called_once()

    def test_com_argv_delega_sem_mexer(self):
        sys.argv = ["anta-exe", "run"]
        with mock.patch.object(launcher, "choose_default") as choose, \
             mock.patch("anta.__main__.main") as dispatch:
            launcher.main()
        self.assertEqual(sys.argv, ["anta-exe", "run"])  # nao injeta nada
        choose.assert_not_called()
        dispatch.assert_called_once()


if __name__ == "__main__":
    unittest.main()
