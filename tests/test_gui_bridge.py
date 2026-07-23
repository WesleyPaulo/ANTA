import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from anta.core.config import UserConfig, load_user_config, save_user_config
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
    # Environment de verdade (nao um SimpleNamespace): a ponte usa propriedades
    # derivadas (label/detail), e um fake solto deixaria de refletir o contrato.
    from anta.platform.detect import Environment

    return Environment(os="linux", session="x11", desktop="GNOME", release="6.1.0")


class TestPingEcho(unittest.TestCase):
    def test_ping(self):
        self.assertEqual(ConfigApi().ping(), "pong")

    def test_echo_serializavel(self):
        self.assertEqual(ConfigApi().echo({"a": 1}), {"a": 1})


class TestEnvironment(unittest.TestCase):
    def test_get_environment(self):
        api = ConfigApi(detect_env=_fake_env)
        env = api.get_environment()
        self.assertEqual(env["os"], "linux")
        self.assertEqual(env["hotkey_strategy"], "auto_x11")
        self.assertFalse(env["is_wayland"])
        self.assertTrue(env["captures_hotkey_in_process"])

    def test_manda_rotulos_prontos_para_a_tela(self):
        # o card 'Ambiente' imprimia os campos crus -> "windows windows" no Windows
        env = ConfigApi(detect_env=_fake_env).get_environment()
        self.assertEqual(env["os_label"], "Linux 6.1")
        self.assertEqual(env["detail"], "x11 · GNOME")


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


class TestDevices(unittest.TestCase):
    def test_list_microphones(self):
        fake = [{"name": "USB Mic", "max_input_channels": 2}]
        with mock.patch("anta.core.capture.list_input_devices", return_value=fake):
            mics = ConfigApi().list_microphones()
        self.assertEqual(mics, [{"name": "USB Mic"}])

    def test_list_speakers(self):
        fake = [{"name": "Alto-falantes", "max_output_channels": 2}]
        with mock.patch("anta.core.capture.list_output_devices", return_value=fake):
            spk = ConfigApi().list_speakers()
        self.assertEqual(spk, [{"name": "Alto-falantes"}])


class TestValidateHotkey(unittest.TestCase):
    def test_ok_normaliza(self):
        r = ConfigApi().validate_hotkey("Ctrl+Alt+Space")
        self.assertTrue(r["valid"])
        self.assertEqual(r["normalized"], "ctrl+alt+space")

    def test_sem_modificador_invalido(self):
        # "a+b" tem 2 tokens mas nenhum modificador -> invalido
        self.assertFalse(ConfigApi().validate_hotkey("a+b")["valid"])

    def test_uma_tecla_so_invalido(self):
        self.assertFalse(ConfigApi().validate_hotkey("a")["valid"])

    def test_token_vazio_invalido(self):
        self.assertFalse(ConfigApi().validate_hotkey("ctrl+")["valid"])


class TestComponentStatusPassthrough(unittest.TestCase):
    def test_delega_para_downloads(self):
        with mock.patch("anta.gui.downloads.component_status",
                        return_value={"installed": True}) as cs:
            r = ConfigApi().component_status("llm", "qwen3:4b")
        cs.assert_called_once_with("llm", "qwen3:4b")
        self.assertTrue(r["installed"])


class TestDownloadProgress(unittest.TestCase):
    def test_push_progress_chama_evaluate_js(self):
        win = mock.MagicMock()
        api = ConfigApi()
        api.set_window(win)
        api._push_progress({"phase": "line", "pct": 50})
        self.assertTrue(win.evaluate_js.called)
        js = win.evaluate_js.call_args[0][0]
        self.assertIn("__antaProgress", js)
        self.assertIn("50", js)

    def test_push_progress_sem_janela_e_noop(self):
        ConfigApi()._push_progress({"x": 1})  # nao levanta

    def test_download_component_encaminha_progresso(self):
        with mock.patch("anta.gui.downloads.download",
                        return_value={"ok": True}) as dl:
            ConfigApi().download_component("stt", "turbo")
        dl.assert_called_once()
        self.assertEqual(dl.call_args[0], ("stt", "turbo"))


class TestOllama(unittest.TestCase):
    def test_status_agrega_installed_e_running(self):
        with mock.patch("anta.gui.downloads.ollama_installed", return_value=True), \
             mock.patch("anta.gui.downloads.ollama_running", return_value=False):
            st = ConfigApi().ollama_status()
        self.assertTrue(st["installed"])
        self.assertFalse(st["running"])

    def test_install_delega_para_downloads(self):
        with mock.patch("anta.gui.downloads.install_ollama",
                        return_value={"ok": True}) as inst:
            r = ConfigApi().install_ollama()
        self.assertTrue(r["ok"])
        inst.assert_called_once()


class TestSave(unittest.TestCase):
    def test_grava_configured_true_e_roda_side_effects(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            api = ConfigApi(config_path=str(p))
            with mock.patch("anta.core.prompts.write_default_prompts") as wp, \
                 mock.patch("anta.platform.hotkey.setup_hotkey", return_value="ok") as sh:
                r = api.save({"family": "gemma", "mode": "pesado", "hotkey": "ctrl+alt+p",
                              "tts": True, "mic_device": "USB Mic"})
            got = load_user_config(p)
        self.assertTrue(r["ok"])
        self.assertTrue(got.configured)
        self.assertEqual(got.family, "gemma")
        self.assertEqual(got.mode, "pesado")
        self.assertEqual(got.mic_device, "USB Mic")
        self.assertTrue(got.tts)
        wp.assert_called_once()
        sh.assert_called_once()

    def test_side_effect_falho_vira_warning_nao_derruba(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            api = ConfigApi(config_path=str(p))
            with mock.patch("anta.core.prompts.write_default_prompts",
                            side_effect=RuntimeError("x")), \
                 mock.patch("anta.platform.hotkey.setup_hotkey", side_effect=RuntimeError("y")):
                r = api.save({"family": "qwen3", "mode": "leve"})
        self.assertTrue(r["ok"])  # o config foi gravado; side effects sao best-effort
        self.assertEqual(len(r["warnings"]), 2)

    def test_string_vazia_vira_none(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            api = ConfigApi(config_path=str(p))
            with mock.patch("anta.core.prompts.write_default_prompts"), \
                 mock.patch("anta.platform.hotkey.setup_hotkey"):
                api.save({"mic_device": "  ", "obsidian_vault": ""})
            got = load_user_config(p)
        self.assertIsNone(got.mic_device)
        self.assertIsNone(got.obsidian_vault)


if __name__ == "__main__":
    unittest.main()
