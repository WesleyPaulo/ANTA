"""Testes do Pipeline com fakes (sem STT/LLM/RAG reais): foca no wiring novo da v0.3
— canal automatico de memoria, guard anti-duplicata do Lembrar e a janela de conversa."""
import tempfile
import unittest
from pathlib import Path

from anta.actions.schema import Decisao, Lembrar, Responder
from anta.core.pipeline import Pipeline


class _FakeTranscriber:
    def __init__(self, text):
        self.text = text

    def load(self):
        pass

    def transcribe(self, audio):
        return self.text


class _FakeBrain:
    def __init__(self, decisao):
        self.decisao = decisao
        self.history_seen = None

    def decide(self, texto, history=None):
        self.history_seen = history
        return self.decisao

    def warm(self):
        pass

    def answer(self, pergunta, contexto):
        return "sintese"


class _FakeRag:
    def ensure_ready(self):
        pass

    def query(self, pergunta, k=5):
        return []


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def _pipeline(self, text, decisao, with_rag=True):
        p = Pipeline(stt_key="turbo", llm="x", obsidian_vault=str(self.vault), rag=False)
        p.transcriber = _FakeTranscriber(text)
        p.brain = _FakeBrain(decisao)
        if with_rag:
            p.rag = _FakeRag()
            p.ctx.rag = p.rag
        return p

    def _memoria_notas(self):
        d = self.vault / "memoria"
        return list(d.glob("*.md")) if d.exists() else []

    def test_canal_automatico_escreve_memoria(self):
        dec = Decisao(escolha=Responder(texto="ok"), memoria="prefiro documentos em docx")
        p = self._pipeline("faca X", dec)
        fb = p.run(None)
        self.assertEqual(fb, "ok")
        notas = self._memoria_notas()
        self.assertEqual(len(notas), 1)
        self.assertIn("prefiro documentos em docx", notas[0].read_text(encoding="utf-8"))

    def test_canal_automatico_com_falha_nao_derruba_o_comando(self):
        # regressao (review #1): se a escrita da memoria falha, o feedback ja
        # computado sobrevive e o turno entra no historico.
        dec = Decisao(escolha=Responder(texto="ok"), memoria="fato")
        p = self._pipeline("faca X", dec)
        import anta.core.pipeline as mod
        orig = mod.write_memory_note
        mod.write_memory_note = lambda *a, **k: (_ for _ in ()).throw(OSError("disco cheio"))
        try:
            fb = p.run(None)
        finally:
            mod.write_memory_note = orig
        self.assertEqual(fb, "ok")            # comando primario preservado
        self.assertEqual(len(p._history), 1)  # turno nao foi perdido

    def test_sem_memoria_nao_escreve(self):
        p = self._pipeline("oi", Decisao(escolha=Responder(texto="ok")))
        p.run(None)
        self.assertEqual(self._memoria_notas(), [])

    def test_lembrar_nao_duplica_pelo_canal_automatico(self):
        # acao Lembrar (handler grava 1 nota) + memoria preenchida: o canal deve PULAR
        dec = Decisao(escolha=Lembrar(fato="prefiro docx"), memoria="prefiro docx")
        p = self._pipeline("lembre que prefiro docx", dec)
        fb = p.run(None)
        self.assertEqual(len(self._memoria_notas()), 1)  # so a do handler; canal pulou
        self.assertIn("Vou lembrar", fb)

    def test_janela_de_conversa_cresce_e_chega_ao_decide(self):
        p = self._pipeline("primeira fala", Decisao(escolha=Responder(texto="ok")))
        p.run(None)
        self.assertEqual(p.brain.history_seen, [])          # 1a: sem historico
        self.assertEqual(len(p._history), 1)
        p.run(None)
        self.assertEqual(len(p.brain.history_seen), 1)       # 2a: ve o 1o turno
        self.assertEqual(p.brain.history_seen[0], ("primeira fala", "responder"))

    def test_transcricao_vazia_nao_registra_turno(self):
        p = self._pipeline("", Decisao(escolha=Responder(texto="ok")))
        fb = p.run(None)
        self.assertIn("Nao entendi", fb)
        self.assertEqual(len(p._history), 0)

    def test_rag_desligado_ainda_grava_memoria(self):
        dec = Decisao(escolha=Responder(texto="ok"), memoria="fato durável")
        p = self._pipeline("x", dec, with_rag=False)
        p.run(None)
        self.assertEqual(len(self._memoria_notas()), 1)  # escreve mesmo sem indexar


if __name__ == "__main__":
    unittest.main()
