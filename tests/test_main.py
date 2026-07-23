import unittest

from anta.__main__ import Session, _short_err, _to_pynput_hotkey


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
    def __init__(self, feedback="feito", fail=False, exc=None, progresso=()):
        self.feedback = feedback
        self.fail = fail or exc is not None
        self.exc = exc or RuntimeError("ollama fora")
        self.received = None
        self.progresso = progresso  # mensagens que o pipeline emite via on_progress

    def run(self, audio, on_progress=None, on_state=None):
        self.received = audio
        for m in self.progresso:
            if on_progress is not None:
                on_progress(m)
        if self.fail:
            raise self.exc
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

    def test_erro_gigante_nao_vaza_pra_notificacao(self):
        """Regressao: o erro do instructor embute o ChatCompletion inteiro; com
        modelo de raciocinio isso viravam kBs de <think> num notify-send."""
        gigante = RuntimeError("<failed_attempts>" + "x" * 9000)
        s, msgs = self._make(_FakeRecorder(audio="A"), _FakePipeline(exc=gigante))
        s.toggle()
        s.toggle()
        (erro,) = [m for m in msgs if m.startswith("erro no pipeline")]
        self.assertLess(len(erro), 260)
        self.assertTrue(erro.endswith("..."))

    def test_progresso_do_pipeline_chega_ao_usuario(self):
        # sem isso o fluxo audio->texto->acao e caixa preta: quando a ANTA responde
        # algo estranho, nao da pra saber se ela ouviu errado ou decidiu errado
        pipe = _FakePipeline(feedback="ok", progresso=['ouvi: "oi"', "acao: responder"])
        s, msgs = self._make(_FakeRecorder(audio="A"), pipe)
        s.toggle()
        s.toggle()
        self.assertIn('ouvi: "oi"', msgs)
        self.assertIn("acao: responder", msgs)
        self.assertLess(msgs.index('ouvi: "oi"'), msgs.index("ok"))  # antes do feedback

    def test_avisa_que_voltou_a_ouvir(self):
        s, msgs = self._make(_FakeRecorder(audio="A"), _FakePipeline(feedback="ok"))
        s.toggle()
        s.toggle()
        self.assertEqual(msgs[-1], "pronto — aperte o atalho para falar de novo.")

    def test_avisa_que_voltou_a_ouvir_mesmo_com_erro(self):
        s, msgs = self._make(_FakeRecorder(audio="A"), _FakePipeline(fail=True))
        s.toggle()
        s.toggle()
        self.assertEqual(msgs[-1], "pronto — aperte o atalho para falar de novo.")


class TestSessionStates(unittest.TestCase):
    """Canal on_state (M3): estados tipados p/ a GUI. O daemon CLI passa None."""

    def _capture(self, rec, pipe):
        states: list[str] = []
        s = Session(rec, pipe, notify=lambda *_: None,
                    on_state=lambda state, **_: states.append(state))
        return s, states

    def test_sequencia_feliz(self):
        # o fake pipeline nao emite 'respondendo' (so o Pipeline real emite);
        # aqui checamos os estados que o Session controla.
        s, states = self._capture(_FakeRecorder(audio="A"), _FakePipeline(feedback="ok"))
        s.toggle()  # 1a pressao
        s.toggle()  # 2a pressao
        self.assertEqual(states, ["ouvindo", "processando", "pronto"])

    def test_erro_no_mic_emite_erro(self):
        s, states = self._capture(_FakeRecorder(fail_start=True), _FakePipeline())
        s.toggle()
        self.assertEqual(states, ["erro"])  # nao entrou em 'ouvindo'

    def test_erro_no_pipeline_fica_no_erro(self):
        # o HUD mostra o erro e FICA nele ate a proxima fala (nao sobrescreve com pronto)
        s, states = self._capture(_FakeRecorder(audio="A"), _FakePipeline(fail=True))
        s.toggle()
        s.toggle()
        self.assertEqual(states, ["ouvindo", "processando", "erro"])

    def test_pronto_carrega_a_resposta(self):
        # regressao: a resposta so ia pro log; agora o PRONTO leva o texto pro HUD
        payloads = []
        s = Session(_FakeRecorder(audio="A"), _FakePipeline(feedback="a resposta"),
                    notify=lambda *_: None,
                    on_state=lambda state, **pl: payloads.append((state, pl)))
        s.toggle()
        s.toggle()
        pronto = [pl for st, pl in payloads if st == "pronto"]
        self.assertEqual(pronto[-1].get("text"), "a resposta")

    def test_cli_sem_on_state_nao_quebra(self):
        # regressao: o daemon CLI nao passa on_state -> emit() vira no-op
        s = Session(_FakeRecorder(audio="A"), _FakePipeline(feedback="ok"), lambda *_: None)
        s.toggle()
        s.toggle()  # nao pode levantar


