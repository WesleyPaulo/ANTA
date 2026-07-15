# Guia de implementacao (para o Claude Code)

Este repositorio e um **scaffold**. A arquitetura, os schemas e as interfaces
ja estao definidos; falta implementar a logica marcada com `TODO(claude-code)`.
Implemente na ordem abaixo. Nao mude a arquitetura sem um bom motivo — cada
decisao abaixo existe por uma restricao real de hardware (GPU de 8GB).

## Principios que NAO devem ser violados

1. **STT na CPU, LLM na GPU.** `faster-whisper` sempre `device="cpu"`,
   `compute_type="int8"`. A VRAM e exclusiva do LLM.
2. **O LLM nunca gera shell.** Ele so escolhe uma acao de `anta/actions/schema.py`
   via `instructor`. Todo efeito colateral vive em `anta/actions/executor.py`.
   `abrir_app` valida contra `APP_WHITELIST`.
3. **MVP = so microfone.** Nao implemente captura de audio do sistema, sink
   virtual ou loopback. Um unico caminho de codigo (`sounddevice`) nos dois SOs.
4. **Device de audio por NOME, nao por indice/default.** Persistir o nome.
5. **Modelo sempre quente.** Setar `OLLAMA_KEEP_ALIVE` (documentar no instalador).
6. **Modos sao declarativos.** Toda escolha de modelo sai de `modes.yaml`.

## Ordem de implementacao

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

### 5. Executor — `anta/actions/executor.py`
- Implementar cada ramo do `match`. `CriarDocumento` converte via `pandoc`
  quando `formato != "md"`. `Responder` opcionalmente fala via Piper se `tts`.

### 6. Pipeline — `anta/core/pipeline.py`
- `run(audio)`: transcribe → decide → execute → retorna feedback.

### 7. Runtime / loop — `anta/__main__.py` (`run`)
- Carrega config, monta `Pipeline`, registra o toggle e o loop de gravacao.
  Feedback via `notify-send` (Linux) / notificacao nativa (Windows).

### 8. Instalador — `anta/installer/app.py`
- Selecao de linha (modo) + dropdown de microfone
  (`capture.list_input_devices`). Bloquear modos "vermelho".
- Ao confirmar: `ollama pull <llm>`, baixar o modelo Whisper, `save_user_config`,
  chamar `hotkey.setup_hotkey`.

### 9. Atalho — `anta/platform/hotkey.py`
- Implementar `setup_hotkey` por estrategia:
  - `auto_win`: listener na bandeja + `keyboard.add_hotkey`.
  - `auto_x11`: `pynput` GlobalHotKeys.
  - `compositor` (KDE/Wayland): gerar `kwriteconfig6` e recarregar; em falha,
    retornar o texto de `docs/atalhos.md` preenchido.
  - `manual`: so instrucao.

## Testes sugeridos
- `hardware.status_for` (verde/amarelo/vermelho nos limites).
- `config.load_modes` (ordenacao por vram_gb).
- `detect.Environment.hotkey_strategy` (mock de env vars).
- Schema: `instructor` devolvendo cada tipo de acao.

## Nao-metas do MVP
- Audio do sistema / reuniao. RAG. Modo conversacional em tempo real.
  Gestao de memoria Linux (zram/systemd slice) — opcional, pos-MVP.
