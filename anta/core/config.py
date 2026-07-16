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
    vram_gb: float             # gate: card minimo recomendado
    llm: str
    stt: str
    description: str
    vram_real: str = ""        # consumo estimado do LLM carregado (opcional; so exibicao)
    structured: str = "tools"  # modo de saida estruturada (vem da familia): tools | json


@dataclass
class Family:
    key: str
    label: str
    structured: str
    modes: list[Mode]          # ja ordenados por vram_gb


def default_modes_path() -> Path:
    """`modes.yaml` na RAIZ DO REPO, resolvido a partir deste arquivo — nunca do CWD.
    O daemon roda de qualquer pasta (autostart do login abre com o CWD do sistema),
    entao um caminho relativo daria FileNotFoundError."""
    return Path(__file__).resolve().parents[2] / "modes.yaml"


def load_families(path: str | Path | None = None) -> list[Family]:
    """Le o manifesto famílias × tiers. Cada Mode junta o tier (gate/stt/descricao) com
    o modelo da familia (llm/vram_real) + o `structured` da familia. Ordem das familias =
    ordem no YAML; uma familia pode omitir tiers."""
    p = Path(path) if path is not None else default_modes_path()
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    tiers = data["tiers"]
    families: list[Family] = []
    for fam_key, fam in data["families"].items():
        structured = fam.get("structured", "tools")
        modes: list[Mode] = []
        for tier_key, model in (fam.get("models") or {}).items():
            t = tiers[tier_key]
            modes.append(Mode(
                key=tier_key,
                label=t["label"],
                vram_gb=float(t["vram_gb"]),
                llm=model["llm"],
                stt=t["stt"],
                description=t.get("description", ""),
                vram_real=str(model.get("vram_real", "")),
                structured=structured,
            ))
        modes.sort(key=lambda x: x.vram_gb)
        families.append(Family(key=fam_key, label=fam["label"],
                               structured=structured, modes=modes))
    return families


def load_modes(family: str = "qwen3", path: str | Path | None = None) -> list[Mode]:
    """Conveniencia: os modos de uma familia (default 'qwen3'), ja ordenados por vram_gb."""
    families = load_families(path)
    by_key = {f.key: f for f in families}
    fam = by_key.get(family) or families[0]
    return fam.modes


# --- Config do usuario (escrita pelo instalador, lida pelo runtime) ---
# Formato TOML simples. Ver config.example.toml.

@dataclass
class UserConfig:
    mode: str = "leve"
    family: str = "qwen3"              # familia de modelos (qwen3 | gemma | deepseek)
    mic_device: str | None = None      # NOME do device; None = default do sistema
    hotkey: str = "ctrl+alt+space"
    obsidian_vault: str | None = None  # caminho do vault; None = ~/anta-notas
    tts: bool = False
    tts_voice: str | None = None       # caminho do .onnx; None = voz padrao baixada
    tts_output: str | None = None      # NOME do device de saida; None = padrao
    rag: bool = True                   # busca/memoria em notas (RAG na CPU via fastembed)
    web: bool = False                  # OPT-IN: busca na web (rompe o offline!) default off
    web_engine: str = "duckduckgo"     # duckduckgo (keyless) | searxng
    web_searxng_url: str | None = None # URL da instancia SearXNG (se web_engine=searxng)

    def mode_or_default(self, modes: list[Mode]) -> Mode:
        """Resolve o Mode correspondente, caindo no mais leve se o nome sumir."""
        by_key = {m.key: m for m in modes}
        return by_key.get(self.mode) or modes[0]

    def family_or_default(self, families: list[Family]) -> Family:
        """Resolve a Family; cai na primeira do YAML se o nome sumir (config antiga)."""
        by_key = {f.key: f for f in families}
        return by_key.get(self.family) or families[0]


def config_dir() -> Path:
    """Diretorio de config por SO (XDG no Linux, APPDATA no Windows)."""
    if os.name == "nt":
        base = os.environ.get("APPDATA") or str(Path.home() / "AppData" / "Roaming")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or str(Path.home() / ".config")
    return Path(base) / "anta"


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
        family=str(data.get("family") or "qwen3"),  # ausente (config antiga) -> qwen3
        mic_device=_clean(data.get("mic_device", "")),
        hotkey=data.get("hotkey", "ctrl+alt+space"),
        obsidian_vault=_clean(data.get("obsidian_vault", "")),
        tts=bool(data.get("tts", False)),
        tts_voice=_clean(data.get("tts_voice", "")),
        tts_output=_clean(data.get("tts_output", "")),
        rag=bool(data.get("rag", True)),  # ausente (config antiga) -> ligado
        web=bool(data.get("web", False)),  # ausente -> desligado (offline por padrao)
        web_engine=str(data.get("web_engine") or "duckduckgo"),  # str(): tolera TOML malformado
        web_searxng_url=_clean(data.get("web_searxng_url", "")),
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
        "# Gerado pelo instalador do ANTA. Editar a mao tambem funciona.",
        f"family = {_toml_str(cfg.family)}",
        f"mode = {_toml_str(cfg.mode)}",
        f"mic_device = {_toml_str(cfg.mic_device or '')}",
        f"hotkey = {_toml_str(cfg.hotkey)}",
        f"obsidian_vault = {_toml_str(cfg.obsidian_vault or '')}",
        f"tts = {'true' if cfg.tts else 'false'}",
        f"tts_voice = {_toml_str(cfg.tts_voice or '')}",
        f"tts_output = {_toml_str(cfg.tts_output or '')}",
        f"rag = {'true' if cfg.rag else 'false'}",
        f"web = {'true' if cfg.web else 'false'}",
        f"web_engine = {_toml_str(cfg.web_engine or 'duckduckgo')}",
        f"web_searxng_url = {_toml_str(cfg.web_searxng_url or '')}",
        "",
    ]
    p.write_text("\n".join(lines), encoding="utf-8")
    return p
