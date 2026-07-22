"""Testes da camada de atalho (anta.platform.hotkey).

Focam no que a v0.2 mexeu: quoting do interpretador, conversao de tecla para o
KDE, automacao best-effort no Wayland e a garantia de que o caminho manual
sempre aparece (nunca fica pior que antes).
"""
import sys
import unittest
from unittest import mock

from anta.platform import hotkey
from anta.platform.detect import Environment


class TestDefaultCommand(unittest.TestCase):
    def test_aspa_interpretador(self):
        cmd = hotkey.default_command()
        self.assertTrue(cmd.startswith('"'))
        self.assertIn('" -m anta', cmd)
        self.assertIn(sys.executable, cmd)

    def test_frozen_nao_usa_dash_m(self):
        # no build PyInstaller o sys.executable JA e o exe da ANTA -> sem `-m anta`
        with mock.patch.object(sys, "frozen", True, create=True):
            cmd = hotkey.default_command()
        self.assertNotIn("-m anta", cmd)
        self.assertEqual(cmd, f'"{sys.executable}"')


class TestKdeKey(unittest.TestCase):
    def test_conversao_basica(self):
        self.assertEqual(hotkey._kde_key("ctrl+alt+space"), "Ctrl+Alt+Space")

    def test_meta_e_tecla_simples(self):
        self.assertEqual(hotkey._kde_key("super+m"), "Meta+M")

    def test_case_insensitive(self):
        self.assertEqual(hotkey._kde_key("CTRL+Alt+SPACE"), "Ctrl+Alt+Space")


class TestKdeAutoshortcut(unittest.TestCase):
    def test_sem_kwriteconfig_retorna_false(self):
        with mock.patch("shutil.which", return_value=None):
            self.assertFalse(
                hotkey._kde_autoshortcut('"x" -m anta toggle', "ctrl+alt+space"))

    def test_falha_de_subprocess_cai_em_false(self):
        with mock.patch("shutil.which", return_value="/usr/bin/kwriteconfig6"), \
             mock.patch.object(hotkey, "_kde_launcher_desktop",
                               return_value="anta-toggle.desktop"), \
             mock.patch("subprocess.run", side_effect=OSError):
            self.assertFalse(
                hotkey._kde_autoshortcut('"x" -m anta toggle', "ctrl+alt+space"))

    def test_sucesso_retorna_true(self):
        with mock.patch("shutil.which", return_value="/usr/bin/kwriteconfig6"), \
             mock.patch.object(hotkey, "_kde_launcher_desktop",
                               return_value="anta-toggle.desktop"), \
             mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            self.assertTrue(
                hotkey._kde_autoshortcut('"x" -m anta toggle', "ctrl+alt+space"))


class TestSetupHotkeyCompositor(unittest.TestCase):
    _env = Environment(os="linux", session="wayland", desktop="KDE")

    def test_compositor_sempre_mostra_manual(self):
        with mock.patch.object(hotkey, "_autostart_linux", return_value=True), \
             mock.patch.object(hotkey, "_kde_autoshortcut", return_value=False):
            out = hotkey.setup_hotkey(self._env, "x", "ctrl+alt+space")
        self.assertIn("Atalhos", out)  # instrucao manual presente

    def test_compositor_prefixa_sucesso(self):
        with mock.patch.object(hotkey, "_autostart_linux", return_value=True), \
             mock.patch.object(hotkey, "_kde_autoshortcut", return_value=True):
            out = hotkey.setup_hotkey(self._env, "x", "ctrl+alt+space")
        self.assertIn("registrado no KDE", out)
        self.assertIn("Atalhos", out)  # manual continua ali como garantia


class TestAutostartWindows(unittest.TestCase):
    def test_reg_add_chamado(self):
        with mock.patch("subprocess.run") as run:
            run.return_value = mock.Mock(returncode=0)
            ok = hotkey._autostart_windows('"C:\\py.exe" -m anta run')
        self.assertTrue(ok)
        argv = run.call_args[0][0]
        self.assertEqual(argv[0], "reg")
        self.assertIn("HKCU\\Software\\Microsoft\\Windows\\CurrentVersion\\Run", argv)


if __name__ == "__main__":
    unittest.main()
