"""Carrega o manifesto de modos (modes.yaml) e a config do usuario."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass
class Mode:
    key: str
    label: str
    vram_gb: float
    llm: str
    stt: str
    description: str


def load_modes(path: str | Path = "modes.yaml") -> list[Mode]:
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    modes = []
    for key, m in data["modes"].items():
        modes.append(Mode(
            key=key,
            label=m["label"],
            vram_gb=float(m["vram_gb"]),
            llm=m["llm"],
            stt=m["stt"],
            description=m.get("description", ""),
        ))
    # ordena do mais leve pro mais pesado
    return sorted(modes, key=lambda x: x.vram_gb)


# --- Config do usuario (escrita pelo instalador, lida pelo runtime) ---
# Formato TOML simples. Ver config.example.toml.

@dataclass
class UserConfig:
    mode: str = "leve"
    mic_device: str | None = None      # NOME do device; None = default do sistema
    hotkey: str = "ctrl+alt+space"
    obsidian_vault: str | None = None  # caminho do vault; None = ~/voz-notas
    tts: bool = False

    def mode_or_default(self, modes: list[Mode]) -> Mode:
        """Resolve o Mode correspondente, caindo no mais leve se o nome sumir."""
        by_key = {m.key: m for m in modes}
        return by_key.get(self.mode) or modes[0]


def config_dir() -> Path:
    """Diretorio de config por SO (XDG no Linux, APPDATA no Windows)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "voz"


def config_path() -> Path:
    return config_dir() / "config.toml"


def _clean(value: str) -> str | None:
    """String vazia no TOML significa 'ausente' -> None."""
    value = value.strip()
    return value or None


def load_user_config(path: str | Path | None = None) -> UserConfig:
    """Le a config do usuario. Devolve os defaults se o arquivo nao existir."""
    p = Path(path) if path is not None else config_path()
    if not p.exists():
        return UserConfig()
    data = tomllib.loads(p.read_text(encoding="utf-8"))
    return UserConfig(
        mode=data.get("mode", "leve"),
        mic_device=_clean(data.get("mic_device", "")),
        hotkey=data.get("hotkey", "ctrl+alt+space"),
        obsidian_vault=_clean(data.get("obsidian_vault", "")),
        tts=bool(data.get("tts", False)),
    )


def _toml_str(value: str) -> str:
    """Escapa uma string para um literal TOML basico entre aspas."""
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def save_user_config(cfg: UserConfig, path: str | Path | None = None) -> Path:
    """Grava a config em TOML. Cria o diretorio se preciso. Retorna o caminho."""
    p = Path(path) if path is not None else config_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# Gerado pelo instalador do voz. Editar a mao tambem funciona.",
        f"mode = {_toml_str(cfg.mode)}",
        f"mic_device = {_toml_str(cfg.mic_device or '')}",
        f"hotkey = {_toml_str(cfg.hotkey)}",
        f"obsidian_vault = {_toml_str(cfg.obsidian_vault or '')}",
        f"tts = {'true' if cfg.tts else 'false'}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
