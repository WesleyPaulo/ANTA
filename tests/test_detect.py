import unittest
from unittest import mock

from anta.platform.detect import Environment, detect


def _env(os_, session):
    return Environment(os=os_, session=session, desktop="")


class TestHotkeyStrategy(unittest.TestCase):
    def test_windows(self):
        self.assertEqual(_env("windows", "windows").hotkey_strategy, "auto_win")

    def test_linux_x11(self):
        self.assertEqual(_env("linux", "x11").hotkey_strategy, "auto_x11")

    def test_linux_wayland(self):
        e = _env("linux", "wayland")
        self.assertEqual(e.hotkey_strategy, "compositor")
        self.assertTrue(e.is_wayland)

    def test_macos_manual(self):
        self.assertEqual(_env("macos", "unknown").hotkey_strategy, "manual")

    def test_linux_desconhecido_manual(self):
        self.assertEqual(_env("linux", "unknown").hotkey_strategy, "manual")

    def test_captures_hotkey_in_process(self):
        self.assertTrue(_env("linux", "x11").captures_hotkey_in_process)
        self.assertTrue(_env("windows", "windows").captures_hotkey_in_process)
        self.assertFalse(_env("linux", "wayland").captures_hotkey_in_process)
        self.assertFalse(_env("macos", "unknown").captures_hotkey_in_process)


class TestRotulos(unittest.TestCase):
    """Regressao: o card 'Ambiente' do Configurador imprimia `os` e `session` crus,
    e no Windows os dois valem "windows" — a tela dizia "windows / windows"."""

    def test_windows_com_versao(self):
        e = Environment(os="windows", session="windows", desktop="", release="11")
        self.assertEqual(e.label, "Windows 11")
        self.assertNotIn("windows windows", f"{e.label} {e.detail}".lower())

    def test_windows_diz_como_o_atalho_funciona(self):
        e = Environment(os="windows", session="windows", desktop="", release="11")
        self.assertEqual(e.detail, "atalho global automático")

    def test_linux_encurta_o_kernel_e_mostra_sessao(self):
        e = Environment(os="linux", session="wayland", desktop="KDE",
                        release="6.6.87.2-microsoft-standard-WSL2")
        self.assertEqual(e.label, "Linux 6.6")
        self.assertEqual(e.detail, "wayland · KDE")

    def test_linux_sem_desktop(self):
        e = Environment(os="linux", session="x11", desktop="", release="6.1.0")
        self.assertEqual(e.detail, "x11")

    def test_wayland_sem_captura_diz_atalho_do_sistema(self):
        e = Environment(os="unknown", session="wayland", desktop="")
        self.assertEqual(e.detail, "atalho manual")  # so o Linux vira 'compositor'

    def test_sem_release_nao_inventa(self):
        self.assertEqual(Environment(os="macos", session="unknown", desktop="").label,
                         "macOS")

    def test_detect_preenche_release(self):
        with mock.patch("platform.system", return_value="Windows"), \
             mock.patch("platform.release", return_value="11"):
            self.assertEqual(detect().label, "Windows 11")


class TestDetect(unittest.TestCase):
    def test_detecta_linux_wayland(self):
        with mock.patch("platform.system", return_value="Linux"), \
             mock.patch.dict("os.environ",
                             {"XDG_SESSION_TYPE": "wayland", "XDG_CURRENT_DESKTOP": "KDE"},
                             clear=True):
            env = detect()
        self.assertEqual(env.os, "linux")
        self.assertEqual(env.session, "wayland")
        self.assertEqual(env.desktop, "KDE")

    def test_detecta_windows(self):
        with mock.patch("platform.system", return_value="Windows"):
            env = detect()
        self.assertEqual(env.os, "windows")
        self.assertEqual(env.hotkey_strategy, "auto_win")


if __name__ == "__main__":
    unittest.main()
