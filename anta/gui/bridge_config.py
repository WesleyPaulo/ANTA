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
        self._window = None                  # janela pywebview (p/ empurrar progresso)

    # Injetado pelo config_app apos criar a janela, p/ o progresso de download
    # chegar no front via evaluate_js (marshalado na thread da GUI pelo pywebview).
    def set_window(self, window) -> None:
        self._window = window

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

    # --- devices de audio (por NOME; ver capture/tts) ---
    def list_microphones(self) -> list[dict]:
        from anta.core.capture import list_input_devices

        return [{"name": d["name"]} for d in list_input_devices()]

    def list_speakers(self) -> list[dict]:
        from anta.core.capture import list_output_devices

        return [{"name": d["name"]} for d in list_output_devices()]

    def list_voices(self) -> dict:
        """Vozes do TTS: catalogo oficial + comunidade + as ja instaladas."""
        from anta.core import tts

        instaladas = sorted(p.stem for p in tts.voices_dir().glob("*.onnx"))
        return {
            "oficiais": [{"nome": n, "desc": d} for n, d in tts.VOZES_PT.items()],
            "comunidade": [{"nome": n} for n in tts.VOZES_COMUNIDADE],
            "instaladas": instaladas,
            "default": tts.DEFAULT_VOICE,
        }

    # --- download / verificacao de componentes (delegado a downloads.py) ---
    def component_status(self, kind: str, key: str) -> dict:
        from anta.gui import downloads

        return downloads.component_status(kind, key)

    def download_component(self, kind: str, key: str) -> dict:
        """Baixa o componente (thread do pywebview), empurrando progresso p/ o front."""
        from anta.gui import downloads

        return downloads.download(kind, key, on_progress=self._push_progress)

    # --- Ollama (o motor do LLM; unica dep externa que nao vai no bundle) ---
    def ollama_status(self) -> dict:
        """{installed, running}: o servidor precisa estar NO AR p/ baixar/rodar o LLM."""
        from anta.gui import downloads

        return {
            "installed": downloads.ollama_installed(),
            "running": downloads.ollama_running(),
        }

    def install_ollama(self) -> dict:
        """Instala o Ollama (winget no Windows; comando manual no Linux/mac). Best-effort."""
        from anta.gui import downloads

        return downloads.install_ollama(on_progress=self._push_progress)

    def _push_progress(self, payload: dict) -> None:
        """Empurra um evento de progresso pro JS (window.__antaProgress). Best-effort."""
        win = self._window
        if win is None:
            return
        import json

        try:
            data = json.dumps(payload)
            win.evaluate_js(f"window.__antaProgress && window.__antaProgress({data})")
        except Exception:  # noqa: BLE001 - progresso nunca derruba o download
            pass

    # --- testes "antes de pronto" (guia §4.6) ---
    def test_microphone(self, device: str | None = None, seconds: float = 2.0) -> dict:
        """Grava um trecho curto e devolve o nivel do sinal (pico/rms). Best-effort."""
        import time

        from anta.core.capture import Recorder, audio_level

        try:
            rec = Recorder(device)
            rec.start()
            time.sleep(max(0.2, min(float(seconds), 10.0)))
            audio = rec.stop()
            pico, rms = audio_level(audio)
            return {"ok": True, "pico": round(float(pico), 4), "rms": round(float(rms), 4)}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    def test_tts(self, voice: str | None = None, device: str | None = None,
                 text: str = "Ola! A ANTA esta funcionando.") -> dict:
        """Fala uma frase de teste pela voz/saida escolhidas. Best-effort."""
        try:
            from anta.core.tts import speak

            speak(text, voice, device)
            return {"ok": True}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    def test_model_load(self, family: str, mode: str) -> dict:
        """Carrega o LLM do modo escolhido (pin na VRAM) p/ validar antes de salvar."""
        try:
            from anta.core.brain import Brain
            from anta.core.config import load_families

            fams = {f.key: f for f in load_families(self._modes_path)}
            fam = fams.get(family) or next(iter(fams.values()))
            m = {x.key: x for x in fam.modes}.get(mode) or fam.modes[0]
            aviso = Brain(m.llm, structured=fam.structured).warm()
            return {"ok": aviso is None, "msg": aviso or ""}
        except Exception as e:  # noqa: BLE001
            return {"ok": False, "msg": str(e)}

    # --- atalho ---
    def validate_hotkey(self, hotkey: str) -> dict:
        """Valida/normaliza o atalho. Precisa de >=1 modificador + 1 tecla."""
        mods = {"ctrl", "alt", "shift", "super", "win", "cmd", "meta"}
        tokens = [t.strip().lower() for t in str(hotkey).split("+")]
        if not all(tokens) or len(tokens) < 2:
            return {"valid": False, "normalized": "", "msg": "Use algo como ctrl+alt+space."}
        if not any(t in mods for t in tokens):
            return {"valid": False, "normalized": "",
                    "msg": "Inclua ao menos um modificador (ctrl/alt/shift/super)."}
        return {"valid": True, "normalized": "+".join(tokens), "msg": ""}

    # --- escrita do config (UNICO writer; replica o final do _install da TUI) ---
    def save(self, cfg: dict) -> dict:
        """Persiste o config (configured=True) + prompts editaveis + atalho/autostart.

        Os downloads sao passos separados (download_component), chamados pelo wizard
        antes daqui. Este metodo e o unico que ESCREVE o config (single-writer)."""
        from anta.core.config import save_user_config

        uc = self._userconfig_from_dict(cfg)
        try:
            path = save_user_config(uc, self._config_path, configured=True)
        except Exception as e:  # noqa: BLE001 - a escrita e o essencial; se falhar, falha
            return {"ok": False, "msg": f"nao consegui gravar o config: {e}"}

        warnings: list[str] = []
        try:  # prompts editaveis (nao sobrescreve edicoes)
            from anta.core.prompts import write_default_prompts

            write_default_prompts()
        except Exception as e:  # noqa: BLE001
            warnings.append(f"prompts: {e}")
        try:  # atalho / autostart por SO
            from anta.platform.hotkey import setup_hotkey

            setup_hotkey(hotkey=uc.hotkey)
        except Exception as e:  # noqa: BLE001
            warnings.append(f"atalho: {e}")

        return {"ok": True, "path": str(path), "warnings": warnings}

    def _userconfig_from_dict(self, cfg: dict):
        """Monta um UserConfig a partir do dict do front, campo a campo com defaults."""
        from anta.core.config import UserConfig

        base = UserConfig()

        def _opt(key):  # string vazia -> None (campos opcionais)
            v = cfg.get(key, getattr(base, key))
            return (v.strip() or None) if isinstance(v, str) else v

        return UserConfig(
            family=str(cfg.get("family", base.family) or base.family),
            mode=str(cfg.get("mode", base.mode) or base.mode),
            mic_device=_opt("mic_device"),
            hotkey=str(cfg.get("hotkey", base.hotkey) or base.hotkey),
            obsidian_vault=_opt("obsidian_vault"),
            tts=bool(cfg.get("tts", base.tts)),
            tts_voice=_opt("tts_voice"),
            tts_output=_opt("tts_output"),
            rag=bool(cfg.get("rag", base.rag)),
            web=bool(cfg.get("web", base.web)),
            web_engine=str(cfg.get("web_engine", base.web_engine) or base.web_engine),
            web_searxng_url=_opt("web_searxng_url"),
        )
