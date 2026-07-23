"""Configuracao do atalho global, em camadas, decidida pelo SO detectado.

Estrategia (ver detect.Environment.hotkey_strategy):
  auto_win    -> Windows: ANTA no login; captura a tecla in-process
  auto_x11    -> Linux X11: ANTA no login; captura a tecla in-process
  compositor  -> Linux Wayland/KDE: ANTA quente + atalho do SO chama `anta toggle`
  manual      -> macOS/desconhecido: apenas instrucao

Filosofia: automacao onde e confiavel; documentacao onde nao e. No Wayland
o proprio design bloqueia apps de sequestrar teclas globais, entao o caminho
manual (docs/atalhos.md) NAO e desistir — e o tier mais robusto.

O que sobe no login e o **HUD** (`anta app`), nao o daemon headless (`anta run`):
o `run` carrega Whisper + fixa o LLM na VRAM sem janela, sem bandeja e sem console
(no build empacotado o stdout vai pro anta.log) — do lado de fora e um processo
invisivel comendo RAM/VRAM. `autostart_subcommand()` so cai no `run` quando o HUD
nao existe (dev sem `npm run build`).
"""
from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

from anta.platform.detect import Environment, detect

_RUN_KEY = r"HKCU\Software\Microsoft\Windows\CurrentVersion\Run"
_RUN_VALUE = "anta"


def default_command() -> str:
    """Prefixo do comando que invoca a ANTA (o chamador anexa run/toggle/...).

    O interpretador vem ASPADO: no autostart do Windows (HKCU\\...\\Run) e em
    qualquer caminho com espacos (ex.: C:\\Users\\Nome Sobrenome\\...python.exe),
    a string sem aspas quebra na execucao. Aspas sao validas tambem no Exec do
    .desktop (Linux) e ao colar o comando no atalho do SO.

    No build PyInstaller (frozen) NAO ha `-m anta`: o sys.executable JA e o exe
    da ANTA (o launcher roteia por argv). Anexar `-m anta` faria o exe procurar
    um modulo e falhar. Entao no frozen o prefixo e so o exe aspado."""
    if getattr(sys, "frozen", False):
        return f'"{sys.executable}"'
    return f'"{sys.executable}" -m anta'


def hud_available() -> bool:
    """True se o App de execucao (HUD, `anta app`) pode subir nesta instalacao.

    No frozen o front vai dentro do bundle; no dev ele existe so depois de
    `npm run build`. Sem isso o `anta app` morre com erro e o autostart viraria
    um item de login quebrado — por isso o subcomando do login depende disto."""
    if getattr(sys, "frozen", False):
        return True
    try:
        from anta.gui import assets  # stdlib-only; nao puxa pywebview

        return assets.dist_index("runtime").exists()
    except Exception:  # noqa: BLE001 - sem o pacote gui: cai no daemon headless
        return False


def autostart_subcommand() -> str:
    """Subcomando que deve subir no login: 'app' (HUD visivel) ou 'run' (headless)."""
    return "app" if hud_available() else "run"


def _autostart_linux(command: str) -> bool:
    """Cria ~/.config/autostart/anta.desktop para subir a ANTA ao logar."""
    try:
        path = _linux_autostart_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Name=anta\n"
            f"Exec={command}\n"
            "X-GNOME-Autostart-enabled=true\n"
            "Comment=Assistente de voz push-to-talk (daemon quente)\n",
            encoding="utf-8",
        )
        return True
    except OSError:
        return False


def _linux_autostart_path() -> Path:
    return Path.home() / ".config" / "autostart" / "anta.desktop"


def _autostart_windows(command: str) -> bool:
    """Registra a ANTA no login via HKCU\\...\\Run."""
    try:
        subprocess.run(
            ["reg", "add", _RUN_KEY,
             "/v", _RUN_VALUE, "/t", "REG_SZ", "/d", command, "/f"],
            capture_output=True, timeout=10, check=True,
        )
        return True
    except (OSError, subprocess.SubprocessError):
        return False


def current_autostart() -> str | None:
    """Comando gravado hoje no autostart (registro no Windows, .desktop no Linux),
    ou None se nao ha entrada. Best-effort: qualquer falha vira None."""
    if sys.platform.startswith("win"):
        try:
            out = subprocess.run(
                ["reg", "query", _RUN_KEY, "/v", _RUN_VALUE],
                capture_output=True, timeout=10, text=True, check=True,
            ).stdout
        except (OSError, subprocess.SubprocessError):
            return None
        for line in out.splitlines():
            if _RUN_VALUE in line and "REG_SZ" in line:
                return line.split("REG_SZ", 1)[1].strip() or None
        return None
    try:
        for line in _linux_autostart_path().read_text(encoding="utf-8").splitlines():
            if line.startswith("Exec="):
                return line[len("Exec="):].strip() or None
    except OSError:
        return None
    return None


def repair_autostart() -> str | None:
    """Migra um autostart antigo apontado pro daemon headless (`... run`) para o HUD.

    Instalacoes ate a v0.4.3 gravavam `anta run` no login: a ANTA subia SEM janela,
    SEM bandeja e sem console, so alocando RAM/VRAM — indistinguivel, de fora, de um
    processo travado. Aqui a entrada (que a propria ANTA criou) e reescrita para
    `anta app`. Idempotente e best-effort: devolve uma mensagem se mudou algo,
    senao None."""
    atual = current_autostart()
    if not atual or not atual.rstrip().endswith(" run") or not hud_available():
        return None
    novo = f"{atual.rstrip()[: -len(' run')]} app"
    ok = (_autostart_windows(novo) if sys.platform.startswith("win")
          else _autostart_linux(novo))
    if not ok:
        return None
    return ("o item de inicializacao apontava para o modo headless (sem janela); "
            "atualizei para abrir o HUD com bandeja no proximo login.")


