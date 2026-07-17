"""Orquestrador: cola as pecas do fluxo push-to-talk.

    toggle (2a pressao) -> Recorder.stop() -> Transcriber -> Brain -> execute -> feedback

Memoria (v0.3): curto prazo = janela de conversa em RAM (deque, zera ao reiniciar),
injetada no decide() para resolver referencias. Longo prazo = notas em <vault>/memoria/
indexadas pelo RAG (persistente). O canal automatico grava fatos duraveis que o LLM
sinaliza em decisao.memoria.
"""
from __future__ import annotations

from collections import deque

from anta.actions.executor import ExecContext, execute
from anta.actions.helpers import write_memory_note
from anta.actions.schema import Lembrar
from anta.core.brain import Brain
from anta.core.capture import MIN_SECONDS, SAMPLE_RATE, SILENCE_PEAK, audio_level
from anta.core.stt import Transcriber

HISTORY_TURNS = 5  # janela de conversa (RAM); cap curto p/ nao estourar contexto do 4B


class Pipeline:
    def __init__(
        self,
        stt_key: str,
        llm: str,
        obsidian_vault: str | None = None,
        tts: bool = False,
        tts_voice: str | None = None,
        tts_output: str | None = None,
        rag: bool = False,
        web: bool = False,
        web_engine: str = "duckduckgo",
        web_searxng_url: str | None = None,
        structured: str = "tools",
    ) -> None:
        self.transcriber = Transcriber(stt_key)
        self.brain = Brain(llm, structured=structured)
        self.ctx = ExecContext.from_config(obsidian_vault, tts, tts_voice, tts_output)
        self.rag = None
        if rag:
            from anta.core.rag import RAG  # import so quando ligado (puxa numpy/fastembed)

            self.rag = RAG(self.ctx.vault)
        # injeta os colaboradores de runtime no contexto dos handlers
        self.ctx.rag = self.rag
        self.ctx.answer = self.brain.answer
        self.ctx.summarize = self.brain.summarize
        # Redacao de notas (expandir=true). O lambda le self._history NA HORA da chamada,
        # entao a nota cobre o que se vinha conversando ("anota isso numa nota"). Nesse
        # ponto o turno atual ainda nao entrou no historico — e certo: ele e o pedido.
        self.ctx.write = lambda titulo, esboco: self.brain.write(
            titulo, esboco, list(self._history))
        if web:  # OPT-IN: rompe o offline; so entao ligamos o buscador
            from anta.core import websearch

            self.ctx.web_search = lambda q: websearch.search(
                q, engine=web_engine, searxng_url=web_searxng_url)
        self._history: deque[tuple[str, str]] = deque(maxlen=HISTORY_TURNS)

    def warm(self) -> str | None:
        """Carrega o Whisper e fixa o LLM na VRAM no boot para nao pagar o custo
        na 1a fala (STT na CPU; LLM via keep_alive=-1 no Ollama). O indice RAG e
        pre-aquecido em thread best-effort — a corretude e lazy no 1o uso.

        Devolve o aviso do preload do LLM (ver Brain.warm) ou None se deu tudo certo."""
        self.transcriber.load()
        aviso = self.brain.warm()
        if self.rag is not None:
            self._prewarm_rag()
        return aviso

    def _prewarm_rag(self) -> None:
        import threading

        def _job() -> None:
            try:
                self.rag.ensure_ready()
            except Exception:  # noqa: BLE001 - best-effort; nao derruba o boot
                pass

        threading.Thread(target=_job, daemon=True).start()

    def run(self, audio, on_progress=None) -> str:
        """Recebe o audio ja gravado e devolve a mensagem de feedback.

        `on_progress(msg)` (opcional) recebe os passos intermediarios — hoje o que o
        STT ouviu. Sem isso o fluxo audio->texto->acao e uma caixa preta: quando a ANTA
        responde algo estranho, nao da pra saber se ela ouviu errado ou decidiu errado.
        """
        segundos = len(audio) / SAMPLE_RATE
        if segundos < MIN_SECONDS:
            return f"Gravacao curta demais ({segundos:.1f}s) — nao deu tempo de falar."
        pico, rms = audio_level(audio)
        if on_progress is not None:
            on_progress(f"audio: {segundos:.1f}s, pico {pico:.3f}, rms {rms:.4f}")
        if pico < SILENCE_PEAK:
            # NAO transcrever: o Whisper inventa frases em cima de silencio ("E ai",
            # "Obrigado") e o LLM responde a alucinacao com toda a confianca. O usuario
            # culpa o modelo por um problema de microfone. Diga a verdade.
            return (f"O microfone nao captou audio (pico {pico:.3f} em {segundos:.1f}s). "
                    f"Rode 'anta mic' para diagnosticar.")
        texto = self.transcriber.transcribe(audio)
        if not texto:
            return "Nao entendi — nada foi transcrito."
        if on_progress is not None:
            on_progress(f'ouvi: "{texto}"')
        decisao = self.brain.decide(texto, list(self._history))
        if on_progress is not None:
            on_progress(f"acao: {self._rotulo(decisao)}")
        feedback = execute(decisao, self.ctx)
        # canal AUTOMATICO de memoria: grava o fato duravel sinalizado pelo LLM.
        # Pula quando a acao ja e Lembrar (o handler ja gravou) -> evita duplicata.
        # BEST-EFFORT: um efeito colateral suplementar NUNCA derruba o comando ja
        # bem-sucedido nem faz perder o turno do historico (o RAG indexa no query).
        if decisao.memoria and not isinstance(decisao.escolha, Lembrar):
            try:
                write_memory_note(self.ctx.vault, decisao.memoria)
            except Exception:  # noqa: BLE001 - memoria automatica e best-effort
                pass
        self._history.append((texto, self._rotulo(decisao)))
        return feedback

    @staticmethod
    def _rotulo(decisao) -> str:
        """Rotulo compacto do turno p/ a janela de conversa (o tipo da acao)."""
        return getattr(decisao.escolha, "acao", "responder")
