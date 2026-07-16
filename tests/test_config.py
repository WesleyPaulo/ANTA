import tempfile
import unittest
from pathlib import Path

from anta.core.config import (
    UserConfig, load_modes, load_user_config, save_user_config,
)


class TestLoadModes(unittest.TestCase):
    def test_ordenacao_por_vram(self):
        modes = load_modes()
        vrams = [m.vram_gb for m in modes]
        self.assertEqual(vrams, sorted(vrams))

    def test_campos_presentes(self):
        modes = load_modes()
        self.assertTrue(modes)
        m = modes[0]
        self.assertTrue(m.key and m.label and m.llm and m.stt)

    def test_vram_real_carrega(self):
        # a coluna vram_real (uso estimado) flui pelo load_modes; e opcional (str)
        modes = load_modes()
        for m in modes:
            self.assertIsInstance(m.vram_real, str)
        self.assertTrue(modes[0].vram_real)  # os modos que shipamos tem o campo


class TestUserConfigRoundTrip(unittest.TestCase):
    def test_salva_e_le(self):
        cfg = UserConfig(mode="pesado", mic_device="Yeti USB",
                         hotkey="ctrl+space", obsidian_vault="/tmp/vault", tts=True,
                         rag=False, web=True, web_engine="searxng",
                         web_searxng_url="http://searx.local")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.toml"
            save_user_config(cfg, path)
            got = load_user_config(path)
        self.assertEqual(got.mode, "pesado")
        self.assertEqual(got.mic_device, "Yeti USB")
        self.assertEqual(got.hotkey, "ctrl+space")
        self.assertEqual(got.obsidian_vault, "/tmp/vault")
        self.assertTrue(got.tts)
        self.assertFalse(got.rag)  # round-trip preserva o toggle
        self.assertTrue(got.web)   # campos de busca web sobrevivem
        self.assertEqual(got.web_engine, "searxng")
        self.assertEqual(got.web_searxng_url, "http://searx.local")

    def test_vazio_vira_none(self):
        cfg = UserConfig(mic_device=None, obsidian_vault=None)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.toml"
            save_user_config(cfg, path)
            got = load_user_config(path)
        self.assertIsNone(got.mic_device)
        self.assertIsNone(got.obsidian_vault)

    def test_web_engine_nao_string_coage_para_str(self):
        # TOML malformado: web_engine = true (bool) nao pode virar bool na config
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            p.write_text("web = true\nweb_engine = true\n", encoding="utf-8")
            got = load_user_config(p)
        self.assertIsInstance(got.web_engine, str)

    def test_defaults_quando_ausente(self):
        with tempfile.TemporaryDirectory() as d:
            got = load_user_config(Path(d) / "nao-existe.toml")
        self.assertEqual(got.mode, "leve")
        self.assertFalse(got.tts)
        self.assertTrue(got.rag)    # ausente -> ligado por padrao
        self.assertFalse(got.web)   # ausente -> offline por padrao

    def test_mode_or_default_cai_no_mais_leve(self):
        modes = load_modes()
        cfg = UserConfig(mode="inexistente")
        self.assertEqual(cfg.mode_or_default(modes), modes[0])


if __name__ == "__main__":
    unittest.main()
