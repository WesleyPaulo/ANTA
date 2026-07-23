import os
import unittest
from collections import namedtuple
from unittest import mock

from anta.gui import detection

_Usage = namedtuple("_Usage", "total used free")
_GIB = 1024 ** 3


class TestDiskFree(unittest.TestCase):
    def test_converte_bytes_para_gib(self):
        fake = _Usage(total=200 * _GIB, used=50 * _GIB, free=150 * _GIB)
        with mock.patch.object(detection.shutil, "disk_usage", return_value=fake):
            self.assertEqual(detection.disk_free_gb("/qualquer"), 150.0)

    def test_arredonda_uma_casa(self):
        fake = _Usage(total=0, used=0, free=int(1.25 * _GIB))
        with mock.patch.object(detection.shutil, "disk_usage", return_value=fake):
            self.assertEqual(detection.disk_free_gb("/x"), 1.2)  # round(1.25,1) -> 1.2

    def test_best_effort_zero_em_erro(self):
        # caminho invalido/inacessivel nao pode derrubar a deteccao -> 0.0
        with mock.patch.object(detection.shutil, "disk_usage", side_effect=OSError):
            self.assertEqual(detection.disk_free_gb("/nao/existe"), 0.0)

    def test_default_usa_home(self):
        captured = {}

        def fake(p):
            captured["path"] = p
            return _Usage(0, 0, 42 * _GIB)

        with mock.patch.object(detection.shutil, "disk_usage", side_effect=fake):
            self.assertEqual(detection.disk_free_gb(), 42.0)
        self.assertIn("path", captured)  # chamou com algum caminho (home)


class TestRam(unittest.TestCase):
    def test_ram_gb_positivo(self):
        # integracao leve: nesta maquina RAM > 0 (psutil ou fallback stdlib)
        self.assertGreater(detection.ram_gb(), 0.0)
        self.assertIsInstance(detection.ram_gb(), float)

    @unittest.skipUnless(
        hasattr(os, "sysconf") and "SC_PHYS_PAGES" in getattr(os, "sysconf_names", {}),
        "sysconf indisponivel",
    )
    def test_fallback_stdlib_posix(self):
        self.assertGreater(detection._ram_gb_stdlib(), 0.0)

    def test_ram_cai_no_stdlib_se_psutil_falha(self):
        # se o import de psutil estourar, ram_gb usa _ram_gb_stdlib (nao propaga erro)
        with mock.patch.object(detection, "_ram_gb_stdlib", return_value=3.3), \
             mock.patch.dict("sys.modules", {"psutil": None}):  # import psutil -> ImportError
            self.assertEqual(detection.ram_gb(), 3.3)


class TestProcessRam(unittest.TestCase):
    """RAM do proprio processo — o Whisper e o embedder vivem aqui (CPU, por
    principio). E o numero que o HUD mostra pra provar que o residente nao vazou."""

    def test_mede_o_rss(self):
        medido = detection.process_ram_gb()
        self.assertIsNotNone(medido)
        self.assertGreater(medido, 0.0)

    def test_sem_psutil_devolve_none(self):
        # None (nao sei) e diferente de 0.0 (nao usa nada): o HUD omite a linha
        with mock.patch.dict("sys.modules", {"psutil": None}):
            self.assertIsNone(detection.process_ram_gb())


if __name__ == "__main__":
    unittest.main()
