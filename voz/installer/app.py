"""Instalador em TUI (Textual). Roda identico em Windows e Linux.

Fluxo:
  1. detecta VRAM (hardware.best_vram_gb)
  2. carrega modos (config.load_modes)
  3. mostra tabela colorida: verde=cabe / amarelo=apertado / vermelho=nao roda
  4. usuario escolhe modo + microfone
  5. puxa modelos via Ollama, grava config, mostra instrucao de atalho do SO

Este arquivo e um esqueleto FUNCIONAL da tela de selecao. Os passos de
'pull' e persistencia estao marcados como TODO para o Claude Code.
"""
from __future__ import annotations

from textual.app import App, ComposeResult
from textual.widgets import DataTable, Footer, Header, Static

from voz.core.config import load_modes
from voz.installer.hardware import best_vram_gb, detect_gpus, status_for
from voz.platform.detect import detect
from voz.platform.hotkey import instructions_for

_COLOR = {"verde": "green", "amarelo": "yellow", "vermelho": "red"}
_MARK = {"verde": "OK", "amarelo": "apertado", "vermelho": "nao roda"}


class InstallerApp(App):
    CSS = """
    #hw { padding: 1; color: $accent; }
    DataTable { height: auto; }
    """
    BINDINGS = [("q", "quit", "Sair")]

    def compose(self) -> ComposeResult:
        yield Header()
        gpus = detect_gpus()
        vram = best_vram_gb()
        gpu_line = ", ".join(f"{g.name} ({g.vram_gb}GB)" for g in gpus) or "nenhuma GPU NVIDIA detectada"
        yield Static(f"GPU: {gpu_line}  |  VRAM disponivel: {vram}GB", id="hw")
        yield DataTable(id="modes")
        env = detect()
        yield Static(instructions_for(env, "python -m voz run"))
        yield Footer()

    def on_mount(self) -> None:
        vram = best_vram_gb()
        table: DataTable = self.query_one("#modes", DataTable)
        table.add_columns("Modo", "VRAM", "Status", "LLM", "STT", "Descricao")
        for m in load_modes():
            st = status_for(m.vram_gb, vram)
            color = _COLOR[st]
            table.add_row(
                f"[{color}]{m.label}[/]",
                f"{m.vram_gb:.0f}GB",
                f"[{color}]{_MARK[st]}[/]",
                m.llm, m.stt, m.description,
            )
        # TODO(claude-code):
        #   - permitir selecionar uma linha (modo) e um microfone
        #     (capture.list_input_devices)
        #   - ao confirmar: `ollama pull <llm>`, baixar modelo Whisper,
        #     salvar config do usuario (config.save_user_config),
        #     e chamar hotkey.setup_hotkey()
        #   - bloquear selecao de modos em vermelho


def main() -> None:
    InstallerApp().run()


if __name__ == "__main__":
    main()
