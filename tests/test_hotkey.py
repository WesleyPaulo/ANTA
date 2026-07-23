"""Testes da camada de atalho (anta.platform.hotkey).

Focam no que a v0.2 mexeu: quoting do interpretador, conversao de tecla para o
KDE, automacao best-effort no Wayland e a garantia de que o caminho manual
sempre aparece (nunca fica pior que antes).
"""
import sys
import tempfile
import unittest
from pathlib import Path
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


class TestSubcomandoDoLogin(unittest.TestCase):
    """Regressao v0.4.3: o login subia `anta run` — headless. A ANTA carregava o
    Whisper e fixava o LLM na VRAM sem janela, sem bandeja e sem console: de fora,
    memoria ocupada e nada na tela."""

    def test_com_hud_sobe_o_app(self):
        with mock.patch.object(hotkey, "hud_available", return_value=True):
            self.assertEqual(hotkey.autostart_subcommand(), "app")

    def test_sem_hud_cai_no_daemon(self):
        # dev sem `npm run build`: `anta app` morreria no boot; melhor o headless
        with mock.patch.object(hotkey, "hud_available", return_value=False):
            self.assertEqual(hotkey.autostart_subcommand(), "run")

    def test_setup_hotkey_grava_o_app_no_login(self):
        env = Environment(os="windows", session="", desktop="")
        with mock.patch.object(hotkey, "hud_available", return_value=True), \
             mock.patch.object(hotkey, "_autostart_windows", return_value=True) as auto:
            hotkey.setup_hotkey(env, '"C:\\anta.exe"')
        auto.assert_called_once_with('"C:\\anta.exe" app')

    def test_subcomando_explicito_vence(self):
        env = Environment(os="linux", session="x11", desktop="GNOME")
        with mock.patch.object(hotkey, "_autostart_linux", return_value=True) as auto:
            hotkey.setup_hotkey(env, '"py" -m anta', subcommand="run")
        auto.assert_called_once_with('"py" -m anta run')

    def test_wayland_tambem_sobe_o_hud(self):
        # o HUD tambem grava o pidfile, entao o `anta toggle` do KDE continua valendo
        env = Environment(os="linux", session="wayland", desktop="KDE")
        with mock.patch.object(hotkey, "hud_available", return_value=True), \
             mock.patch.object(hotkey, "_autostart_linux", return_value=True) as auto, \
             mock.patch.object(hotkey, "_kde_autoshortcut", return_value=False):
            hotkey.setup_hotkey(env, '"py" -m anta', "ctrl+alt+space")
        auto.assert_called_once_with('"py" -m anta app')


class TestRepairAutostart(unittest.TestCase):
    """Quem instalou antes ja tem `... run` gravado no login; so mudar o codigo nao
    conserta a maquina de ninguem. O `anta run` migra a propria entrada."""

    def test_migra_run_para_app(self):
        with mock.patch.object(hotkey, "current_autostart", return_value='"C:\\anta.exe" run'), \
             mock.patch.object(hotkey, "hud_available", return_value=True), \
             mock.patch.object(sys, "platform", "win32"), \
             mock.patch.object(hotkey, "_autostart_windows", return_value=True) as auto:
            msg = hotkey.repair_autostart()
        auto.assert_called_once_with('"C:\\anta.exe" app')
        self.assertIn("inicializacao", msg)

    def test_ja_no_app_e_noop(self):
        with mock.patch.object(hotkey, "current_autostart", return_value='"C:\\anta.exe" app'), \
             mock.patch.object(hotkey, "hud_available", return_value=True), \
             mock.patch.object(hotkey, "_autostart_windows") as auto:
            self.assertIsNone(hotkey.repair_autostart())
        auto.assert_not_called()

    def test_sem_entrada_nao_cria(self):
        # quem nunca ligou o autostart nao ganha um item de login de brinde
        with mock.patch.object(hotkey, "current_autostart", return_value=None), \
             mock.patch.object(hotkey, "_autostart_linux") as auto:
            self.assertIsNone(hotkey.repair_autostart())
        auto.assert_not_called()

    def test_sem_hud_nao_migra(self):
        with mock.patch.object(hotkey, "current_autostart", return_value='"py" -m anta run'), \
             mock.patch.object(hotkey, "hud_available", return_value=False), \
             mock.patch.object(hotkey, "_autostart_linux") as auto:
            self.assertIsNone(hotkey.repair_autostart())
        auto.assert_not_called()

    def test_le_o_desktop_do_linux(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "anta.desktop"
            path.write_text("[Desktop Entry]\nType=Application\nExec=\"py\" -m anta run\n",
                            encoding="utf-8")
            with mock.patch.object(sys, "platform", "linux"), \
                 mock.patch.object(hotkey, "_linux_autostart_path", return_value=path):
                self.assertEqual(hotkey.current_autostart(), '"py" -m anta run')


if __name__ == "__main__":
    unittest.main()
