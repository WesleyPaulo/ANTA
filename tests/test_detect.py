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
