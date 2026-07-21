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
| PyInstaller "só empacotar" | `default_modes_path()`/`default_command()` quebram frozen | modes path já resolve sob `sys._MEIPASS` (M0); `default_command` fica p/ M5 |
| Máquina de estados no backend | Só `Session` (bool) + strings livres | `anta/gui/state.py` — M3 |
| "Descarregar modelo" | Não existe unload em lugar nenhum | `Brain.unload()`/`Pipeline.unload()` — M3 |
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

### M4 — HUD + bandeja · pendente
`apps/runtime` (store de estado alimentada por `window.__antaOnState` + `get_state`),
animação por estado, botão descarregar; `anta/gui/runtime_app.py` (worker thread + `pystray`),
comando `anta app`. Fluxo "não ouviu → verificar microfone" abre o Configurador.

### M5 — Empacotamento · pendente
`anta.spec` (PyInstaller: dois `dist/` + `modes.yaml` + hiddenimports), `launcher.py` (roteia
por `configured`), `default_command()` frozen, instaladores (Inno/NSIS, AppImage), autostart
reusando `anta/platform/hotkey.py`.

## Mudanças por commit (branch `feat/frontend-fundacao`)

- `docs:` guia do frontend (o brief).
- `feat:` config ganha `schema_version` + `configured` (+ modes.yaml frozen).
- `feat:` `anta/gui` — ponte PyWebview (ConfigApi) + `anta config`.
- `feat:` frontend monorepo (Vue+Vite+Tailwind) — walking skeleton.
- `feat:` ConfigApi do Configurador — devices, downloads, testes e save.
- `feat(bridge):` superfície completa do Configurador na ponte.
- `feat(configurador):` wizard completo + paleta preto/branco/azul-escuro.
- `feat:` runtime backend — máquina de estados + unload de modelo (M3).

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
  config_app.py               # bootstrap da janela (anta config)
  detection.py                # RAM/disco (complementa installer/hardware.py)
  downloads.py                # verificação idempotente + download dos componentes
  state.py                    # StateMachine + emitter (App de execução, M3+)
frontend/
  packages/bridge/            # @anta/bridge — callApi + mock + facade tipada
  packages/ui/                # @anta/ui — componentes + tailwind-preset (paleta)
  apps/configurador/          # @anta/configurador — wizard (store + router + views)
```
