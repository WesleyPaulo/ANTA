"""Testes do modulo de TTS (anta.core.tts).

Cobrem a logica pura e os guards best-effort — sem exigir piper/onnxruntime nem
PortAudio: usamos um sounddevice falso e mockamos urllib.
"""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anta.core import tts


class TestSpeakGuards(unittest.TestCase):
    def test_texto_vazio_noop(self):
        tts.speak("", None)  # nao deve levantar nem tentar sintetizar

    def test_voz_inexistente_noop(self):
        # Voz que nao existe -> no-op silencioso (nem tenta importar piper).
        tts.speak("oi", voice_path="/caminho/que/nao/existe.onnx")


class TestEnsureVoice(unittest.TestCase):
    def test_nao_baixa_se_ja_existe(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            (dest / f"{tts.DEFAULT_VOICE}.onnx").write_bytes(b"modelo")
            (dest / f"{tts.DEFAULT_VOICE}.onnx.json").write_bytes(b"{}")
            with mock.patch("urllib.request.urlopen") as u:
                path = tts.ensure_voice(dest_dir=dest)
                u.assert_not_called()  # arquivos presentes -> sem download
            self.assertEqual(path.name, f"{tts.DEFAULT_VOICE}.onnx")

    def test_baixa_o_que_falta(self):
        with tempfile.TemporaryDirectory() as d:
            dest = Path(d)
            calls = []

            def fake_download(url, target):
                calls.append(url)
                Path(target).write_bytes(b"x")

            with mock.patch.object(tts, "_download", side_effect=fake_download):
                tts.ensure_voice(dest_dir=dest)
            # baixou os dois artefatos (.onnx e .onnx.json)
            self.assertEqual(len(calls), 2)


class TestResolveOutput(unittest.TestCase):
    def _fake_sd(self, devices):
        fake = mock.MagicMock()
        fake.query_devices.return_value = devices
        return mock.patch.dict(sys.modules, {"sounddevice": fake})

    def test_none_quando_vazio(self):
        self.assertIsNone(tts._resolve_output(None))
        self.assertIsNone(tts._resolve_output(""))

    def test_match_exato_saida(self):
        devs = [{"name": "HDA Speakers", "max_output_channels": 2},
                {"name": "USB Mic", "max_output_channels": 0}]
        with self._fake_sd(devs):
            self.assertEqual(tts._resolve_output("HDA Speakers"), 0)

    def test_ignora_entradas(self):
        devs = [{"name": "USB Mic", "max_output_channels": 0},
                {"name": "HDA Speakers", "max_output_channels": 2}]
        with self._fake_sd(devs):
            self.assertIsNone(tts._resolve_output("USB Mic"))


if __name__ == "__main__":
    unittest.main()
