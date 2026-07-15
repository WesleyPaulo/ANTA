import unittest

from anta.__main__ import Session, _to_pynput_hotkey


class TestHotkeyConversion(unittest.TestCase):
    def test_ctrl_alt_space(self):
        self.assertEqual(_to_pynput_hotkey("ctrl+alt+space"),
                         "<ctrl>+<alt>+<space>")

    def test_letra_simples_fica_bare(self):
        self.assertEqual(_to_pynput_hotkey("ctrl+shift+h"),
                         "<ctrl>+<shift>+h")

    def test_super_vira_cmd(self):
        self.assertEqual(_to_pynput_hotkey("super+space"),
                         "<cmd>+<space>")


class _FakeRecorder:
    def __init__(self, audio="AUDIO", fail_start=False, fail_stop=False):
        self.audio = audio
        self.fail_start = fail_start
        self.fail_stop = fail_stop
        self.started = False
        self.stopped = False

    def start(self):
        if self.fail_start:
            raise RuntimeError("mic indisponivel")
        self.started = True

    def stop(self):
        self.stopped = True
        if self.fail_stop:
            raise RuntimeError("falha ao parar")
        return self.audio


class _FakePipeline:
    def __init__(self, feedback="feito", fail=False):
        self.feedback = feedback
        self.fail = fail
        self.received = None

    def run(self, audio):
        self.received = audio
        if self.fail:
            raise RuntimeError("ollama fora")
        return self.feedback


class TestSession(unittest.TestCase):
    def _make(self, rec, pipe):
        msgs: list[str] = []
        return Session(rec, pipe, msgs.append), msgs

    def test_dupla_pressao_roda_pipeline(self):
        rec, pipe = _FakeRecorder(audio="A"), _FakePipeline(feedback="ok")
        s, msgs = self._make(rec, pipe)
        s.toggle()                        # 1a: comeca a gravar
        self.assertTrue(s.on and rec.started)
        s.toggle()                        # 2a: encerra e roda o pipeline
        self.assertFalse(s.on)
        self.assertEqual(pipe.received, "A")
        self.assertIn("ok", msgs)

    def test_erro_no_mic_mantem_off(self):
        s, msgs = self._make(_FakeRecorder(fail_start=True), _FakePipeline())
        s.toggle()
        self.assertFalse(s.on)            # nao entrou em gravacao
        self.assertTrue(any("microfone" in m for m in msgs))

    def test_erro_ao_parar_nao_roda_pipeline(self):
        pipe = _FakePipeline()
        s, msgs = self._make(_FakeRecorder(fail_stop=True), pipe)
        s.toggle()                        # grava
        s.toggle()                        # encerra -> stop falha
        self.assertFalse(s.on)
        self.assertIsNone(pipe.received)  # pipeline nao roda
        self.assertTrue(any("encerrar" in m for m in msgs))

    def test_erro_no_pipeline_notifica_e_reseta(self):
        s, msgs = self._make(_FakeRecorder(audio="A"), _FakePipeline(fail=True))
        s.toggle()                        # grava
        s.toggle()                        # encerra -> pipeline falha
        self.assertFalse(s.on)
        self.assertTrue(any("pipeline" in m for m in msgs))


if __name__ == "__main__":
    unittest.main()
