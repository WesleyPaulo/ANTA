import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from anta.core.config import UserConfig, save_user_config
from anta.gui.bridge_config import ConfigApi


class _FakeHardware:
    """Dublê do anta.installer.hardware (sem NVIDIA/nvidia-smi)."""

    def __init__(self, best=8.0):
        self._best = best

    def detect_gpus(self):
        return [SimpleNamespace(name="Fake RTX", vram_gb=self._best)]

    def best_vram_gb(self):
        return self._best

    def status_for(self, mode_vram, available):
        if available >= mode_vram:
            return "verde"
        if available >= mode_vram - 1.0:
            return "amarelo"
        return "vermelho"


class _FakeDetection:
    def ram_gb(self):
        return 16.0

    def disk_free_gb(self, path=None):
        return 123.4


def _fake_env():
    return SimpleNamespace(
        os="Linux", session="x11", desktop="gnome", is_wayland=False,
        hotkey_strategy="auto_x11", captures_hotkey_in_process=True,
    )


class TestPingEcho(unittest.TestCase):
    def test_ping(self):
        self.assertEqual(ConfigApi().ping(), "pong")

    def test_echo_serializavel(self):
        self.assertEqual(ConfigApi().echo({"a": 1}), {"a": 1})


class TestEnvironment(unittest.TestCase):
    def test_get_environment(self):
        api = ConfigApi(detect_env=_fake_env)
        env = api.get_environment()
        self.assertEqual(env["os"], "Linux")
        self.assertEqual(env["hotkey_strategy"], "auto_x11")
        self.assertFalse(env["is_wayland"])
        self.assertTrue(env["captures_hotkey_in_process"])


class TestHardware(unittest.TestCase):
    def test_get_hardware_agrega_gpu_ram_disco(self):
        api = ConfigApi(hardware=_FakeHardware(best=8.0), detection=_FakeDetection())
        hw = api.get_hardware()
        self.assertEqual(hw["best_vram_gb"], 8.0)
        self.assertEqual(hw["ram_gb"], 16.0)
        self.assertEqual(hw["disk_free_gb"], 123.4)
        self.assertEqual(hw["gpus"][0]["name"], "Fake RTX")
        self.assertEqual(hw["gpus"][0]["vram_gb"], 8.0)


class TestCatalog(unittest.TestCase):
    def test_get_catalog_marca_status_por_vram(self):
        # placa de 4GB: modos leves verdes, pesados vermelhos
        api = ConfigApi(hardware=_FakeHardware(best=4.0))
        cat = api.get_catalog()
        self.assertEqual(cat["best_vram_gb"], 4.0)
        fam_keys = {f["key"] for f in cat["families"]}
        self.assertIn("qwen3", fam_keys)
        qwen = next(f for f in cat["families"] if f["key"] == "qwen3")
        by_key = {m["key"]: m for m in qwen["modes"]}
        # o tier 'leve' pede 4GB -> verde numa placa de 4GB
        self.assertEqual(by_key["leve"]["status"], "verde")
        # cada modo carrega os campos que a UI mostra
        m = by_key["leve"]
        for campo in ("label", "vram_gb", "llm", "stt", "description", "status"):
            self.assertIn(campo, m)
        # um tier pesado (>=8GB) fica vermelho com 4GB
        pesados = [m for m in qwen["modes"] if m["vram_gb"] >= 8]
        self.assertTrue(pesados and all(m["status"] == "vermelho" for m in pesados))


class TestGetConfig(unittest.TestCase):
    def test_le_config_temporaria_com_campos_novos(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            save_user_config(UserConfig(family="gemma", mode="pesado"), p, configured=True)
            api = ConfigApi(config_path=str(p))
            cfg = api.get_config()
        self.assertEqual(cfg["family"], "gemma")
        self.assertEqual(cfg["mode"], "pesado")
        self.assertTrue(cfg["configured"])
        self.assertEqual(cfg["schema_version"], 1)

    def test_sem_arquivo_devolve_defaults_nao_configurado(self):
        with tempfile.TemporaryDirectory() as d:
            api = ConfigApi(config_path=str(Path(d) / "nao-existe.toml"))
            cfg = api.get_config()
        self.assertFalse(cfg["configured"])
        self.assertEqual(cfg["family"], "qwen3")


if __name__ == "__main__":
    unittest.main()
