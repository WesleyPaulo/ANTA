import subprocess
import unittest
from unittest import mock

from anta.installer import hardware
from anta.installer.hardware import status_for, vram_usage_gb


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


class TestVramUsage(unittest.TestCase):
    """O HUD mostra quanto a ANTA custa agora. Sem NVIDIA a resposta e 'nao sei'
    (None), nunca 0.0 — zero seria uma afirmacao falsa sobre uma GPU em uso."""

    def _smi(self, saida):
        return mock.patch.object(subprocess, "check_output", return_value=saida)

    def test_le_usada_e_total(self):
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             self._smi("5324, 8192\n"):
            self.assertEqual(vram_usage_gb(), (5.2, 8.0))

    def test_escolhe_a_gpu_maior(self):
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             self._smi("1024, 4096\n6144, 16384\n"):
            self.assertEqual(vram_usage_gb(), (6.0, 16.0))

    def test_sem_nvidia_smi_e_none(self):
        with mock.patch.object(hardware.shutil, "which", return_value=None):
            self.assertEqual(vram_usage_gb(), (None, None))

    def test_falha_do_comando_e_none(self):
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             mock.patch.object(subprocess, "check_output", side_effect=OSError):
            self.assertEqual(vram_usage_gb(), (None, None))

    def test_saida_estranha_nao_levanta(self):
        with mock.patch.object(hardware.shutil, "which", return_value="/usr/bin/nvidia-smi"), \
             self._smi("[N/A], [N/A]\n"):
            self.assertEqual(vram_usage_gb(), (None, None))


if __name__ == "__main__":
    unittest.main()