def _kde_instructions(toggle_command: str) -> str:
    """Passo-a-passo do KDE (Wayland) preenchido com o comando de toggle."""
    return (
        "KDE (Wayland): o daemon fica quente via autostart, mas o atalho e "
        "criado pelo proprio KDE (apps nao capturam teclas globais):\n"
        "  1. Configuracoes do Sistema > Atalhos > Adicionar > Atalho de Comando/URL\n"
        f"  2. Comando: {toggle_command}\n"
        "  3. Clique na coluna de atalho e pressione a combinacao (ex.: Ctrl+Alt+Espaco)\n"
        "  4. Aplicar\n"
        "Passo-a-passo completo em docs/atalhos.md."
    )


_KDE_KEYMAP = {
    "ctrl": "Ctrl", "control": "Ctrl", "alt": "Alt", "shift": "Shift",
    "meta": "Meta", "super": "Meta", "win": "Meta", "cmd": "Meta",
    "space": "Space", "enter": "Return", "return": "Return", "tab": "Tab",
    "esc": "Escape", "escape": "Escape",
}


def _kde_key(hotkey: str) -> str:
    """'ctrl+alt+space' -> 'Ctrl+Alt+Space' (notacao de teclas do KDE)."""
    parts = []
    for raw in hotkey.split("+"):
        tok = raw.strip().lower()
        parts.append(_KDE_KEYMAP.get(tok, tok.upper() if len(tok) == 1 else tok.capitalize()))
    return "+".join(parts)


def _kde_launcher_desktop(toggle_command: str) -> str:
    """Cria ~/.local/share/applications/anta-toggle.desktop e retorna o id."""
    path = Path.home() / ".local" / "share" / "applications" / "anta-toggle.desktop"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "[Desktop Entry]\n"
        "Type=Application\n"
        "Name=anta toggle\n"
        f"Exec={toggle_command}\n"
        "NoDisplay=true\n"
        "X-KDE-GlobalAccel-CommandShortcut=true\n",
        encoding="utf-8",
    )
    return "anta-toggle.desktop"


def _kde_autoshortcut(toggle_command: str, hotkey: str) -> bool:
    """Best-effort: registra o atalho global no KDE (Plasma 5/6) escrevendo em
    kglobalshortcutsrc via kwriteconfig + um launcher .desktop. Retorna True so
    se os comandos existirem e rodarem; qualquer falha -> False (o chamador cai
    na instrucao manual, que continua sendo o caminho garantido). O atalho passa
    a valer quando o kglobalaccel rele a config (proximo login)."""
    writer = shutil.which("kwriteconfig6") or shutil.which("kwriteconfig5")
    if writer is None:
        return False
    try:
        desktop_id = _kde_launcher_desktop(toggle_command)
        key = _kde_key(hotkey)
        for cfg_key, value in (("_launch", f"{key},none,anta toggle"),
                               ("_k_friendly_name", "anta toggle")):
            subprocess.run(
                [writer, "--file", "kglobalshortcutsrc",
                 "--group", desktop_id, "--key", cfg_key, value],
                capture_output=True, timeout=10, check=True,
            )
    except (OSError, subprocess.SubprocessError):
        return False
    return True


def setup_hotkey(env: Environment | None = None, command: str | None = None,
                 hotkey: str = "ctrl+alt+space", subcommand: str | None = None) -> str:
    """Configura o atalho conforme o ambiente. Retorna instrucao para o usuario.

    `subcommand` e o que sobe no login — default `autostart_subcommand()` ('app',
    o HUD com bandeja; 'run' so quando o front nao foi buildado)."""
    env = env or detect()
    command = command or default_command()
    sub = subcommand or autostart_subcommand()
    login = f"{command} {sub}"
    rotulo = "ANTA (janela + bandeja)" if sub == "app" else "daemon 'anta run' (headless)"
    strategy = env.hotkey_strategy

    if strategy == "auto_x11":
        ok = _autostart_linux(login)
        base = instructions_for(env, login)
        prefix = (f"{rotulo} adicionada ao autostart; ela escuta o atalho "
                  "configurado ao logar.\n") if ok else ""
        return prefix + base

    if strategy == "auto_win":
        ok = _autostart_windows(login)
        base = instructions_for(env, login)
        prefix = f"{rotulo} registrada no login do Windows.\n" if ok else ""
        return prefix + base

    if strategy == "compositor":
        _autostart_linux(login)  # mantem o modelo quente
        auto = _kde_autoshortcut(f"{command} toggle", hotkey)
        prefix = (f"Atalho '{hotkey}' registrado no KDE (vale no proximo login). "
                  "Se preferir configurar agora, ou se nao funcionar, use o manual:\n"
                  if auto else "")
        return prefix + _kde_instructions(f"{command} toggle")

    return instructions_for(env, login)


def instructions_for(env: Environment, command: str) -> str:
    """Texto de atalho correto para ESTE ambiente (nao um README generico)."""
    if env.os == "windows":
        return (f"Windows: o instalador registra o atalho automaticamente. "
                f"Se preferir manual, crie um atalho apontando para: {command}")
    if env.is_wayland:
        return (
            "KDE (Wayland): Configuracoes do Sistema > Atalhos > Adicionar > "
            "Atalho de Comando/URL. Aponte para:\n"
            f"    {command}\n"
            "e defina a combinacao de teclas desejada. Passo-a-passo completo "
            "em docs/atalhos.md."
        )
    if env.os == "linux":
        return (f"Linux (X11): o instalador pode registrar automaticamente. "
                f"Manual: mapeie um atalho para: {command}")
    return f"Crie um atalho do sistema apontando para: {command}"
