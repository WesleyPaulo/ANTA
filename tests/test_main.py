import unittest

from anta.__main__ import _to_pynput_hotkey


class TestHotkeyConversion(unittest.TestCase):
    def test_ctrl_alt_space(self):
        self.assertEqual(_to_pynput_hotkey("ctrl+alt+space"),
                         "<ctrl>+<alt>+<space>")

    def test_letra_simples_fica_bare(self):
        self.assertEqual(_to_pynput_hotkey("ctrl+shift+h"),
                         "<ctrl>+<shift>+h")

    def test_super_vira_cmd(self):
        self.assertEqual(_to_pynput_hotkey("super+space"),
                         "<cmd>+<space>")


if __name__ == "__main__":
    unittest.main()
