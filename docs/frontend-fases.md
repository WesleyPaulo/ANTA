# Frontend desktop — fases e mudanças

Registro vivo da construção do frontend desktop do ANTA (duas apps Vue 3 + PyWebview).
Guia de design: [frontend-assistente-guia.md](frontend-assistente-guia.md). Este documento
rastreia **o que foi feito, por quê, e o que falta**. Atualize a cada milestone.

## Visão geral

Duas peças independentes que conversam **só pelo config** (single-writer):

| Peça | Comando | Papel |
|------|---------|-------|
| **Configurador** | `anta config` | Único que **escreve** o config. Substitui a TUI (que vira fallback). |
| **App de execução** | `anta app` (futuro) | Residente na bandeja, **só lê** o config; reflete a máquina de estados do backend. |

Stack: Vue 3 + Vite + Tailwind (build estático), servido numa janela **PyWebview** pelo
mesmo processo Python (sem sidecar/IPC). Ponte = `window.pywebview.api` → Promise.

## Decisões de arquitetura

- **TUI Textual continua como fallback headless.** `anta` sem argumento ainda abre a TUI
  (SSH/servidor/sem display); a GUI (`anta config`) é o padrão nos builds empacotados.
- **Configurador é a prioridade** (produz o config que o runtime consome).
- **Single-writer:** só o `ConfigApi.save` escreve o config. `anta vozes` segue como
  escape hatch de CLI (nunca concorrente com a GUI); o runtime nunca escreve.
- **Paleta preto/branco + azul escuro:** no `tailwind-preset.cjs`, neutros = `slate`,
  acento único de marca = `brand` (navy; botões em `brand-700` = `#1c3d6e`), theme-aware.
  As pílulas de status (verde/âmbar/vermelho) do gate de VRAM ficam **fora da paleta de
  marca** — são funcionais (roda/aperta/não-roda), não decorativas.
- **Regras que não podem quebrar** (guia §3/§7): `base: './'` no Vite e router em
  `createWebHashHistory()` — history normal quebra sob `file://`. Toda chamada à ponte é
  async e falível. `packages/bridge` cai num **mock** em browser puro (dev de UI sem Python).

## Divergências guia × código (o guia assumia coisas que não existiam)

| Guia assumia | Realidade | Resolução |
|--------------|-----------|-----------|
| Detecção entrega GPU/RAM/VRAM/disco | Só GPU/VRAM (`installer/hardware.py`) | `anta/gui/detection.py` (RAM via psutil, disco via stdlib) — M0 |
| Config tem versão + flag "configurado" | Não tinha | `schema_version` + `configured` em `UserConfig` (retrocompat) — M0 |
| PyInstaller "só empacotar" | `default_modes_path()`/`default_command()` quebram frozen | modes path resolve sob `sys._MEIPASS` (M0); `default_command` frozen (M5) |
| Máquina de estados no backend | Só `Session` (bool) + strings livres | `anta/core/states.py` + `anta/gui/state.py` — M3 |
| "Descarregar modelo" | Não existe unload em lugar nenhum | `Brain.unload()`/`Pipeline.unload()` — M3; botão no HUD — M4 |
| Downloads com checksum/retomada | `ollama pull` idempotente; cache HF cobre STT/embed | só a voz Piper baixa cru — M2 usa o que já existe |

## Fases (roadmap + status)

### M0 — Fundação (walking skeleton) · ✅ feito (2026-07-21)
De-risca a costura PyWebview ↔ Vue ↔ dev/build ↔ chamada-Python ↔ `file://`.
- Monorepo `frontend/` (npm workspace): `packages/bridge` (callApi + mock), `packages/ui`
  (StatusPill + preset), `apps/configurador` (Vue + hash router).
- Backend `anta/gui/`: `assets.py` (dev/build/frozen), `bridge_config.ConfigApi` (só-leitura),
  `config_app.py`, `detection.py`. Config ganha `schema_version` + `configured`. Dispatch
  `anta config`. Deps: `pywebview`, `psutil`.
- **Done:** `anta config` abre a janela (dev ou dist) e faz round-trip de `get_hardware`/
  `get_catalog`; frozen path resolve sob `_MEIPASS`.

