"""A ponte Python <-> Vue do Configurador (App A).

Cada metodo publico vira `window.pywebview.api.<metodo>(...)` no front, devolvendo
uma Promise (guia §3). Tudo aqui e JSON-serializavel (dict/list/str/num/bool) e
puro-leitura NESTA FASE: detecta hardware e monta o catalogo do `modes.yaml`. O
`save` (escrita do config) e os downloads entram na fase do Configurador completo.

Colaboradores sao injetaveis (default = modulos reais, importados preguicosamente)
para testar sem NVIDIA/psutil/arquivo real — mesmo padrao de fakes do resto da suite.
"""
from __future__ import annotations

from dataclasses import asdict
from pathlib import Path


class ConfigApi:
    """API exposta ao Configurador. Instanciada e passada como `js_api=`."""

    def __init__(
        self,
        *,
        config_path: str | Path | None = None,
        modes_path: str | Path | None = None,
        hardware=None,
        detection=None,
        detect_env=None,
    ) -> None:
        self._config_path = config_path      # TOML do usuario (default: config_path())
        self._modes_path = modes_path        # modes.yaml (default: default_modes_path())
        self._hardware = hardware            # default: anta.installer.hardware
        self._detection = detection          # default: anta.gui.detection
        self._detect_env = detect_env        # default: anta.platform.detect.detect

    # --- resolucao preguicosa dos colaboradores (permite injecao em teste) ---
    def _hw(self):
        if self._hardware is None:
            from anta.installer import hardware
            self._hardware = hardware
        return self._hardware

    def _det(self):
        if self._detection is None:
            from anta.gui import detection
            self._detection = detection
        return self._detection

    def _env_fn(self):
        if self._detect_env is None:
            from anta.platform.detect import detect
            self._detect_env = detect
        return self._detect_env

    # --- smoke da ponte ---
    def ping(self) -> str:
        """Round-trip minimo pra provar a costura PyWebview <-> Vue."""
        return "pong"

    def echo(self, value):
        """Devolve o que recebeu (checa serializacao ida-e-volta)."""
        return value

    # --- ambiente / hardware ---
    def get_environment(self) -> dict:
        """SO, sessao e estrategia de atalho (pra UI adaptar instrucoes de hotkey)."""
        env = self._env_fn()()
        return {
            "os": env.os,
            "session": env.session,
            "desktop": env.desktop,
            "is_wayland": env.is_wayland,
            "hotkey_strategy": env.hotkey_strategy,
            "captures_hotkey_in_process": env.captures_hotkey_in_process,
        }

    def get_hardware(self) -> dict:
        """GPU/VRAM (ja existia) + RAM/disco (novos). Livre do disco = da pasta de config."""
        from anta.core.config import config_dir

        hw, det = self._hw(), self._det()
        gpus = [{"name": g.name, "vram_gb": g.vram_gb} for g in hw.detect_gpus()]
        return {
            "gpus": gpus,
            "best_vram_gb": hw.best_vram_gb(),
            "ram_gb": det.ram_gb(),
            "disk_free_gb": det.disk_free_gb(config_dir()),
        }

    def get_catalog(self) -> dict:
        """Familias x modos do `modes.yaml`, cada modo com o status (verde/amarelo/
        vermelho) do gate de VRAM contra a placa detectada."""
        from anta.core.config import load_families

        hw = self._hw()
        best_vram = hw.best_vram_gb()
        families = load_families(self._modes_path)
        out = []
        for fam in families:
            modes = [
                {
                    "key": m.key,
                    "label": m.label,
                    "vram_gb": m.vram_gb,
                    "vram_real": m.vram_real,
                    "llm": m.llm,
                    "stt": m.stt,
                    "description": m.description,
                    "structured": m.structured,
                    "status": hw.status_for(m.vram_gb, best_vram),
                }
                for m in fam.modes
            ]
            out.append({
                "key": fam.key,
                "label": fam.label,
                "structured": fam.structured,
                "modes": modes,
            })
        return {"best_vram_gb": best_vram, "families": out}

    def get_config(self) -> dict:
        """Config atual do usuario (inclui schema_version e configured)."""
        from anta.core.config import load_user_config

        return asdict(load_user_config(self._config_path))
