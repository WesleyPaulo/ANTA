"""Entrypoint.

  python -m anta          -> abre o instalador (TUI) — fallback headless
  python -m anta config   -> abre o Configurador (GUI PyWebview + Vue)
  python -m anta app      -> abre o App de execucao (HUD na bandeja; push-to-talk)
  python -m anta run      -> roda o assistente (daemon quente, sem GUI, push-to-talk)
  python -m anta toggle   -> alterna a gravacao do daemon (usado pelo atalho do SO
                            no Wayland, onde apps nao capturam teclas globais)
  python -m anta mic      -> diagnostico do microfone (device resolvido + nivel do sinal)
  python -m anta vozes    -> lista/instala vozes do TTS (catalogo Piper ou voz sua)
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import threading
from pathlib import Path

from anta.core.states import State, emit

# Evento disparado por qualquer fonte de atalho (pynput ou SIGUSR1).
_trigger = threading.Event()


def _pidfile():
    from anta.core.config import config_dir

    return config_dir() / "anta.pid"


def _notify(msg: str) -> None:
    """Feedback curto: notify-send no Linux, print sempre."""
    print(f"[anta] {msg}")
    if sys.platform.startswith("linux") and shutil.which("notify-send"):
        try:
            subprocess.run(["notify-send", "anta", msg], timeout=5, check=False)
        except (OSError, subprocess.SubprocessError):
            pass


def _short_err(e: BaseException, limite: int = 200) -> str:
    """Erro -> uma linha curta, pra notificacao.

    Os erros do instructor embutem o ChatCompletion inteiro — com modelo de
    raciocinio isso vira alguns kB de <think> na cara do usuario. O traceback
    completo vai pro console (stderr); aqui fica so o resumo.
    """
    txt = " ".join(str(e).split()) or e.__class__.__name__
    return txt if len(txt) <= limite else f"{txt[:limite].rstrip()}..."


def _to_pynput_hotkey(hotkey: str) -> str:
    """'ctrl+alt+space' -> '<ctrl>+<alt>+<space>' (formato do pynput)."""
    special = {"ctrl", "alt", "shift", "cmd", "super", "win", "space",
               "enter", "tab", "esc", "escape", "up", "down", "left", "right"}
    alias = {"super": "cmd", "win": "cmd", "escape": "esc"}
    parts = []
    for raw in hotkey.split("+"):
        tok = raw.strip().lower()
        if tok in special:
            parts.append(f"<{alias.get(tok, tok)}>")
        else:
            parts.append(tok)
    return "+".join(parts)


class Session:
    """Maquina de estado do push-to-talk: alterna gravar/encerrar e roda o
    pipeline ao encerrar. Isolada de run() (que so faz wiring de ciclo de vida)
    para ser testavel com fakes de recorder/pipeline/notify.

    `request()` e a entrada UNICA de qualquer gatilho (atalho global, SIGUSR1,
    botao do HUD, menu da bandeja) e e segura de chamar de qualquer thread: ela
    ROTEIA por estado em vez de sempre enfileirar uma gravacao. Sem isso um
    clique enquanto a ANTA respondia (ou falava) nao parava nada e ainda deixava
    o gatilho armado — assim que o turno acabava, comecava uma gravacao fantasma.
    """

    def __init__(self, recorder, pipeline, notify=_notify, on_state=None,
                 trigger=None) -> None:
        self.recorder = recorder
        self.pipeline = pipeline
        self.notify = notify
        self.on_state = on_state  # None no daemon CLI -> emit() vira no-op
        self.trigger = trigger if trigger is not None else threading.Event()
        self.on = False           # gravando
        self.busy = False         # pipeline rodando (transcreve/decide/executa/fala)
        self.suspended = False    # memoria desalocada: ignora gatilhos ate carregar

    # --- entrada unica dos gatilhos (thread-safe) ---
    def request(self) -> None:
        """Gatilho apertado. Suspenso -> so lembra; respondendo -> para; senao grava."""
        if self.suspended:
            self.notify("memoria desalocada — carregue de novo para usar a ANTA.")
            emit(self.on_state, State.DESCARREGADO)
            return
        if self.busy:
            self.cancel()
            return
        self.trigger.set()

    def cancel(self) -> None:
        """Para o que estiver em andamento: gravacao (descarta) ou turno/fala.

        Chamada da thread da GUI enquanto a worker esta dentro de `toggle()` —
        por isso so mexe em flags e no `sd.stop()` (via Pipeline.cancel)."""
        if self.on:  # gravando: encerra e joga o audio fora
            self.on = False
            try:
                self.recorder.stop()
            except Exception:  # noqa: BLE001 - descartando mesmo; nao ha o que salvar
                pass
            self.notify("gravacao descartada.")
            emit(self.on_state, State.PRONTO)
            return
        cancel = getattr(self.pipeline, "cancel", None)
        if callable(cancel):
            cancel()

    def suspend(self) -> None:
        """Desalocar memoria: para o que houver e passa a ignorar os gatilhos."""
        self.cancel()
        self.suspended = True
        self.trigger.clear()  # descarta gatilho ja enfileirado

    def resume(self) -> None:
        self.suspended = False

    def toggle(self) -> None:
        if self.suspended and not self.on:
            # corrida: o gatilho ja tinha sido consumido quando o unload chegou.
            # Abrir o microfone agora contrariaria o "desalocar" que acabou de rodar.
            emit(self.on_state, State.DESCARREGADO)
            return
        if not self.on:
            try:
                self.recorder.start()
                self.on = True
                self.notify("gravando... (aperte de novo para encerrar)")
                emit(self.on_state, State.OUVINDO)
            except Exception as e:  # noqa: BLE001
                self.notify(f"nao consegui abrir o microfone: {e}")
                emit(self.on_state, State.ERRO, code="mic", text=str(e))
            return
        # 2a pressao: encerra e roda o pipeline
        self.on = False
        try:
            audio = self.recorder.stop()
        except Exception as e:  # noqa: BLE001
            self.notify(f"erro ao encerrar a gravacao: {e}")
            emit(self.on_state, State.ERRO, text=str(e))
            return
        self.notify("processando...")
        emit(self.on_state, State.PROCESSANDO)
        self.busy = True  # a partir daqui o gatilho vira "parar", nao "gravar"
        try:
            feedback = self.pipeline.run(audio, on_progress=self.notify, on_state=self.on_state)
        except Exception as e:  # noqa: BLE001
            import traceback

            traceback.print_exc()  # vai pro anta.log (app de janela nao tem console)
            short = _short_err(e)
            self.notify(f"erro no pipeline: {short}")
            self.notify("pronto — aperte o atalho para falar de novo.")
            # HUD mostra o erro e FICA nele ate a proxima fala (nao sobrescreve com pronto).
            emit(self.on_state, State.ERRO, text=short)
            return
        finally:
            self.busy = False
        if self.suspended:  # desalocou no meio do turno: nao anuncia "pronto"
            emit(self.on_state, State.DESCARREGADO)
            return
        self.notify(feedback)
        # o loop ja volta a esperar o atalho quando toggle() retorna, mas nada
        # dizia isso: o usuario ficava sem saber se a ANTA morreu ou esta pronta.
        self.notify("pronto — aperte o atalho para falar de novo.")
        # PRONTO carrega a RESPOSTA -> o HUD exibe o texto (antes so ia pro log/voz).
        emit(self.on_state, State.PRONTO, text=feedback)


def install_sigusr1(session) -> None:
    """SIGUSR1 (`anta toggle`) -> `session.request()`, via thread despachante.

    O handler de sinal so seta um Event (regra do guia: nada pesado no handler);
    quem roteia — e eventualmente chama `sd.stop()` pra cortar a fala — e uma
    thread daemon normal. Sem essa indirecao, cancelar pelo atalho no Wayland
    rodaria audio de dentro do signal handler."""
    if not hasattr(signal, "SIGUSR1"):
        return  # Windows: o atalho e capturado in-process
    pulso = threading.Event()
    signal.signal(signal.SIGUSR1, lambda *_: pulso.set())

    def _pump() -> None:
        while True:
            pulso.wait()
            pulso.clear()
            try:
                session.request()
            except Exception:  # noqa: BLE001 - um gatilho ruim nao mata o despachante
                import traceback

                traceback.print_exc()

    threading.Thread(target=_pump, daemon=True).start()


def run() -> None:
    from anta.core.config import config_path, load_families, load_user_config
    from anta.core.capture import Recorder
    from anta.core.pipeline import Pipeline
    from anta.platform.detect import detect
    from anta.platform.hotkey import default_command, instructions_for

    cfg = load_user_config()
    families = load_families()
    family = cfg.family_or_default(families)
    mode = cfg.mode_or_default(family.modes)

    # Este e o modo HEADLESS: carrega o Whisper e fixa o LLM na VRAM sem janela, sem
    # bandeja e (no build empacotado) sem console. Se o HUD existe, o item de login
    # nao deveria apontar pra ca — era assim ate a v0.4.3, e do lado de fora a ANTA
    # sumia: nada na tela, nada na bandeja, so a memoria ocupada.
    try:
        from anta.platform.hotkey import default_command, hud_available, repair_autostart

        if hud_available():
            corrigido = repair_autostart()
            if corrigido:
                _notify(corrigido)
            _notify(f"modo headless (sem janela e sem bandeja). Para a interface: "
                    f"{default_command()} app")
    except Exception:  # noqa: BLE001 - diagnostico nunca derruba o boot
        pass

    # Uma ANTA por vez — a MESMA trava do HUD ("runtime"): `anta run` e `anta app`
    # sao o mesmo assistente com e sem janela. Dois deles = dois Whispers na RAM,
    # dois preloads na VRAM e dois donos do mesmo pidfile.
    from anta.platform.singleton import SingleInstance

    trava = SingleInstance("runtime")
    if not trava.acquire():
        trava.signal_existing()  # se quem esta rodando for o HUD, ele aparece
        _notify("a ANTA ja esta rodando (janela ou daemon). Nao vou subir outra.")
        sys.exit(1)

    _notify(f"iniciando {family.label} / modo '{mode.label}' — carregando modelos...")
    pipeline = Pipeline(
        stt_key=mode.stt, llm=mode.llm,
        obsidian_vault=cfg.obsidian_vault, tts=cfg.tts,
        tts_voice=cfg.tts_voice, tts_output=cfg.tts_output,
        rag=cfg.rag, web=cfg.web, web_engine=cfg.web_engine,
        web_searxng_url=cfg.web_searxng_url, structured=mode.structured,
    )
    try:
        aviso = pipeline.warm()
    except Exception as e:  # noqa: BLE001 - nao deixar o boot morrer por causa do STT
        _notify(f"aviso: falha ao carregar STT ({e}). Vou tentar sob demanda.")
    else:
        if aviso:  # LLM nao ficou quente (modelo ausente, Ollama fora do ar...)
            _notify(f"aviso: {aviso}")

    recorder = Recorder(cfg.mic_device)
    session = Session(recorder, pipeline, _notify, trigger=_trigger)

    # pidfile para o `anta toggle` achar este processo
    pid_path = _pidfile()
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    pid_path.write_text(str(os.getpid()), encoding="utf-8")

    # SIGUSR1 -> dispara o toggle (Wayland/manual e universal em POSIX)
    install_sigusr1(session)

    env = detect()
    listener = None
    toggle_cmd = f"{default_command()} toggle"
    if env.captures_hotkey_in_process:
        try:
            from pynput import keyboard

            listener = keyboard.GlobalHotKeys(
                {_to_pynput_hotkey(cfg.hotkey): session.request}
            )
            listener.start()
            _notify(f"ouvindo atalho {cfg.hotkey}. Fale apos apertar.")
        except Exception as e:  # noqa: BLE001
            _notify(f"nao consegui registrar {cfg.hotkey} in-process ({e}). "
                    f"Use: {toggle_cmd} (vincule ao atalho do SO).")
    else:
        _notify(instructions_for(env, toggle_cmd))
        _notify(f"daemon quente. Config em {config_path()}. "
                f"Vincule o atalho do SO a: {toggle_cmd}")

    try:
        while True:
            _trigger.wait()
            _trigger.clear()
            session.toggle()
    except KeyboardInterrupt:
        pass
    finally:
        if listener is not None:
            listener.stop()
        pid_path.unlink(missing_ok=True)
        trava.release()


def toggle_daemon() -> None:
    """`anta toggle`: sinaliza o daemon (`anta run`) para alternar a gravacao."""
    from anta.platform.hotkey import default_command

    if not hasattr(signal, "SIGUSR1"):  # Windows
        print("[anta] 'anta toggle' e para Linux (Wayland/manual). No Windows o "
              "atalho e capturado in-process pelo proprio 'anta run'.")
        sys.exit(1)
    pid_path = _pidfile()
    if not pid_path.exists():
        print(f"[anta] daemon nao esta rodando. Inicie com: {default_command()} run")
        sys.exit(1)
    try:
        pid = int(pid_path.read_text(encoding="utf-8").strip())
        os.kill(pid, signal.SIGUSR1)
    except (ValueError, ProcessLookupError, PermissionError, OSError) as e:
        print(f"[anta] nao consegui sinalizar o daemon ({e}). "
              f"Reinicie com: {default_command()} run")
        pid_path.unlink(missing_ok=True)
        sys.exit(1)


def mic_check(segundos: float = 4.0) -> None:
    """`anta mic`: diagnostico do microfone. Lista os devices (com host API) e grava,
    medindo o nivel do sinal.

    Existe porque um mic mudo e indistinguivel de um LLM burro pelo lado de fora: o
    Whisper alucina em cima do silencio ("E ai"), o modelo responde a alucinacao, e a
    culpa parece ser do modelo. Aqui o numero e o pico do sinal — sem interpretacao.
    """
    import time

    try:
        import sounddevice as sd
    except OSError as e:  # PortAudio ausente (Linux sem libportaudio2; nao ocorre no Windows)
        print(f"[anta] audio indisponivel: {e}\n"
              f"   Linux: instale a libportaudio2 (o install.sh faz isso).")
        return

    from anta.core.capture import SAMPLE_RATE, Recorder, _resolve_device, audio_level
    from anta.core.config import load_user_config

    cfg = load_user_config()
    apis = sd.query_hostapis()
    print("[anta] microfones detectados:")
    for idx, d in enumerate(sd.query_devices()):
        if d.get("max_input_channels", 0) <= 0:
            continue
        api = apis[d["hostapi"]]["name"]
        print(f"   [{idx:2}] {d['name']!r}  ({api}, {d['max_input_channels']}ch, "
              f"{d['default_samplerate']:.0f} Hz)")

    escolhido = _resolve_device(cfg.mic_device)
    print(f"\n[anta] na config: {cfg.mic_device!r}")
    if escolhido is None:
        print("[anta] resolvido para: (default do sistema)"
              + ("" if cfg.mic_device else " — nenhum nome salvo"))
    else:
        d = sd.query_devices()[escolhido]
        print(f"[anta] resolvido para: [{escolhido}] {d['name']!r} "
              f"({apis[d['hostapi']]['name']})")

    rec = Recorder(cfg.mic_device)
    try:
        rec.start()
    except Exception as e:  # noqa: BLE001
        print(f"[anta] FALHA ao abrir o microfone: {e}")
        return
    print(f"\n[anta] gravando {segundos:.0f}s — FALE AGORA, alto e claro...")
    time.sleep(segundos)
    audio = rec.stop()
    pico, rms = audio_level(audio)
    print(f"[anta] resultado: {len(audio) / SAMPLE_RATE:.1f}s | pico {pico:.4f} | rms {rms:.4f}")

    if pico == 0.0:
        print("[anta] SILENCIO DIGITAL (zero absoluto). O stream abriu mas nao chega som:\n"
              "   - Privacidade do Windows: Configuracoes > Privacidade > Microfone,\n"
              "     ligue 'Permitir que aplicativos da area de trabalho acessem'.\n"
              "   - O mic pode estar mudo no mixer ou com o botao fisico de mute ligado.\n"
              "   - Tente outro device da lista acima (reinstale com 'anta' e escolha outro).")
    elif pico < 0.01:
        print("[anta] praticamente silencio: o mic capta, mas o nivel esta baixissimo.\n"
              "   Aumente o volume/ganho do microfone nas configuracoes de som do Windows.")
    elif pico < 0.05:
        print("[anta] nivel baixo — deve funcionar, mas o STT vai errar mais. Aumente o ganho.")
    else:
        print("[anta] nivel OK. O microfone esta captando sua voz.")


def voices_cli(args: list[str]) -> None:
    """`anta vozes` lista; `anta vozes <nome-ou-caminho-ou-url>` instala e passa a usar.

    Aceita tanto uma voz do catalogo oficial quanto QUALQUER voz Piper (.onnx local ou
    URL) — o Piper so precisa do par .onnx + .onnx.json, nao ha catalogo fechado.
    """
    from anta.core.config import load_user_config, save_user_config
    from anta.core.tts import (
        AMOSTRAS_URL, VOZES_COMUNIDADE, VOZES_PT, default_voice_path, import_voice,
        voices_dir,
    )

    cfg = load_user_config()
    atual = cfg.tts_voice or str(default_voice_path())

    if not args:
        print("[anta] vozes em portugues do catalogo oficial do Piper:")
        for nome, desc in VOZES_PT.items():
            marca = " <- em uso" if Path(atual).name.startswith(nome) else ""
            print(f"   {nome:22} {desc}{marca}")
        print("\n[anta] vozes da comunidade (fora do catalogo, conferidas):")
        for nome, (_url, desc) in VOZES_COMUNIDADE.items():
            marca = " <- em uso" if Path(atual).name.startswith(nome) else ""
            print(f"   {nome:22} {desc}{marca}")
        print(f"\n   Nenhuma fonte informa GENERO das vozes; o F0 acima e medido (registro"
              f" grave/agudo)\n   e nao prova genero. Para decidir, ouca: {AMOSTRAS_URL}")
        print(f"\n[anta] instaladas em {voices_dir()}:")
        instaladas = sorted(p.name for p in voices_dir().glob("*.onnx")) \
            if voices_dir().exists() else []
        for n in instaladas:
            print(f"   {n}{'  <- em uso' if n == Path(atual).name else ''}")
        print(f"   (nenhuma)" if not instaladas else "", end="" if instaladas else "\n")
        print("\n[anta] para usar outra voz:")
        print("   anta vozes pt_BR-cadu-medium              (do catalogo oficial)")
        print("   anta vozes C:\\caminho\\minha-voz.onnx      (voz Piper sua)")
        print("   anta vozes https://.../voz.onnx           (qualquer voz Piper na web)")
        print("   Fora do catalogo, o .onnx.json tem que estar ao lado (mesmo nome + .json).")
        return

    alvo = args[0]
    try:
        if alvo in VOZES_COMUNIDADE:  # antes do catalogo: nao esta no repo oficial -> 404
            url, _ = VOZES_COMUNIDADE[alvo]
            print(f"[anta] baixando '{alvo}' (voz da comunidade)...")
            caminho = import_voice(url, nome=alvo)
        elif alvo in VOZES_PT or (alvo.count("-") == 2 and not Path(alvo).suffix):
            from anta.core.tts import ensure_voice

            print(f"[anta] baixando '{alvo}' do catalogo oficial...")
            caminho = ensure_voice(alvo)
        else:
            print(f"[anta] importando voz de {alvo}...")
            caminho = import_voice(alvo)
    except Exception as e:  # noqa: BLE001 - erro de rede/arquivo: dizer, nao explodir
        print(f"[anta] falhou: {e}")
        if not str(alvo).endswith(".onnx"):
            print("   Nomes do catalogo seguem <locale>-<speaker>-<qualidade> "
                  "(ex.: pt_BR-cadu-medium). Rode 'anta vozes' para ver a lista.")
        else:
            print("   Uma voz Piper e o par <voz>.onnx + <voz>.onnx.json — os dois "
                  "precisam existir lado a lado.")
        sys.exit(1)

    cfg.tts_voice = str(caminho)
    if not cfg.tts:
        cfg.tts = True
        print("[anta] TTS estava desligado; liguei.")
    save_user_config(cfg)
    print(f"[anta] voz ativa: {caminho}")
    print("[anta] reinicie o 'anta run' para valer.")


def main() -> None:
    arg = sys.argv[1] if len(sys.argv) > 1 else ""
    if arg == "run":
        run()
        return
    if arg in ("vozes", "voices"):
        voices_cli(sys.argv[2:])
        return
    if arg == "toggle":
        toggle_daemon()
        return
    if arg == "mic":
        mic_check()
        return
    if arg == "config":  # Configurador GUI (PyWebview + Vue)
        from anta.gui.config_app import main as config_gui

        config_gui()
        return
    if arg == "app":  # App de execucao GUI (HUD residente na bandeja)
        from anta.gui.runtime_app import main as runtime_gui

        runtime_gui()
        return
    # Sem argumento: a TUI Textual fica como fallback headless (SSH/servidor/sem
    # display). Nos builds empacotados a GUI vira o padrao (via launcher, fase M5).
    from anta.installer.app import main as installer

    installer()


if __name__ == "__main__":
    main()
