import contextlib
import os
import tempfile
import unittest
from pathlib import Path

from anta.core.config import (
    UserConfig, default_modes_path, load_families, load_modes, load_user_config,
    save_user_config,
)


@contextlib.contextmanager
def _cwd(path):
    old = os.getcwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


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


class TestLoadFamilies(unittest.TestCase):
    def test_tres_familias_com_structured(self):
        fams = load_families()
        by_key = {f.key: f for f in fams}
        self.assertIn("qwen3", by_key)
        self.assertIn("gemma", by_key)
        self.assertIn("deepseek", by_key)
        # 'tools' NAO serve com Ollama (ele ignora tool_choice -> o modelo conversa em
        # vez de chamar a acao). Toda familia usa gramatica. Ver brain._instructor_mode.
        for fam in fams:
            self.assertNotEqual(fam.structured, "tools", f"{fam.key}: tools quebra no Ollama")
            self.assertIn(fam.structured, ("json_schema", "json"))

    def test_modos_herdam_tier_e_familia(self):
        fams = {f.key: f for f in load_families()}
        leve = next(m for m in fams["gemma"].modes if m.key == "leve")
        self.assertEqual(leve.vram_gb, 4)            # do tier
        self.assertEqual(leve.stt, "turbo")          # do tier
        self.assertEqual(leve.llm, "gemma3:4b")      # do modelo da familia
        self.assertEqual(leve.structured, fams["gemma"].structured)  # da familia
        # ordenados por vram_gb
        vrams = [m.vram_gb for m in fams["qwen3"].modes]
        self.assertEqual(vrams, sorted(vrams))

    def test_familia_pode_omitir_tier(self):
        fams = {f.key: f for f in load_families()}
        deepseek_tiers = {m.key for m in fams["deepseek"].modes}
        self.assertNotIn("batata", deepseek_tiers)   # deepseek nao cabe em 1GB
        self.assertIn("ultra-leve", deepseek_tiers)

    def test_load_modes_por_familia(self):
        gemma = load_modes("gemma")
        self.assertTrue(all(m.llm.startswith("gemma") for m in gemma))

    def test_carrega_de_qualquer_cwd(self):
        # regressao: o daemon roda de qualquer pasta (autostart do login abre com o
        # CWD do sistema). O modes.yaml e resolvido pela raiz do repo, nao pelo CWD.
        self.assertTrue(default_modes_path().is_absolute())
        with tempfile.TemporaryDirectory() as d, _cwd(d):
            self.assertTrue(load_families())   # nao pode dar FileNotFoundError
            self.assertTrue(load_modes("qwen3"))


class TestUserConfigRoundTrip(unittest.TestCase):
    def test_salva_e_le(self):
        cfg = UserConfig(mode="pesado", family="gemma", mic_device="Yeti USB",
                         hotkey="ctrl+space", obsidian_vault="/tmp/vault", tts=True,
                         rag=False, web=True, web_engine="searxng",
                         web_searxng_url="http://searx.local")
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.toml"
            save_user_config(cfg, path)
            got = load_user_config(path)
        self.assertEqual(got.mode, "pesado")
        self.assertEqual(got.family, "gemma")  # familia sobrevive ao round-trip
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
        self.assertEqual(got.family, "qwen3")  # ausente (config antiga) -> qwen3

    def test_mode_or_default_cai_no_mais_leve(self):
        modes = load_modes()
        cfg = UserConfig(mode="inexistente")
        self.assertEqual(cfg.mode_or_default(modes), modes[0])

    def test_family_or_default_cai_na_primeira(self):
        fams = load_families()
        self.assertEqual(UserConfig(family="gemma").family_or_default(fams).key, "gemma")
        self.assertEqual(UserConfig(family="sumiu").family_or_default(fams), fams[0])


class TestSchemaVersionEConfigured(unittest.TestCase):
    def test_round_trip_schema_e_configured(self):
        cfg = UserConfig(schema_version=1, configured=True)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.toml"
            save_user_config(cfg, path)
            texto = path.read_text(encoding="utf-8")
            got = load_user_config(path)
        self.assertEqual(got.schema_version, 1)
        self.assertTrue(got.configured)
        self.assertIn("schema_version = 1", texto)
        self.assertIn("configured = true", texto)

    def test_kwarg_configured_sobrescreve(self):
        # o Configurador passa configured=True ao concluir, mesmo com cfg.configured=False
        cfg = UserConfig(configured=False)
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "config.toml"
            save_user_config(cfg, path, configured=True)
            got = load_user_config(path)
        self.assertTrue(got.configured)

    def test_sem_arquivo_nasce_nao_configurado(self):
        # o sinal p/ o runtime abrir o Configurador: default (sem arquivo) = False
        with tempfile.TemporaryDirectory() as d:
            got = load_user_config(Path(d) / "nao-existe.toml")
        self.assertFalse(got.configured)

    def test_config_antiga_sem_a_chave_vira_configurado(self):
        # retrocompat: arquivo existe mas sem 'configured' = TUI antiga (so gravava
        # em sucesso) -> ja configurado. Nao pode forcar re-setup em quem ja instalou.
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            p.write_text('family = "qwen3"\nmode = "leve"\n', encoding="utf-8")
            got = load_user_config(p)
        self.assertTrue(got.configured)
        self.assertEqual(got.schema_version, 1)  # ausente -> 1

    def test_configured_false_explicito_sobrevive(self):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            p.write_text("configured = false\n", encoding="utf-8")
            got = load_user_config(p)
        self.assertFalse(got.configured)


if __name__ == "__main__":
    unittest.main()
