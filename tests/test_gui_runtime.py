import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from anta.core.config import UserConfig, save_user_config
from anta.core.states import State
from anta.gui.bridge_runtime import RuntimeApi
from anta.gui.state import StateMachine


class _FakePipeline:
    def __init__(self, warm_aviso=None, unload_aviso=None):
        self._warm_aviso = warm_aviso
        self._unload_aviso = unload_aviso
        self.warmed = False
        self.unloaded = False

    def warm(self):
        self.warmed = True
        return self._warm_aviso

    def unload(self):
        self.unloaded = True
        return self._unload_aviso


def _api(pipeline=None, config_path=None):
    sm = StateMachine()
    estados = []
    sm.add_listener(lambda ev: estados.append(ev["state"]))
    trigger = threading.Event()
    api = RuntimeApi(sm, trigger, pipeline or _FakePipeline(), config_path=config_path)
    return api, sm, trigger, estados


class TestToggle(unittest.TestCase):
    def test_toggle_dispara_o_gatilho(self):
        api, _sm, trigger, _ = _api()
        self.assertFalse(trigger.is_set())
        api.toggle()
        self.assertTrue(trigger.is_set())


class TestState(unittest.TestCase):
    def test_get_state_snapshot(self):
        api, _sm, _t, _ = _api()
        self.assertEqual(api.get_state(), {"state": "carregando"})


class TestModelLifecycle(unittest.TestCase):
    def test_load_model_sucesso(self):
        pipe = _FakePipeline(warm_aviso=None)
        api, _sm, _t, estados = _api(pipe)
        r = api.load_model()
        self.assertTrue(r["ok"])
        self.assertTrue(pipe.warmed)
        self.assertEqual(estados, ["carregando", "pronto"])

    def test_load_model_com_aviso_vira_erro(self):
        pipe = _FakePipeline(warm_aviso="modelo nao instalado")
        api, sm, _t, estados = _api(pipe)
        r = api.load_model()
        self.assertFalse(r["ok"])
        self.assertEqual(sm.current, State.ERRO)
        self.assertEqual(estados, ["carregando", "erro"])

    def test_unload_model_vira_descarregado(self):
        pipe = _FakePipeline()
        api, sm, _t, estados = _api(pipe)
        r = api.unload_model()
        self.assertTrue(r["ok"])
        self.assertTrue(pipe.unloaded)
        self.assertEqual(sm.current, State.DESCARREGADO)

    def test_unload_com_aviso_ainda_descarrega(self):
        # unload e best-effort: mesmo com aviso do Ollama, o estado vira descarregado
        api, sm, _t, _ = _api(_FakePipeline(unload_aviso="Ollama fora"))
        r = api.unload_model()
        self.assertFalse(r["ok"])
        self.assertEqual(sm.current, State.DESCARREGADO)


class TestReadOnly(unittest.TestCase):
    def test_get_config_le_temporaria(self):
        with TemporaryDirectory() as d:
            p = Path(d) / "config.toml"
            save_user_config(UserConfig(family="gemma"), p, configured=True)
            api, *_ = _api(config_path=str(p))
            cfg = api.get_config()
        self.assertEqual(cfg["family"], "gemma")
        self.assertTrue(cfg["configured"])

    def test_list_microphones(self):
        api, *_ = _api()
        with mock.patch("anta.core.capture.list_input_devices",
                        return_value=[{"name": "Mic"}]):
            self.assertEqual(api.list_microphones(), [{"name": "Mic"}])


class TestOpenConfigurador(unittest.TestCase):
    def test_spawna_processo(self):
        api, *_ = _api()
        with mock.patch("subprocess.Popen") as popen:
            r = api.open_configurador()
        self.assertTrue(r["ok"])
        popen.assert_called_once()
        args = popen.call_args[0][0]
        self.assertIn("config", args)  # abre o Configurador

    def test_falha_vira_resultado(self):
        api, *_ = _api()
        with mock.patch("subprocess.Popen", side_effect=OSError("boom")):
            r = api.open_configurador()
        self.assertFalse(r["ok"])


if __name__ == "__main__":
    unittest.main()