### M2 — Configurador completo · ✅ feito (2026-07-21)
- Backend: `capture.list_output_devices`; `anta/gui/downloads.py` (verificação idempotente +
  download com progresso dos 4 componentes); `ConfigApi` expandido (devices, voices,
  `component_status`, `download_component` via `evaluate_js`, `test_microphone/tts/model_load`,
  `validate_hotkey`, `save` = único writer + `configured=True`).
- Frontend: paleta; componentes `@anta/ui` (Button, Card, Toggle, DeviceSelect, HotkeyCapture,
  DownloadableItem, Stepper); wizard de 4 passos (Modelo → Áudio → Ajustes → Instalar) +
  modo edição (abas), com store reativa.
- **Done:** o wizard produz um config válido e completo; downloads com progresso; testes de
  mic/TTS/modelo; parity com o `_install` da TUI.

### M3 — Runtime backend (máquina de estados + unload) · ✅ feito (2026-07-21)
- `anta/core/states.py`: enum `State` (`carregando/pronto/ouvindo/processando/respondendo/
  descarregado/erro`) + helper `emit` — no **core** (o pipeline não pode depender da GUI).
- `anta/gui/state.py`: `StateMachine` (guarda o estado, coage string→enum, notifica ouvintes)
  + `make_pywebview_emitter` (empurra pro front via `window.__antaOnState`).
- `Brain.unload()` (POST `keep_alive:0` no Ollama; 404 = já descarregado) + `Pipeline.unload()`
  (solta o LLM e larga STT/embedding da CPU; tudo recarrega lazy).
- Canal `on_state` **aditivo** em `Session` e `Pipeline.run` — sem quebrar o daemon CLI
  (`anta run`) nem os testes: quem não passa `on_state` mantém o comportamento (emit vira no-op).
- **Done:** `anta run` inalterado; a máquina emite a sequência (ouvindo→processando→
  respondendo→pronto; silêncio→erro code=mic); `unload` faz o POST e solta os modelos.
  311 testes Python verdes (26 novos: `test_states` + unload/estados em brain/pipeline/main).

### M4 — HUD + bandeja · ✅ feito (2026-07-21)
- Backend: `anta/gui/bridge_runtime.py` (`RuntimeApi` — só-leitura: `get_state`, `toggle`,
  `load_model`/`unload_model`, `get_config`, `list_*`, `open_configurador`, `hide`/`show`);
  `anta/gui/runtime_app.py` (bootstrap: PyWebview na thread principal + **worker thread** com
  o loop push-to-talk emitindo estados; pidfile + SIGUSR1 + pynput convergindo no mesmo
  `Event`); `anta/gui/tray.py` (`pystray`, best-effort); dispatch `anta app`.
