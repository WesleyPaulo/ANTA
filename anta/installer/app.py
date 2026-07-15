"""Instalador em TUI (Textual). Roda identico em Windows e Linux.

Fluxo:
  1. detecta VRAM (hardware.best_vram_gb)
  2. carrega modos (config.load_modes)
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
    Button, DataTable, Footer, Header, Label, RichLog, Select, Static,
)

from anta.core.config import (
    UserConfig, load_modes, load_user_config, save_user_config,
)
from anta.installer.hardware import best_vram_gb, detect_gpus, status_for
from anta.platform.detect import detect
from anta.platform.hotkey import instructions_for, setup_hotkey

_COLOR = {"verde": "green", "amarelo": "yellow", "vermelho": "red"}
_MARK = {"verde": "OK", "amarelo": "apertado", "vermelho": "nao roda"}
_DEFAULT_MIC = "(padrao do sistema)"


class InstallerApp(App):
    CSS = """
    #hw { padding: 1; color: $accent; }
    DataTable { height: auto; }
    #row { height: auto; padding: 1; }
    #mic { width: 60; }
    RichLog { height: 12; border: round $primary; padding: 0 1; }
    Button { margin: 0 1; }
    """
    BINDINGS = [("q", "quit", "Sair")]

    def __init__(self) -> None:
        super().__init__()
        self._modes = load_modes()
        self._vram = best_vram_gb()
        self._cfg = load_user_config()

    def compose(self) -> ComposeResult:
        yield Header()
        gpus = detect_gpus()
        gpu_line = ", ".join(f"{g.name} ({g.vram_gb}GB)" for g in gpus) \
            or "nenhuma GPU NVIDIA detectada"
        yield Static(f"GPU: {gpu_line}  |  VRAM disponivel: {self._vram}GB", id="hw")
        yield DataTable(id="modes")
        with Horizontal(id="row"):
            yield Label("Microfone: ")
            yield Select(self._mic_options(), id="mic", value=_DEFAULT_MIC,
                         allow_blank=False)
            yield Button("Instalar modo selecionado", id="go", variant="success")
        env = detect()
        yield Static(instructions_for(env, "python -m anta run"))
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
        table.add_columns("Modo", "VRAM", "Status", "LLM", "STT", "Descricao")
        for m in self._modes:
            st = status_for(m.vram_gb, self._vram)
            color = _COLOR[st]
            table.add_row(
                f"[{color}]{m.label}[/]",
                f"{m.vram_gb:.0f}GB",
                f"[{color}]{_MARK[st]}[/]",
                m.llm, m.stt, m.description,
            )
        self._log("Escolha um modo (verde/amarelo), o microfone e clique em Instalar.")

    def _log(self, msg: str) -> None:
        self.query_one("#log", RichLog).write(msg)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id != "go":
            return
        table: DataTable = self.query_one("#modes", DataTable)
        idx = table.cursor_row
        if idx is None or idx < 0 or idx >= len(self._modes):
            self._log("[red]Selecione uma linha de modo primeiro.[/]")
            return
        mode = self._modes[idx]
        if status_for(mode.vram_gb, self._vram) == "vermelho":
            self._log(f"[red]'{mode.label}' precisa de {mode.vram_gb:.0f}GB de VRAM; "
                      f"voce tem {self._vram}GB. Escolha um modo mais leve.[/]")
            return
        mic = self.query_one("#mic", Select).value
        mic_name = None if mic == _DEFAULT_MIC else str(mic)
        self.query_one("#go", Button).disabled = True
        self._install(mode, mic_name)

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
    def _install(self, mode, mic_name: str | None) -> None:
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

        # 3. Salvar config do usuario
        cfg = UserConfig(
            mode=mode.key,
            mic_device=mic_name,
            hotkey=self._cfg.hotkey,
            obsidian_vault=self._cfg.obsidian_vault,
            tts=self._cfg.tts,
        )
        path = save_user_config(cfg)
        log(f"Config salva em {path}")

        # 4. Atalho global conforme o SO
        log(setup_hotkey())

        # 5. Lembrete: manter o modelo quente
        log("[b]Dica:[/] setar OLLAMA_KEEP_ALIVE=-1 (ex.: no servico do ollama) "
            "mantem o LLM na VRAM e evita 5-10s de recarga por comando.")
        log("[green]Instalacao concluida.[/] Rode: python -m anta run")
        self.call_from_thread(self._enable_go)

    def _enable_go(self) -> None:
        self.query_one("#go", Button).disabled = False


def main() -> None:
    InstallerApp().run()


if __name__ == "__main__":
    main()
