"""Instalador em TUI (Textual). Roda identico em Windows e Linux.

Fluxo:
  1. detecta VRAM (hardware.best_vram_gb)
  2. carrega familias/modos (config.load_families)
  3. mostra tabela colorida: verde=cabe / amarelo=apertado / vermelho=nao roda
  4. usuario escolhe modo + microfone
  5. puxa modelos via Ollama, grava config, mostra instrucao de atalho do SO
"""
from __future__ import annotations

import shutil
import subprocess

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal
from textual.widgets import (
    Button, Checkbox, DataTable, Footer, Header, Label, RichLog, Select, Static,
)

from anta.core.config import (
    UserConfig, load_families, load_user_config, save_user_config,
)
from anta.installer.hardware import best_vram_gb, detect_gpus, status_for
from anta.platform.detect import detect
from anta.platform.hotkey import default_command, instructions_for, setup_hotkey

_COLOR = {"verde": "green", "amarelo": "yellow", "vermelho": "red"}
_MARK = {"verde": "OK", "amarelo": "apertado", "vermelho": "nao roda"}
_DEFAULT_MIC = "(padrao do sistema)"


class InstallerApp(App):
    CSS = """
    #hw { padding: 1; color: $accent; }
    DataTable { height: auto; }
    #famrow { height: auto; padding: 0 1; }
    #family { width: 40; }
    #row { height: auto; padding: 1; }
    #mic { width: 60; }
    RichLog { height: 12; border: round $primary; padding: 0 1; }
    Button { margin: 0 1; }
    """
    BINDINGS = [("q", "quit", "Sair")]

    def __init__(self) -> None:
        super().__init__()
        self._families = load_families()
        self._fam_by_key = {f.key: f for f in self._families}
        self._vram = best_vram_gb()
        self._cfg = load_user_config()
        self._default_family = (self._cfg.family if self._cfg.family in self._fam_by_key
                                else self._families[0].key)
        # NAO usar '_ready': colide com App._ready (corotina que o Textual chama no boot).
        self._cols_ready = False  # evita repovoar antes das colunas existirem

    def compose(self) -> ComposeResult:
        yield Header()
        gpus = detect_gpus()
        gpu_line = ", ".join(f"{g.name} ({g.vram_gb}GB)" for g in gpus) \
            or "nenhuma GPU NVIDIA detectada"
        yield Static(f"GPU: {gpu_line}  |  VRAM disponivel: {self._vram}GB", id="hw")
        with Horizontal(id="famrow"):
            yield Label("Familia: ")
            yield Select([(f.label, f.key) for f in self._families], id="family",
                         value=self._default_family, allow_blank=False)
        yield DataTable(id="modes")
        with Horizontal(id="row"):
            yield Label("Microfone: ")
            yield Select(self._mic_options(), id="mic", value=_DEFAULT_MIC,
                         allow_blank=False)
            yield Checkbox("Falar respostas (TTS)", value=self._cfg.tts, id="tts")
            yield Button("Instalar modo selecionado", id="go", variant="success")
        env = detect()
        yield Static(instructions_for(env, f"{default_command()} run"))
        yield RichLog(id="log", markup=True, wrap=True)
        yield Footer()

    def _mic_options(self) -> list[tuple[str, str]]:
        options = [(_DEFAULT_MIC, _DEFAULT_MIC)]
        try:
            from anta.core.capture import list_input_devices

            for d in list_input_devices():
                name = d["name"]
                options.append((name, name))
        except Exception as e:  # noqa: BLE001 - portaudio ausente etc.
            options.append((f"(nao listou microfones: {e})", _DEFAULT_MIC))
        return options

    def on_mount(self) -> None:
        table: DataTable = self.query_one("#modes", DataTable)
        table.cursor_type = "row"
        # "VRAM min" = gate (card minimo); "VRAM uso~" = consumo estimado do LLM carregado.
        table.add_columns("Modo", "VRAM min", "VRAM uso~", "Status", "LLM", "STT", "Descricao")
        self._populate_modes(self._default_family)
        self._cols_ready = True  # colunas prontas: mudancas de familia ja podem repovoar
        self._log("Escolha a familia, um modo (verde/amarelo), o microfone e Instalar.")

    def _modes_of(self, family_key: str):
        return (self._fam_by_key.get(family_key) or self._families[0]).modes

    def _populate_modes(self, family_key: str) -> None:
        table: DataTable = self.query_one("#modes", DataTable)
        table.clear()  # mantem as colunas
        for m in self._modes_of(family_key):
            st = status_for(m.vram_gb, self._vram)
            color = _COLOR[st]
            table.add_row(
                f"[{color}]{m.label}[/]",
                f"{m.vram_gb:.0f}GB",
                m.vram_real or "-",
                f"[{color}]{_MARK[st]}[/]",
                m.llm, m.stt, m.description,
            )

    def on_select_changed(self, event: Select.Changed) -> None:
        # troca de familia repovoa a tabela de modos (ignora o Select de microfone)
        if event.select.id == "family" and self._cols_ready:
            self._populate_modes(str(event.value))

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "go":
            return
        family_key = str(self.query_one("#family", Select).value)
        modes = self._modes_of(family_key)
        table: DataTable = self.query_one("#modes", DataTable)
        idx = table.cursor_row
        if idx is None or idx < 0 or idx >= len(modes):
            self._log("[red]Selecione uma linha de modo primeiro.[/]")
            return
        mode = modes[idx]
        if status_for(mode.vram_gb, self._vram) == "vermelho":
            self._log(f"[red]'{mode.label}' precisa de {mode.vram_gb:.0f}GB de VRAM; "
                      f"voce tem {self._vram}GB. Escolha um modo mais leve.[/]")
            return
        mic = self.query_one("#mic", Select).value
        mic_name = None if mic == _DEFAULT_MIC else str(mic)
        tts_on = self.query_one("#tts", Checkbox).value
        self.query_one("#go", Button).disabled = True
        self._install(mode, family_key, mic_name, tts_on)

    def _run_stream(self, argv: list[str]) -> int:
        """Roda um comando, transmitindo stdout para o log. Retorna returncode."""
        try:
            proc = subprocess.Popen(
                argv, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
            )
        except OSError as e:
            self.call_from_thread(self._log, f"[red]falha ao rodar {argv[0]}: {e}[/]")
            return 1
        assert proc.stdout is not None
        for line in proc.stdout:
            line = line.rstrip()
            if line:
                self.call_from_thread(self._log, f"  {line}")
        return proc.wait()

    @work(thread=True, exclusive=True)
    def _install(self, mode, family_key: str, mic_name: str | None, tts_on: bool) -> None:
        log = lambda m: self.call_from_thread(self._log, m)  # noqa: E731

        # 1. LLM via Ollama
        if shutil.which("ollama") is None:
            log("[yellow]ollama nao encontrado.[/] Instale: "
                "curl -fsSL https://ollama.com/install.sh | sh")
        else:
            log(f"[b]Puxando LLM {mode.llm}[/] via ollama (pode demorar)...")
            code = self._run_stream(["ollama", "pull", mode.llm])
            log("LLM ok." if code == 0 else f"[red]ollama pull falhou (codigo {code}).[/]")

        # 2. Modelo STT (faster-whisper baixa no primeiro load)
        log(f"[b]Baixando modelo STT '{mode.stt}'[/] (faster-whisper, CPU int8)...")
        try:
            from anta.core.stt import Transcriber

            Transcriber(mode.stt).load()
            log("STT ok.")
        except Exception as e:  # noqa: BLE001
            log(f"[red]falha ao baixar STT: {e}[/]")

        # 3. Voz TTS (so se o usuario ligou) — baixa a voz PT-BR padrao
        tts_voice = None
        if tts_on:
            log("[b]Baixando voz TTS (Piper, PT-BR)[/]...")
            try:
                from anta.core.tts import ensure_voice

                tts_voice = str(ensure_voice())
                log("Voz TTS ok.")
            except Exception as e:  # noqa: BLE001
                log(f"[yellow]nao baixei a voz TTS: {e}. Deixando TTS desligado.[/]")
                tts_on = False

        # 3.5. Modelo de embedding p/ RAG (CPU, so se ligado) — mesmo padrao do STT
        if self._cfg.rag:
            log("[b]Baixando modelo de embedding (RAG, CPU)[/]...")
            try:
                from anta.core.rag import Embedder

                Embedder().load()
                log("Embedding ok.")
            except Exception as e:  # noqa: BLE001 - RAG segue lazy no 1o uso se falhar aqui
                log(f"[yellow]nao baixei o modelo de embedding: {e}. "
                    f"O RAG tentara baixar sob demanda.[/]")

        # 4. Salvar config do usuario
        cfg = UserConfig(
            family=family_key,
            mode=mode.key,
            mic_device=mic_name,
            hotkey=self._cfg.hotkey,
            obsidian_vault=self._cfg.obsidian_vault,
            tts=tts_on,
            tts_voice=tts_voice,
            tts_output=self._cfg.tts_output,
            rag=self._cfg.rag,
            web=self._cfg.web,
            web_engine=self._cfg.web_engine,
            web_searxng_url=self._cfg.web_searxng_url,
        )
        path = save_user_config(cfg)
        log(f"Config salva em {path}")

        # 4.5. Prompts editaveis: escreve o prompts.toml padrao (sem sobrescrever edicoes)
        try:
            from anta.core.prompts import write_default_prompts

            pp = write_default_prompts()
            log(f"Prompts editaveis em {pp} (ajuste tom/regras sem mexer no codigo).")
        except Exception as e:  # noqa: BLE001
            log(f"[yellow]nao escrevi o prompts.toml: {e}[/]")

        # 5. Atalho global conforme o SO
        log(setup_hotkey(hotkey=cfg.hotkey))

        # 6. Nota: o daemon ja fixa o LLM na VRAM no boot (Brain.warm, keep_alive=-1).
        log("[b]Nota:[/] o daemon fixa o LLM na VRAM ao iniciar (keep_alive=-1); "
            "para persistir entre reinicios, setar OLLAMA_KEEP_ALIVE=-1 no servico "
            "do ollama tambem ajuda.")
        log(f"[green]Instalacao concluida.[/] Rode: {default_command()} run")
        self.call_from_thread(self._enable_go)

    def _enable_go(self) -> None:
        self.query_one("#go", Button).disabled = False


def main() -> None:
    InstallerApp().run()


if __name__ == "__main__":
    main()