- Frontend: `apps/runtime` (HUD de uma tela; store assina `window.__antaOnState` + `get_state`
  no mount; **orb animado por estado** — ping em ouvindo, spin em processando, pulse em
  carregando/respondendo; botões Falar/Parar e Descarregar modelo; "não ouviu → verificar
  microfone" abre o Configurador). Ponte: facade `runtimeApi` + `onState` + mock que simula
  as transições no browser.
- Três fontes de gatilho (pynput / `anta toggle` via SIGUSR1 / botão do HUD) convergem no
  mesmo `Event`; o TTS bloqueia no worker, então a GUI nunca trava.
- **Done:** `anta run` (headless) segue intacto; `anta app` sobe o HUD; 321 testes Python
  (10 novos de `RuntimeApi`) + 9 Vitest + build das duas apps.

### M5 — Empacotamento · ✅ feito (2026-07-21)
- `anta/gui/launcher.py` + `packaging/entry.py`: o exe empacotado é **um só** — com argv age
  como CLI (`config`/`app`/`run`/`toggle`), sem argv roteia por `configured` (1ª vez →
  Configurador; já configurado → HUD). Nunca a TUI (a GUI é o padrão no build).
- `hotkey.default_command()` ganhou o branch **frozen** (usa o exe, sem `-m anta`) — o
  autostart depende disso.
- `packaging/anta.spec`: empacota os dois `dist/` do Vite (`web/configurador`/`web/runtime`) +
  `modes.yaml`/`config.example.toml`; `hiddenimports` p/ os lazy (faster_whisper/fastembed/
  piper/sounddevice/pynput/pystray/webview/instructor/openai/...). Resolve tudo via `_MEIPASS`.
- Instaladores: `packaging/windows/anta.iss` (Inno: Program Files + atalhos + autostart HKCU +
  "run after install"), `packaging/linux/` (AppRun + `.desktop` p/ AppImage). Build por SO:
  `packaging/build.sh [--appimage]` / `packaging/build.ps1 [-Inno]`. Ver `packaging/README.md`.
- **Done (na máquina de build):** `pip install -r requirements.txt` + `npm run build` +
  `pyinstaller packaging/anta.spec` → `dist/anta/anta`; roteia por `configured`; autostart sobe
  o HUD. **O build em si roda em Windows/Linux nativo** (a dev box WSL2 não tem as deps nativas
  instaladas). 326 testes Python verdes (launcher + `default_command` frozen).

## Mudanças por commit (branch `feat/frontend-fundacao`)

- `docs:` guia do frontend (o brief).
- `feat:` config ganha `schema_version` + `configured` (+ modes.yaml frozen).
- `feat:` `anta/gui` — ponte PyWebview (ConfigApi) + `anta config`.
- `feat:` frontend monorepo (Vue+Vite+Tailwind) — walking skeleton.
- `feat:` ConfigApi do Configurador — devices, downloads, testes e save.
- `feat(bridge):` superfície completa do Configurador na ponte.
- `feat(configurador):` wizard completo + paleta preto/branco/azul-escuro.
- `feat:` runtime backend — máquina de estados + unload de modelo (M3).
- `feat:` App de execução — RuntimeApi + HUD na bandeja (`anta app`) (M4).
- `feat:` empacotamento — PyInstaller + launcher + instaladores (M5).

## Como rodar e validar

```bash
# Testes (dev box WSL2 roda tudo isto):
.venv/bin/python -m unittest discover -s tests   # backend
cd frontend && npm install && npm test           # ponte (Vitest)
cd frontend && npm run build                      # build do Configurador

# Ver a UI no browser (sem Python; usa o mock com dados de exemplo):
cd frontend && npm run dev        # http://localhost:5173

# Janela real (precisa de display + pywebview): Windows/Linux nativo
pip install -r requirements.txt && cd frontend && npm run build
anta config                       # abre a janela servindo o dist/
ANTA_GUI_DEV=1 anta config        # aponta pro dev server (hot reload)
```

> **Limitação da dev box:** o WSL2 aqui não tem display/GPU/pywebview nem libs de sistema
> pro chromium headless sem root — a validação **visual** roda no browser (mock) ou numa
> máquina nativa. Testes/build rodam normalmente. Ver a memória `dev-box-wsl2`.

## Estrutura de arquivos

```
anta/core/states.py           # contrato de estados (enum State + emit) — sem I/O
anta/gui/                     # backend das apps (PyWebview)
  assets.py                   # resolve a raiz web (dev/build/frozen)
  bridge_config.py            # ConfigApi (a ponte do Configurador; único writer)
  bridge_runtime.py           # RuntimeApi (a ponte do App de execução; só-leitura)
  config_app.py               # bootstrap da janela (anta config)
  runtime_app.py              # bootstrap do HUD (anta app; worker thread + bandeja)
  tray.py                     # ícone de bandeja (pystray, best-effort)
  detection.py                # RAM/disco (complementa installer/hardware.py)
  downloads.py                # verificação idempotente + download dos componentes
  state.py                    # StateMachine + emitter (App de execução)
frontend/
  packages/bridge/            # @anta/bridge — callApi + mock + facades (config/runtime)
  packages/ui/                # @anta/ui — componentes + tailwind-preset (paleta)
  apps/configurador/          # @anta/configurador — wizard (store + router + views)
  apps/runtime/               # @anta/runtime — HUD por estado (store + App.vue)
```
