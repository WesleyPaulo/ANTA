import unittest
from types import SimpleNamespace
from unittest import mock

from anta.gui import downloads


class _FakeStdout:
    def __init__(self, lines):
        self._it = iter(lines)

    def __iter__(self):
        return self._it

    def close(self):
        pass


def _fake_popen_factory(lines, rc=0):
    def factory(cmd, **kwargs):
        return SimpleNamespace(stdout=_FakeStdout(lines), returncode=rc, wait=lambda: None)
    return factory


class TestRunStream(unittest.TestCase):
    def test_transmite_linhas_sem_ansi_e_retorna_rc(self):
        linhas = []
        rc = downloads.run_stream(
            ["ollama", "pull", "x"], linhas.append,
            popen=_fake_popen_factory(["pulling \x1b[32m10%\x1b[0m\n", "done\n", "\n"], rc=0),
        )
        self.assertEqual(rc, 0)
        self.assertEqual(linhas, ["pulling 10%", "done"])  # ANSI removido, linha vazia fora

    def test_propaga_codigo_de_erro(self):
        rc = downloads.run_stream(["x"], None, popen=_fake_popen_factory([], rc=1))
        self.assertEqual(rc, 1)


class TestLlmInstalled(unittest.TestCase):
    def _run(self, stdout):
        return lambda *a, **k: SimpleNamespace(stdout=stdout)

    def test_acha_o_tag(self):
        out = "NAME\nqwen3:4b-instruct  abc  2.5GB\ngemma3:4b  def  3GB\n"
        with mock.patch.object(downloads, "ollama_installed", return_value=True):
            self.assertTrue(downloads.llm_installed("qwen3:4b-instruct", run=self._run(out)))
            self.assertFalse(downloads.llm_installed("qwen3:14b", run=self._run(out)))

    def test_latest_implicito(self):
        out = "NAME\nllama3:latest  abc  4GB\n"
        with mock.patch.object(downloads, "ollama_installed", return_value=True):
            self.assertTrue(downloads.llm_installed("llama3", run=self._run(out)))

    def test_sem_ollama_e_falso(self):
        with mock.patch.object(downloads, "ollama_installed", return_value=False):
            self.assertFalse(downloads.llm_installed("qwen3:4b"))


class TestComponentStatus(unittest.TestCase):
    def test_llm_usa_ollama(self):
        with mock.patch.object(downloads, "llm_installed", return_value=True):
            self.assertTrue(downloads.component_status("llm", "qwen3:4b")["installed"])

    def test_stt_desconhecido(self):
        self.assertIsNone(downloads.component_status("stt", "turbo")["installed"])

    def test_voz_usa_glob(self):
        with mock.patch.object(downloads, "voice_installed", return_value=False):
            self.assertFalse(downloads.component_status("tts_voice", "pt_BR-faber-medium")["installed"])


class TestDownloadDispatch(unittest.TestCase):
    def test_llm_ok_com_progresso(self):
        eventos = []
        with mock.patch.object(downloads, "ollama_installed", return_value=True), \
             mock.patch.object(downloads, "llm_installed", return_value=False), \
             mock.patch.object(downloads, "run_stream",
                               side_effect=lambda cmd, on_line, **k: (on_line("pulling 50%"), 0)[1]):
            r = downloads.download("llm", "qwen3:4b", on_progress=eventos.append)
        self.assertTrue(r["ok"])
        fases = [e["phase"] for e in eventos]
        self.assertEqual(fases[0], "start")
        self.assertEqual(fases[-1], "done")
        # a linha com 50% virou pct
        linha = next(e for e in eventos if e["phase"] == "line")
        self.assertEqual(linha["pct"], 50)

    def test_llm_ja_instalado_nao_baixa(self):
        with mock.patch.object(downloads, "ollama_installed", return_value=True), \
             mock.patch.object(downloads, "llm_installed", return_value=True), \
             mock.patch.object(downloads, "run_stream") as rs:
            r = downloads.download("llm", "qwen3:4b")
        self.assertTrue(r["ok"])
        rs.assert_not_called()

    def test_erro_vira_resultado(self):
        with mock.patch.object(downloads, "_download_stt", side_effect=RuntimeError("boom")):
            r = downloads.download("stt", "turbo")
        self.assertFalse(r["ok"])
        self.assertIn("boom", r["msg"])

    def test_kind_desconhecido(self):
        r = downloads.download("xpto", "k")
        self.assertFalse(r["ok"])


class TestDownloadVoice(unittest.TestCase):
    def test_nome_de_catalogo_usa_ensure_voice(self):
        with mock.patch.object(downloads, "voice_installed", return_value=False), \
             mock.patch("anta.core.tts.ensure_voice", return_value="/v/faber.onnx") as ev, \
             mock.patch("anta.core.tts.import_voice") as iv:
            r = downloads._download_voice("pt_BR-faber-medium", None)
        self.assertTrue(r["ok"])
        ev.assert_called_once()
        iv.assert_not_called()

    def test_url_usa_import_voice(self):
        with mock.patch.object(downloads, "voice_installed", return_value=False), \
             mock.patch("anta.core.tts.ensure_voice") as ev, \
             mock.patch("anta.core.tts.import_voice", return_value="/v/x.onnx") as iv:
            r = downloads._download_voice("https://exemplo/x.onnx", None)
        self.assertTrue(r["ok"])
        iv.assert_called_once()
        ev.assert_not_called()


if __name__ == "__main__":
    unittest.main()
