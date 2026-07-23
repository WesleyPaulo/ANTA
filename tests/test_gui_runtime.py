import threading
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from anta.core.config import UserConfig, save_user_config
from anta.core.states import State
from anta.gui import runtime_app
from anta.gui.bridge_runtime import RuntimeApi
from anta.gui.state import StateMachine


class _FakePipeline:
    def __init__(self, warm_aviso=None, unload_aviso=None):
        self._warm_aviso = warm_aviso
        self._unload_aviso = unload_aviso
        self.warmed = False
        self.unloaded = False
        self.cancelado = False

    def warm(self):
        self.warmed = True
        return self._warm_aviso

    def unload(self):
        self.unloaded = True
        return self._unload_aviso

    def cancel(self):
        self.cancelado = True


class _FakeSession:
    """Espelha a Session real no que a ponte usa (request/cancel/suspend/resume)."""

    def __init__(self):
        self.pedidos = 0
        self.cancelado = False
        self.suspenso = False

    def request(self):
        self.pedidos += 1

    def cancel(self):
        self.cancelado = True

    def suspend(self):
        self.suspenso = True

    def resume(self):
        self.suspenso = False


def _api(pipeline=None, config_path=None, session=None):
    sm = StateMachine()
    estados = []
    sm.add_listener(lambda ev: estados.append(ev["state"]))
    trigger = threading.Event()
    api = RuntimeApi(sm, trigger, pipeline or _FakePipeline(), session=session,
                     config_path=config_path)
    return api, sm, trigger, estados


class TestToggle(unittest.TestCase):
    def test_toggle_dispara_o_gatilho(self):
        api, _sm, trigger, _ = _api()
        self.assertFalse(trigger.is_set())
        api.toggle()
        self.assertTrue(trigger.is_set())

    def test_toggle_com_session_vai_pelo_request(self):
        # com a Session ligada o botao NAO arma o Event direto: quem decide gravar
        # ou PARAR e o request() (senao um clique durante a fala virava gravacao)
        sess = _FakeSession()
        api, _sm, trigger, _ = _api(session=sess)
        api.toggle()
        self.assertEqual(sess.pedidos, 1)
        self.assertFalse(trigger.is_set())


class TestCancel(unittest.TestCase):
    def test_cancel_delega_pra_session(self):
        sess = _FakeSession()
        api, *_ = _api(session=sess)
        self.assertEqual(api.cancel(), {"ok": True})
        self.assertTrue(sess.cancelado)

    def test_cancel_sem_session_cai_no_pipeline(self):
        pipe = _FakePipeline()
        api, *_ = _api(pipe)
        api.cancel()
        self.assertTrue(pipe.cancelado)


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

    def test_unload_suspende_a_sessao(self):
        """'Desalocar memoria' tem que PARAR a ANTA: sem suspender, o proximo atalho
        recarregava Whisper/LLM em silencio e a memoria voltava sozinha."""
        sess = _FakeSession()
        api, sm, _t, _ = _api(session=sess)
        api.unload_model()
        self.assertTrue(sess.suspenso)
        self.assertEqual(sm.current, State.DESCARREGADO)

    def test_load_retoma_a_sessao(self):
        sess = _FakeSession()
        sess.suspenso = True
        api, sm, _t, _ = _api(session=sess)
        api.load_model()
        self.assertFalse(sess.suspenso)
        self.assertEqual(sm.current, State.PRONTO)

    def test_load_com_falha_nao_retoma(self):
        # o modelo nao subiu: continuar suspenso e melhor do que fingir que da pra usar
        sess = _FakeSession()
        sess.suspenso = True
        api, sm, _t, _ = _api(_FakePipeline(warm_aviso="modelo ausente"), session=sess)
        api.load_model()
        self.assertTrue(sess.suspenso)
        self.assertEqual(sm.current, State.ERRO)


class TestMemoria(unittest.TestCase):
    """O HUD mostra o que a ANTA ocupa — um residente sem numero na tela vira suspeita."""

    def test_get_memory_agrega_vram_e_ram(self):
        api, *_ = _api()
        with mock.patch("anta.installer.hardware.vram_usage_gb", return_value=(5.2, 8.0)), \
             mock.patch("anta.gui.detection.process_ram_gb", return_value=1.4):
            m = api.get_memory()
        self.assertEqual((m["vram_used_gb"], m["vram_total_gb"]), (5.2, 8.0))
        self.assertEqual(m["ram_used_gb"], 1.4)
        self.assertTrue(m["loaded"])

    def test_sem_nvidia_devolve_none_em_vez_de_zero(self):
        # 0.0 seria mentira (a GPU existe e esta em uso); o HUD omite a linha
        api, *_ = _api()
        with mock.patch("anta.installer.hardware.vram_usage_gb", return_value=(None, None)), \
             mock.patch("anta.gui.detection.process_ram_gb", return_value=None):
            m = api.get_memory()
        self.assertIsNone(m["vram_used_gb"])
        self.assertIsNone(m["ram_used_gb"])

    def test_loaded_false_quando_desalocado(self):
        api, sm, _t, _ = _api()
        sm.transition(State.DESCARREGADO)
        with mock.patch("anta.installer.hardware.vram_usage_gb", return_value=(0.4, 8.0)), \
             mock.patch("anta.gui.detection.process_ram_gb", return_value=0.3):
            self.assertFalse(api.get_memory()["loaded"])


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


class _FakeEvent:
    """Espelha o `window.events.closing` do pywebview: handlers com `+=`, e um
    False cancela o fechamento."""

    def __init__(self):
        self.handlers = []

    def __iadd__(self, fn):
        self.handlers.append(fn)
        return self

    def disparar(self):
        return all(fn() is not False for fn in self.handlers)


class TestFecharParaBandeja(unittest.TestCase):
    """Com icone na bandeja, o X tem que ESCONDER: um app que promete ficar
    residente e morre quando a janela fecha leva junto o atalho global."""

    def _janela(self):
        win = mock.MagicMock()
        win.events.closing = _FakeEvent()
        return win

    def test_x_esconde_em_vez_de_fechar(self):
        win = self._janela()
        api, *_ = _api()
        api.set_window(win)
        tray = mock.Mock(quitting=False)
        self.assertTrue(runtime_app._fechar_para_a_bandeja(win, api, tray))
        self.assertFalse(win.events.closing.disparar())  # fechamento cancelado
        win.hide.assert_called_once()

    def test_sair_pelo_menu_fecha_de_verdade(self):
        win = self._janela()
        api, *_ = _api()
        api.set_window(win)
        tray = mock.Mock(quitting=True)  # o item "Sair" marcou antes do destroy()
        runtime_app._fechar_para_a_bandeja(win, api, tray)
        self.assertTrue(win.events.closing.disparar())
        win.hide.assert_not_called()

    def test_backend_sem_o_evento_nao_quebra(self):
        class _JanelaVelha:  # backend do pywebview sem `events.closing`
            pass

        self.assertFalse(
            runtime_app._fechar_para_a_bandeja(_JanelaVelha(), _api()[0], mock.Mock()))


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
