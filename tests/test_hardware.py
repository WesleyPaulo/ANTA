import unittest

from voz.installer.hardware import status_for


class TestStatusFor(unittest.TestCase):
    def test_verde_quando_cabe(self):
        self.assertEqual(status_for(8.0, 8.0), "verde")
        self.assertEqual(status_for(4.0, 8.1), "verde")

    def test_amarelo_dentro_de_1gb(self):
        self.assertEqual(status_for(8.0, 7.5), "amarelo")
        self.assertEqual(status_for(8.0, 7.0), "amarelo")  # limite exato

    def test_vermelho_abaixo_do_limite(self):
        self.assertEqual(status_for(8.0, 6.9), "vermelho")
        self.assertEqual(status_for(12.0, 8.0), "vermelho")


if __name__ == "__main__":
    unittest.main()
