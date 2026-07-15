"""Testes de capture._resolve_device (resolucao de microfone por NOME).

Regressao do bug em que `_resolve_device` usava `sd` sem importar sounddevice
(NameError no caminho recomendado: mic configurado por nome). Injetamos um
sounddevice falso em sys.modules para nao depender do PortAudio nativo.
"""
import sys
import unittest
from unittest import mock

from anta.core import capture


def _devices():
    return [
        {"name": "Default Sink", "max_input_channels": 0},   # saida: ignorado
        {"name": "USB Mic (Yeti)", "max_input_channels": 2},
        {"name": "Webcam Mic", "max_input_channels": 1},
    ]


def _fake_sd(devices):
    fake = mock.MagicMock()
    fake.query_devices.return_value = devices
    return mock.patch.dict(sys.modules, {"sounddevice": fake})


class TestResolveDevice(unittest.TestCase):
    def test_none_quando_vazio(self):
        self.assertIsNone(capture._resolve_device(None))
        self.assertIsNone(capture._resolve_device(""))

    def test_match_exato(self):
        with _fake_sd(_devices()):
            self.assertEqual(capture._resolve_device("USB Mic (Yeti)"), 1)

    def test_match_case_insensitive(self):
        with _fake_sd(_devices()):
            self.assertEqual(capture._resolve_device("usb mic (yeti)"), 1)

    def test_fallback_substring(self):
        with _fake_sd(_devices()):
            self.assertEqual(capture._resolve_device("yeti"), 1)

    def test_ignora_saidas(self):
        with _fake_sd(_devices()):
            # "Default Sink" tem 0 canais de entrada -> nunca casa
            self.assertIsNone(capture._resolve_device("Default Sink"))

    def test_nome_sumido_cai_no_default(self):
        with _fake_sd(_devices()):
            self.assertIsNone(capture._resolve_device("Microfone Inexistente"))


if __name__ == "__main__":
    unittest.main()
