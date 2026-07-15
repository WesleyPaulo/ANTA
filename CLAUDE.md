# Guia de arquitetura (para o Claude Code)

O MVP esta **implementado** (pacote `anta`; os `TODO(claude-code)` do scaffold
foram preenchidos e ha suite de testes). Este guia documenta a arquitetura e os
invariantes. Nao mude a arquitetura sem um bom motivo — cada decisao existe por
uma restricao real de hardware (GPU de 8GB).

## Principios que NAO devem ser violados

1. **STT na CPU, LLM na GPU.** `faster-whisper` sempre `device="cpu"`,
   `compute_type="int8"`. A VRAM e exclusiva do LLM.
2. **O LLM nunca gera shell.** Ele so escolhe uma acao de `anta/actions/schema.py`
   via `instructor`. Os efeitos vivem em `anta/actions/handlers/` (um arquivo por
   acao), despachados por `registry.py`; a entrada publica e `executor.py`.
   `abrir_app` valida contra a whitelist de `anta/actions/apps.py`.
3. **MVP = so microfone.** Nao implemente captura de audio do sistema, sink
   virtual ou loopback. Um unico caminho de codigo (`sounddevice`) nos dois SOs.
4. **Device de audio por NOME, nao por indice/default.** Persistir o nome.
5. **Modelo sempre quente.** `Brain.warm()` fixa o LLM na VRAM no boot com um
   preload `keep_alive=-1` no endpoint nativo do Ollama (o endpoint OpenAI-compat
   nao aceita `keep_alive`); setar `OLLAMA_KEEP_ALIVE=-1` no servico persiste
   entre reinicios (documentar no instalador).
6. **Modos sao declarativos.** Toda escolha de modelo sai de `modes.yaml`.

## Mapa dos modulos

### 1. Config do usuario — `anta/core/config.py`
- `load_user_config()` / `save_user_config()` lendo/escrevendo TOML
  (ver `config.example.toml`). Campos: mode, mic_device, hotkey,
  obsidian_vault, tts.

### 2. Captura — `anta/core/capture.py`
- `list_input_devices()` via `sounddevice.query_devices()`.
- `Recorder` em toggle: `start()` abre `InputStream` acumulando em buffer;
  `stop()` encerra e devolve `np.ndarray` float32 mono 16kHz. Aplicar
  `MAX_SECONDS`. Resolver device por nome.

### 3. STT — `anta/core/stt.py`
- `Transcriber` carregando `WhisperModel(..., device="cpu", compute_type="int8")`.
- `transcribe(audio) -> str` com `language="pt"`.

### 4. Cerebro — `anta/core/brain.py`
- `Brain.decide(texto) -> Decisao` via `instructor.from_openai(OpenAI(
  base_url="http://localhost:11434/v1", api_key="ollama"))`, `response_model=Decisao`,
  `temperature=0.1`, `model=self.llm`.
- `Brain.warm()` faz o preload `keep_alive=-1` (principio 5); chamado por `Pipeline.warm()`.

### 4.5 TTS — `anta/core/tts.py`
- `speak(texto, voice_path, output_device)`: sintetiza via `PiperVoice.synthesize`
  (API Python do `piper-tts`) e reproduz o PCM pelo `sounddevice` (mesmo backend
  da captura). Best-effort: no-op silencioso se o piper ou a voz nao existirem.
- `ensure_voice(nome, dest)`: baixa a voz `.onnx` (+ `.onnx.json`) do HuggingFace
  se faltar. O instalador chama quando o usuario liga o TTS.
- Fica no `core` (nao em `actions/helpers.py`, que e folha stdlib-only) porque
  precisa de `sounddevice`/`numpy`/`piper`. O onnxruntime roda na CPU (nao viola
  o principio 1: a VRAM segue exclusiva do LLM) e so e importado ao falar.

### 5. Executor — `anta/actions/` (fachada + handlers)
- `executor.py` e uma fachada fina: `execute(decisao, ctx)` despacha via
  `registry.HANDLERS` (mapa explicito tipo-de-acao -> handler; sem decorator/magia).
- Um arquivo por acao em `handlers/`, com `handle(acao, ctx) -> str`.
  `criar_documento` converte via `pandoc` quando `formato != "md"`; `responder`
  fala via `anta/core/tts.speak` (Piper) se `ctx.tts`.
- `apps.py`: whitelist de `abrir_app` isolada (`lookup`/`permitidos`).
  `context.py`: `ExecContext` + constantes. `helpers.py`: `slug`/`unique_path`/`speak`.
- Adicionar acao = classe no schema + arquivo em `handlers/` + 1 linha em `HANDLERS`
  (o teste de exaustividade em `tests/test_apps.py` cobre o resto).

### 6. Pipeline — `anta/core/pipeline.py`
- `run(audio)`: transcribe → decide → execute → retorna feedback.

### 7. Runtime / loop — `anta/__main__.py` (`run`)
- `run` e um **daemon quente** (Whisper carregado + LLM via `OLLAMA_KEEP_ALIVE`):
  carrega config, monta `Pipeline`, `warm()`, e alterna a gravacao no toggle.
- O toggle vem de duas fontes num `threading.Event` (nunca trabalho pesado no
  signal handler): `pynput` in-process (X11/Windows) ou `SIGUSR1`. No Wayland,
  o atalho do SO chama `python -m anta toggle`, que sinaliza o daemon (pidfile).
- Feedback via `notify-send` (Linux) / `print`.

### 8. Instalador — `anta/installer/app.py`
- Selecao de linha (modo) + dropdown de microfone
  (`capture.list_input_devices`). Bloquear modos "vermelho".
- Ao confirmar: `ollama pull <llm>`, baixar o modelo Whisper, `save_user_config`,
  chamar `hotkey.setup_hotkey`.

### 9. Atalho — `anta/platform/hotkey.py`
- `setup_hotkey` por estrategia (o daemon `anta run` captura a tecla via
  `pynput.GlobalHotKeys` no X11/Windows; no Wayland o atalho do SO chama
  `anta toggle`):
  - `auto_x11` / `auto_win`: autostart do daemon no login (`.desktop` / HKCU Run).
  - `compositor` (KDE/Wayland): autostart do daemon + instrucao de `docs/atalhos.md`
    preenchida com `anta toggle` (o caminho manual e o mais robusto no Wayland).
  - `manual`: so instrucao.

## Testes
Suite em `tests/` (`unittest` stdlib):
`.venv/bin/python -m unittest discover -s tests`. Cobrem: `hardware.status_for`
(limites), `config.load_modes` + round-trip da config, `detect.hotkey_strategy`
(mock de env), schema (uniao discriminada por acao), executor (cada handler),
whitelist + exaustividade do registro (`tests/test_apps.py`), resolucao de mic
por nome (`test_capture.py`), guards do TTS + `_resolve_output` (`test_tts.py`) e
a camada de atalho: quoting, `_kde_key`, automacao KDE best-effort com fallback
manual (`test_hotkey.py`). Testes de I/O usam um `sounddevice` falso via
`sys.modules` — nao dependem de PortAudio/piper reais.

## Nao-metas do MVP
- Audio do sistema / reuniao. RAG. Modo conversacional em tempo real.
  Gestao de memoria Linux (zram/systemd slice) — opcional, pos-MVP.