class _FakePipelineCancelavel(_FakePipeline):
    """Pipeline que registra o cancel() e roda um callback no meio do turno —
    e assim que a GUI chega: outra thread apertando 'Parar' com o run() em curso."""

    def __init__(self, durante=None, **kw):
        super().__init__(**kw)
        self.cancelado = False
        self._durante = durante

    def cancel(self):
        self.cancelado = True

    def run(self, audio, on_progress=None, on_state=None):
        if self._durante is not None:
            self._durante()
        return super().run(audio, on_progress=on_progress, on_state=on_state)


class TestSessionRequest(unittest.TestCase):
    """`request()` e a entrada UNICA dos gatilhos (atalho, SIGUSR1, botao, bandeja).

    Regressao da v0.4.3: o gatilho so ARMAVA o Event. Apertar 'Falar' enquanto a
    ANTA falava nao parava nada e ainda deixava o Event armado — o turno acabava e
    comecava uma gravacao que ninguem pediu."""

    def _sessao(self, pipe=None, rec=None):
        msgs: list[str] = []
        estados: list[str] = []
        s = Session(rec or _FakeRecorder(audio="A"), pipe or _FakePipelineCancelavel(),
                    notify=msgs.append, on_state=lambda st, **_: estados.append(st))
        return s, msgs, estados

    def test_ocioso_arma_o_gatilho(self):
        s, _msgs, _e = self._sessao()
        s.request()
        self.assertTrue(s.trigger.is_set())

    def test_durante_o_turno_cancela_em_vez_de_enfileirar(self):
        pipe = _FakePipelineCancelavel()
        s, _msgs, _e = self._sessao(pipe)
        pipe._durante = s.request        # 'Parar' apertado no meio do run()
        s.toggle()                       # grava
        s.toggle()                       # encerra -> roda o pipeline (e cancela dentro)
        self.assertTrue(pipe.cancelado)
        self.assertFalse(s.trigger.is_set())  # NAO ficou gravacao armada
        self.assertFalse(s.busy)

    def test_suspenso_ignora_o_gatilho(self):
        s, msgs, estados = self._sessao()
        s.suspend()
        s.request()
        self.assertFalse(s.trigger.is_set())
        self.assertFalse(s.on)
        self.assertIn("descarregado", estados)
        self.assertTrue(any("desalocada" in m for m in msgs))

    def test_resume_volta_a_funcionar(self):
        s, _msgs, _e = self._sessao()
        s.suspend()
        s.resume()
        s.request()
        self.assertTrue(s.trigger.is_set())

    def test_cancel_gravando_descarta_o_audio(self):
        rec = _FakeRecorder(audio="A")
        pipe = _FakePipelineCancelavel()
        s, _msgs, estados = self._sessao(pipe, rec)
        s.toggle()                       # gravando
        s.cancel()
        self.assertFalse(s.on)
        self.assertTrue(rec.stopped)
        self.assertIsNone(pipe.received)  # o audio nao virou turno
        self.assertEqual(estados[-1], "pronto")

    def test_suspender_no_meio_do_turno_termina_em_descarregado(self):
        # desalocar memoria enquanto responde: o HUD nao pode voltar pra 'pronto'
        pipe = _FakePipelineCancelavel()
        s, _msgs, estados = self._sessao(pipe)
        pipe._durante = s.suspend
        s.toggle()
        s.toggle()
        self.assertEqual(estados[-1], "descarregado")

    def test_toggle_suspenso_nao_abre_o_microfone(self):
        # corrida: o gatilho foi consumido antes do unload chegar
        rec = _FakeRecorder()
        s, _msgs, estados = self._sessao(rec=rec)
        s.suspend()
        s.toggle()
        self.assertFalse(rec.started)
        self.assertEqual(estados[-1], "descarregado")

    def test_pipeline_sem_cancel_nao_quebra(self):
        # fakes antigos (e o daemon CLI com pipelines injetados) nao tem cancel()
        s, _msgs, _e = self._sessao(_FakePipeline())
        s.busy = True
        s.cancel()  # nao levanta

    def test_trigger_injetado_e_o_mesmo_do_loop(self):
        import threading

        ev = threading.Event()
        s = Session(_FakeRecorder(), _FakePipeline(), lambda *_: None, trigger=ev)
        s.request()
        self.assertTrue(ev.is_set())


class TestShortErr(unittest.TestCase):
    def test_curto_passa_inteiro(self):
        self.assertEqual(_short_err(ValueError("falhou feio")), "falhou feio")

    def test_colapsa_quebras_de_linha(self):
        self.assertEqual(_short_err(ValueError("a\n  b\n\nc")), "a b c")

    def test_trunca_com_reticencias(self):
        self.assertEqual(len(_short_err(ValueError("y" * 500), limite=50)), 53)

    def test_excecao_sem_mensagem_usa_o_tipo(self):
        self.assertEqual(_short_err(TimeoutError()), "TimeoutError")


if __name__ == "__main__":
    unittest.main()
