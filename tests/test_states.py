import unittest
from unittest import mock

from anta.core.states import State, emit
from anta.gui.state import StateMachine, make_pywebview_emitter


class TestEmit(unittest.TestCase):
    def test_none_e_noop(self):
        emit(None, State.PRONTO)  # nao levanta

    def test_chama_com_o_valor_string(self):
        vistos = []
        emit(lambda s, **p: vistos.append((s, p)), State.OUVINDO)
        self.assertEqual(vistos, [("ouvindo", {})])

    def test_passa_payload(self):
        vistos = []
        emit(lambda s, **p: vistos.append((s, p)), State.ERRO, code="mic", text="x")
        self.assertEqual(vistos, [("erro", {"code": "mic", "text": "x"})])

    def test_aceita_string_crua(self):
        vistos = []
        emit(lambda s, **p: vistos.append(s), "pronto")
        self.assertEqual(vistos, ["pronto"])

    def test_swallow_excecao_do_ouvinte(self):
        def ruim(*a, **k):
            raise RuntimeError("boom")
        emit(ruim, State.PRONTO)  # nao propaga


class TestStateMachine(unittest.TestCase):
    def test_transition_atualiza_e_notifica(self):
        eventos = []
        sm = StateMachine(listeners=[eventos.append])
        ev = sm.transition(State.OUVINDO)
        self.assertEqual(sm.current, State.OUVINDO)
        self.assertEqual(ev, {"state": "ouvindo"})
        self.assertEqual(eventos, [{"state": "ouvindo"}])

    def test_coage_string_para_enum(self):
        sm = StateMachine()
        sm.transition("processando")
        self.assertEqual(sm.current, State.PROCESSANDO)

    def test_filtra_payload_none(self):
        sm = StateMachine()
        ev = sm.transition(State.ERRO, code="mic", text=None)
        self.assertEqual(ev, {"state": "erro", "code": "mic"})  # text=None sai

    def test_ouvinte_ruim_nao_trava_os_outros(self):
        bons = []
        def ruim(_ev):
            raise RuntimeError("x")
        sm = StateMachine(listeners=[ruim, bons.append])
        sm.transition(State.PRONTO)
        self.assertEqual(bons, [{"state": "pronto"}])

    def test_snapshot(self):
        sm = StateMachine(initial=State.DESCARREGADO)
        self.assertEqual(sm.snapshot(), {"state": "descarregado"})

    def test_add_listener(self):
        eventos = []
        sm = StateMachine()
        sm.add_listener(eventos.append)
        sm.transition(State.PRONTO)
        self.assertEqual(eventos, [{"state": "pronto"}])


class TestPywebviewEmitter(unittest.TestCase):
    def test_empurra_para_o_js(self):
        win = mock.MagicMock()
        make_pywebview_emitter(win)({"state": "ouvindo"})
        self.assertTrue(win.evaluate_js.called)
        js = win.evaluate_js.call_args[0][0]
        self.assertIn("__antaOnState", js)
        self.assertIn("ouvindo", js)

    def test_sem_janela_e_noop(self):
        make_pywebview_emitter(None)({"state": "pronto"})  # nao levanta

    def test_evaluate_js_falho_nao_propaga(self):
        win = mock.MagicMock()
        win.evaluate_js.side_effect = RuntimeError("janela morreu")
        make_pywebview_emitter(win)({"state": "erro"})  # engole


if __name__ == "__main__":
    unittest.main()
