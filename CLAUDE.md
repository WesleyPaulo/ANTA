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
6. **Modos sao declarativos.** Toda escolha de modelo sai de `modes.yaml`, agora estruturado
   em **familias × tiers**: `tiers` (gate `vram_gb` + `stt` + descricao, compartilhados) e
   `families` (Qwen3/Gemma/DeepSeek — cada uma troca o `llm` por tier + o modo `structured`).
   Adicionar familia/tier = um bloco no YAML; nenhum codigo muda.
7. **RAG/embedding SEMPRE na CPU.** O embedder (`fastembed`/onnxruntime) roda na CPU,
   como o STT — a VRAM segue exclusiva do LLM (reforca o principio 1). O RAG so LE
   arquivos e devolve trechos; a sintese em linguagem natural e do LLM (`Brain.answer`).

## Mapa dos modulos

### 1. Config do usuario — `anta/core/config.py`
- `load_user_config()` / `save_user_config()` lendo/escrevendo TOML
  (ver `config.example.toml`). Campos: family, mode, mic_device, hotkey,
  obsidian_vault, tts, rag, web*. Campos novos ausentes caem em default (retrocompat).
- `load_families() -> list[Family]` monta os `Mode`s juntando tier + modelo da familia
  (+ `structured`); `load_modes(family="qwen3")` e conveniencia. `UserConfig.family_or_default`
  + `mode_or_default` resolvem familia→modo (fallback: 1a familia / mais leve).
- `default_modes_path()`: o `modes.yaml` e resolvido pela **raiz do repo** (via `__file__`),
  NUNCA pelo CWD — o daemon sobe pelo autostart do login, com o CWD do sistema. Pelo mesmo
  motivo os instaladores fazem `uv pip install -e .` (sem isso `-m anta` so acha o pacote
  com o CWD no repo).

### 2. Captura — `anta/core/capture.py`
- `list_input_devices()` via `sounddevice.query_devices()`.
- `Recorder` em toggle: `start()` abre `InputStream` acumulando em buffer;
  `stop()` encerra e devolve `np.ndarray` float32 mono 16kHz. Aplicar
  `MAX_SECONDS`. Resolver device por nome.

### 3. STT — `anta/core/stt.py`
- `Transcriber` carregando `WhisperModel(..., device="cpu", compute_type="int8")`.
- `transcribe(audio) -> str` com `language="pt"`.

### 4. Cerebro — `anta/core/brain.py`
- `Brain.decide(texto, history) -> Decisao` via `instructor.from_openai(OpenAI(...),
  mode=_instructor_mode(self.structured))`, `response_model=Decisao`, `temperature=0.1`,
  `max_retries=2`. `answer()`/`summarize()` usam client cru (sem instructor).
- **NUNCA `structured: "tools"` com Ollama** (fica so como escape hatch). O Ollama
  **ignora `tool_choice`** — o campo nao existe no `ChatCompletionRequest` dele e campo
  desconhecido e descartado sem erro. Logo a chamada de ferramenta NUNCA e obrigatoria:
  num "e ai" o modelo so conversa -> `No tool calls found (mode: TOOLS)`, e o
  `reask_tools` do instructor ainda crasha iterando `tool_calls=None`, matando o retry.
  Todas as familias usam `json_schema` (default de `_instructor_mode`): o schema vai no
  `response_format`, o Ollama repassa pro llama.cpp e vira **gramatica GBNF** — a saida
  nao pode fugir do schema. E o que o `tool_choice` faria, uma camada abaixo, onde
  funciona. `json` (gramatica JSON generica + schema no prompt) fica de fallback.
- `Decisao.model_json_schema()` **forca `acao` em `required`** em cada acao. Os defaults
  (`acao: Literal["resumir"] = "resumir"`) tiram o campo do `required`, e o que nao e
  required vira OPCIONAL na gramatica: o modelo podia omitir o discriminador e `Resumir`
  degenerava no valido-e-inutil `{"escolha": {}}`. Corrigido no schema (nao tirando os
  defaults) pra nao poluir o codigo Python com `acao="..."` redundante.
- `_texto_solto()`: se o instructor falha e o modelo tinha escrito texto (nao JSON, nao
  tool call), vira `Responder`. A resposta certa existia, so no envelope errado — jogar
  fora e mostrar traceback e o pior desfecho.
- **Raciocinio SEMPRE desligado** (`_SEM_RACIOCINIO = {"reasoning_effort": "none"}` no
  `extra_body` de `decide` e `_complete`). O Ollama LIGA o thinking por padrao em todo
  modelo capaz, e thinking+tools quebra o tool-calling (o modelo emite a chamada como
  texto -> `No tool calls found (mode: TOOLS)`). `reasoning_effort` e o UNICO lever do
  endpoint OpenAI-compat: `think:false` e `chat_template_kwargs` sao **silenciosamente
  ignorados** (campo desconhecido -> descartado). `"none"` e seguro nas 3 familias (o
  guard e `req.Think != nil && req.Think.Bool()`, e "none" vira `false` -> sem 400).
- **`qwen3:4b-instruct`, nunca `qwen3:4b`** nos tiers leve/normal: o tag `qwen3:4b` foi
  repontado pro Thinking-2507, cujo template abre `<think>` **incondicionalmente** — nao
  ha parametro que desligue (o `reasoning_effort:"none"` vira no-op). Nao existe
  `qwen3:8b-instruct`/`14b-instruct`; nesses tiers o lever funciona.
- `now_line()` (de `prompts.py`) injeta data/hora em todo system prompt via `_sys()`. Sem
  isso o modelo nao sabe a data e a persona manda "nunca invente" -> "que dia e hoje?"
  virava `buscar_web`. Fica fora do `Prompts` de proposito: e fato, nao tom (nao editavel),
  e precisa ser recalculado a cada chamada (o daemon fica ligado dias).
- `Brain.warm()` faz o preload `keep_alive=-1` (principio 5); chamado por `Pipeline.warm()`.

### 4.5 TTS — `anta/core/tts.py`
- `speak(texto, voice_path, output_device)`: sintetiza via `PiperVoice.synthesize`
  (API Python do `piper-tts`) e reproduz o PCM pelo `sounddevice` (mesmo backend
  da captura). Best-effort: no-op silencioso se o piper ou a voz nao existirem.
- **`stop()` / `reset()` / `cancelled()`**: o botao "Parar" do HUD. `stop()` corta o
  audio que ja toca (`sd.stop()` faz o `sd.wait()` retornar) **e** marca um Event de
  modulo — as duas metades importam: sem o Event, cancelar durante a sintese so adiava
  a fala. O Event e de modulo porque `speak()` roda no fundo (handler -> executor ->
  pipeline) e quem cancela esta noutra thread; `Pipeline.run` chama `reset()` a cada turno.
- `ensure_voice(nome, dest)`: baixa a voz `.onnx` (+ `.onnx.json`) do HuggingFace
  se faltar. O instalador chama quando o usuario liga o TTS.
- Fica no `core` (nao em `actions/helpers.py`, que e folha stdlib-only) porque
  precisa de `sounddevice`/`numpy`/`piper`. O onnxruntime roda na CPU (nao viola
  o principio 1: a VRAM segue exclusiva do LLM) e so e importado ao falar.

### 4.55 Prompts — `anta/core/prompts.py` (v0.3)
- Todos os prompts vivem aqui (unica fonte): `PERSONA` (tom compartilhado) + `DECIDE`
  (roteamento com few-shot) + `ANSWER` (RAG) + `RESUMO` + `ESCRITA` (notas/documentos).
- **A `PERSONA` so vale para o que e FALADO** (`decide`/`answer`/`resumo`, via `_sys()`).
  Ela manda "frases curtas, sem markdown, sem listas" porque a saida vai pro TTS — e isso
  vazava para a escrita de notas: o modelo obedecia e entregava um paragrafo raso onde se
  pedia material util. `Brain.write()` usa `ESCRITA` **sem** a persona. Nao prefixe a
  persona em nada escrito.
- **`write_default_prompts()` escreve tudo COMENTADO.** Antes copiava os padroes pro TOML
  e, como `load_prompts()` sobrepoe o codigo, o snapshot da instalacao ganhava para
  sempre: melhorias no `decide` (afiado a cada bug de roteamento) nunca chegavam em quem
  ja tinha instalado, sem aviso. Comentado, o padrao do codigo vale ate o usuario decidir
  o contrario.
- `load_prompts()` sobrepoe overrides de `config_dir()/prompts.toml` campo a campo
  (string vazia/tipo errado/arquivo invalido caem no padrao). `write_default_prompts()`
  escreve o TOML editavel sem sobrescrever edicoes (o instalador chama). O `Brain` recebe
  um `Prompts` (default `load_prompts()`) e prefixa a persona via `_sys(task)`.

### 4.6 Memoria + RAG — `anta/core/rag.py` (v0.3)
- Memoria de **curto prazo**: janela de conversa (`deque`, RAM-only, some ao reiniciar)
  mantida no `Pipeline` e injetada em `Brain.decide(texto, history)` para resolver
  referencias ("cria outra igual", "e o prazo disso?").
- Memoria de **longo prazo**: notas `.md` em `<vault>/memoria/` (via
  `helpers.write_memory_note`) indexadas pelo RAG. Escrita **automatica** (o LLM sinaliza
  um fato duravel em `Decisao.memoria`, aplicado pelo `Pipeline`) **+ explicita** (acao
  `Lembrar`). O guard `not isinstance(escolha, Lembrar)` evita gravacao dupla.
- `RAG` (fachada) sobre `Embedder` (fastembed CPU, `load()` lazy, cache em
  `config_dir()/embeddings`, `paraphrase-multilingual-MiniLM-L12-v2`; a logica de prefixo
  e5 so dispara p/ modelos e5) e `Index` (matriz numpy float32 + metadados, persistida em
  `config_dir()/index`, `reconcile` incremental por `(mtime,size)`, busca por cosseno).
- **Frescura:** `RAG.query()` reconcilia o vault ANTES de buscar (o daemon e de vida
  longa; notas/documentos criados na sessao ou editados por fora precisam aparecer). Por
  isso os handlers de escrita NAO indexam explicitamente — nada de `index_file` no caminho
  quente. `ensure_ready()`/`warm()` so pre-aquecem o modelo em thread best-effort.
- Consulta = acao `Consultar` -> `handlers/consultar.py` recupera top-k e sintetiza via
  `ctx.answer` (ligado a `Brain.answer`, completion crua sem `response_model`). Zero VRAM
  extra: mesmo endpoint Ollama. Toggle `rag` na config (default `true`).
- **Resumo** = acao `Resumir(periodo)` -> `handlers/resumir.py`: `helpers.gather_activity`
  varre o que o usuario produziu na janela (notas/docs por mtime; tarefas por timestamp
  da linha; ignora `resumos/`), `ctx.summarize` (=`Brain.summarize`) sintetiza, e
  `helpers.write_summary_note` salva em `<vault>/resumos/`. O `Index._scan` inclui
  `resumos/`, entao resumos ficam pesquisaveis pelo RAG.

### 4.7 Busca na web — `anta/core/websearch.py` (v0.3, OPT-IN)
- **Rompe o offline** (a query vai para um buscador), por isso e desligado por padrao
  (`web=false`). NAO e o comportamento default da ANTA — e uma excecao consciente.
- `search(query, engine, searxng_url)` -> `[Result]` best-effort (falha -> `[]`): DuckDuckGo
  keyless via `ddgs` (import preguicoso, dep opcional) ou SearXNG (JSON, so stdlib). So LE
  resultados; a sintese e do LLM.
- Acao `BuscarWeb(consulta)` -> `handlers/buscar_web.py`: se `ctx.web_search is None` (web
  off) responde que esta desativado; senao busca, sintetiza via **`ctx.answer_web`**
  (`Brain.answer_web`, prompt `BUSCA`) e anexa as fontes. O Pipeline injeta `web_search` +
  `answer_web` so quando `web=true`. Config: `web`, `web_engine`, `web_searxng_url`.
- **`BUSCA` e separado do `ANSWER` de proposito.** O `ANSWER` (notas) manda dizer "nao
  encontrei" quando o contexto nao responde — certo pro RAG, errado pra web: uma busca que
  trouxe 3 paginas uteis virava "Nao encontrou." **com as fontes listadas logo abaixo**,
  contradizendo a si mesma. Resultado de busca quase nunca responde ao pe da letra; o
  `BUSCA` manda dizer o que os resultados DE FATO cobrem.

### 5. Executor — `anta/actions/` (fachada + handlers)
- `executor.py` e uma fachada fina: `execute(decisao, ctx)` despacha via
  `registry.HANDLERS` (mapa explicito tipo-de-acao -> handler; sem decorator/magia).
- Um arquivo por acao em `handlers/`, com `handle(acao, ctx) -> str`.
  `criar_documento` converte via `pandoc` quando `formato != "md"`; `responder`
  fala via `anta/core/tts.speak` (Piper) se `ctx.tts`.
- **Redacao em 2 passes** (`CriarNota`/`CriarDocumento` com `expandir=true`): o `conteudo`
  do `decide()` e so um ESBOCO — sai a temperatura 0.1, dentro de uma string JSON com
  gramatica e sob a persona de voz. `helpers.corpo_da_nota(acao, ctx)` chama `ctx.write`
  (-> `Brain.write`, prompt `ESCRITA`, temp 0.6, com a janela de conversa) para redigir.
  Best-effort: sem `ctx.write` ou se a redacao falhar/vier vazia, fica o esboco — nota
  rasa e melhor que nota nenhuma. `expandir=false` grava LITERAL (o usuario ditou).
- `apps.py`: whitelist de `abrir_app` isolada (`lookup`/`permitidos`).
  `context.py`: `ExecContext` + constantes (agora carrega `rag`/`answer`/`summarize`,
  injetados em runtime pelo `Pipeline`, anotados sob `TYPE_CHECKING` p/ a folha seguir
  stdlib-only). `helpers.py`: `slug`/`unique_path`/`note_body`/`write_memory_note` +
  helpers do resumo (`window_start`/`gather_activity`/`write_summary_note`).
- Adicionar acao = classe no schema + arquivo em `handlers/` + 1 linha em `HANDLERS`
  (o teste de exaustividade em `tests/test_apps.py` cobre o resto). `lembrar`/`consultar`
  (v0.3) seguem esse padrao; `consultar` usa `ctx.rag`/`ctx.answer` (ver 4.6).

### 6. Pipeline — `anta/core/pipeline.py`
- `run(audio)`: transcribe → decide(texto, history) → execute → aplica canal automatico
  de memoria (`Decisao.memoria`) → registra o turno na janela → retorna feedback.
- Possui a memoria de sessao (`deque`) e o `RAG` (quando `rag=true`); `warm()` pre-aquece
  o indice em thread best-effort. Ver 4.6.
- **`cancel()` = cancelamento COOPERATIVO.** Whisper e LLM sao chamadas bloqueantes e
  nao dao pra interromper no meio, entao a flag e checada nas FRONTEIRAS de etapa (pos-STT,
  pos-decide e **antes do execute**) e o que ainda nao aconteceu nao acontece — parar tem
  que impedir o EFEITO (criar nota, abrir app), nao so calar a voz depois do fato. A fala
  morre na hora (`tts.stop`). Turno cancelado devolve `CANCELADO` e nao entra no historico.
  `unload()` cancela antes de soltar os modelos.

### 7. Runtime / loop — `anta/__main__.py` (`run`)
- `run` e um **daemon quente** (Whisper carregado + LLM via `OLLAMA_KEEP_ALIVE`):
  carrega config, monta `Pipeline`, `warm()`, e alterna a gravacao no toggle.
  E o modo **headless**, sem janela e sem bandeja — ver 7.5 para o modo normal (HUD).
- **`Session.request()` e a entrada UNICA de qualquer gatilho** (pynput, SIGUSR1,
  botao do HUD, menu da bandeja) e roteia por estado: suspenso -> so avisa; turno em
  andamento -> `cancel()`; ocioso -> arma o Event. Antes o gatilho so ARMAVA o Event:
  apertar "Falar" enquanto a ANTA respondia nao parava nada **e** deixava o Event
  armado — o turno acabava e comecava uma gravacao fantasma.
- `SIGUSR1` continua sem trabalho pesado no handler: ele so seta um Event e uma
  thread despachante (`install_sigusr1`) chama a `request()`. Cancelar mexe em audio
  (`sd.stop()`), que nao pode rodar de dentro de um signal handler.
- `Session.suspend()/resume()`: "desalocar memoria" nao e so soltar o modelo — a
  ANTA para de aceitar gatilhos ate carregar de novo. Sem isso o proximo atalho
  recarregava tudo em silencio e a memoria voltava pelas costas do usuario.
- Feedback via `notify-send` (Linux) / `print`.

### 7.5 App de execucao (HUD) — `anta/gui/` (fases do frontend em `docs/frontend-fases.md`)
- `anta app` e o modo **normal**: janela PyWebview + Vue, bandeja e o mesmo loop
  push-to-talk (mesma `Session`, mesmo `Pipeline`). `runtime_app.py` faz o wiring;
  `bridge_runtime.RuntimeApi` e a API exposta ao Vue; `state.StateMachine` empurra
  cada transicao pro front (`window.__antaOnState`).
- **A bandeja reflete o estado** (`tray.Tray.on_state` assina a `StateMachine`):
  cor do icone + tooltip + rotulos do menu. Um app residente que ocupa VRAM tem que
  mostrar o que esta fazendo; icone mudo (ou nenhum) e indistinguivel de vazamento.
  Falha da bandeja e LOGADA (`return None` mudo e o pior desfecho num app sem console).
- **Com bandeja no ar, o X esconde** (`_fechar_para_a_bandeja`); "Sair" do menu marca
  `tray.quitting` e ai o `closing` deixa fechar. Sem bandeja o X encerra normalmente —
  esconder sem icone nenhum deixaria a ANTA invisivel, o problema que se quer evitar.
- O HUD mostra **VRAM/RAM em uso** (`RuntimeApi.get_memory`, polling de 10s). A VRAM e
  a da placa (o LLM vive no processo do Ollama); a RAM e o RSS da ANTA (Whisper +
  embedder, que por principio ficam na CPU). Sem medicao -> `None` e o HUD omite; 0.0
  seria uma afirmacao falsa.
- **`cancel()` e um metodo proprio, nao um `toggle`**: se o turno terminar entre o
  render e o clique, cancelar vira no-op — um toggle atrasado comecaria a gravar.
- **Uma instancia por app** (`anta/platform/singleton.py`): lock de arquivo do SO
  (`flock`/`msvcrt`), nao pidfile — processo morto no tapa nao deixa trava velha, e
  PID reciclado nao engana. Travas: `runtime` (compartilhada por `anta app` e
  `anta run` — e o mesmo assistente com e sem janela; duas = dois Whispers na RAM,
  dois preloads na VRAM, dois `pynput` no mesmo atalho) e `config` (o Configurador e
  o unico writer do TOML; duas janelas editando = a ultima a salvar apaga a outra).
  A 2a tentativa nao abre: escreve a sentinela `<nome>.focus`, que a instancia viva
  consome num watcher e MOSTRA a janela. E a unica IPC que funciona nos dois SOs
  (Windows nao tem sinais) e faz "abrir de novo" virar "traz pra frente".
- Falhar ao criar a trava (disco/permissao) NAO impede o app de abrir: a trava e
  comodidade, e virar "a ANTA nao abre" seria um remedio pior que a doenca.

### 7.6 Configurador (App A) — `anta/gui/config_app.py`
- `window_size()` corta o tamanho pedido pela TELA REAL (`webview.screens`) antes do
  minimo: pedir 1180x900 num monitor de 768 de altura faz o rodape (Voltar/Avancar/
  Salvar) nascer fora da area visivel.
- O card "Ambiente" mostra `os_label`/`detail` (de `Environment.label`/`.detail`),
  nao os campos crus: no Windows `os` e `session` valem os DOIS "windows", e a tela
  dizia "windows / windows". No Linux o detalhe e `sessao · desktop` (o que de fato
  muda a estrategia de atalho); no Windows, como o atalho global vai funcionar.

### 8. Instalador — `anta/installer/app.py`
- `Select` de **familia** (repovoa a tabela de modos no `Select.Changed`, guardado por
  `_ready` p/ nao correr antes das colunas) + selecao de linha (modo) + dropdown de
  microfone (`capture.list_input_devices`). Bloquear modos "vermelho". Salva family+mode.
- A tabela mostra `vram_gb` (**VRAM min** — gate que libera/bloqueia) e `vram_real`
  (**VRAM uso~** — consumo estimado do LLM carregado, so exibicao). Ambos vem de
  `modes.yaml`; `vram_real` e opcional no `Mode` (tier sem ele ainda carrega).
- Ao confirmar: `ollama pull <llm>`, baixar o modelo Whisper, baixar o modelo de
  embedding se `rag` (mesmo padrao do STT, best-effort), `save_user_config`,
  `prompts.write_default_prompts()` (cria o `prompts.toml` editavel se ausente),
  chamar `hotkey.setup_hotkey`. Campos novos da config (ex.: `rag`) sao preservados
  puxando de `self._cfg` (senao resetam ao default numa reinstalacao).

### 9. Atalho — `anta/platform/hotkey.py`
- `setup_hotkey` por estrategia (a ANTA captura a tecla via `pynput.GlobalHotKeys`
  no X11/Windows; no Wayland o atalho do SO chama `anta toggle`):
  - `auto_x11` / `auto_win`: autostart no login (`.desktop` / HKCU Run).
  - `compositor` (KDE/Wayland): autostart + instrucao de `docs/atalhos.md`
    preenchida com `anta toggle` (o caminho manual e o mais robusto no Wayland).
  - `manual`: so instrucao.
- **O login sobe o HUD (`anta app`), nao o daemon headless** — `autostart_subcommand()`
  so cai no `run` quando o front nao foi buildado (`hud_available()`). Ate a v0.4.3 o
  login subia `anta run`: Whisper na RAM, LLM fixo na VRAM, **nada** na tela nem na
  bandeja e sem console. De fora era um processo fantasma comendo memoria. O HUD tambem
  grava o pidfile, entao o `anta toggle` do Wayland continua valendo.
- `repair_autostart()` (chamado no boot do `anta run`) migra a entrada antiga
  `... run` -> `... app`. So mudar o codigo nao conserta a maquina de quem ja instalou;
  a entrada e da propria ANTA, e a migracao e idempotente e avisada.

## Testes
Suite em `tests/` (`unittest` stdlib):
`.venv/bin/python -m unittest discover -s tests`. Cobrem: `hardware.status_for`
(limites), `config.load_modes` + round-trip da config, `detect.hotkey_strategy`
(mock de env), schema (uniao discriminada por acao), executor (cada handler),
whitelist + exaustividade do registro (`tests/test_apps.py`), resolucao de mic
por nome (`test_capture.py`), guards do TTS + `_resolve_output` (`test_tts.py`) e
a camada de atalho: quoting, `_kde_key`, automacao KDE best-effort com fallback
manual (`test_hotkey.py`), o nucleo RAG com **embedder fake** (chunking, ranking por
cosseno, `reconcile` incremental, persistencia, prefixo e5, frescura no query —
`test_rag.py`), `Brain` com clients falsos (strip `<think>`, history/persona no prompt,
`summarize` — `test_brain.py`), o wiring do `Pipeline` (canal de memoria automatico +
best-effort, guard anti-duplicata, janela de conversa — `test_pipeline.py`), os prompts
editaveis (overlay/round-trip — `test_prompts.py`), os helpers do resumo (janelas +
`gather_activity` por mtime/timestamp — `test_helpers.py`) e a busca web (DDG via `ddgs`
falso + SearXNG via `urlopen` mockado, best-effort — `test_websearch.py`). Testes de I/O
usam fakes via `sys.modules`/injecao — nao dependem de PortAudio/piper/fastembed/ddgs/rede.

Da camada residente (v0.4.4): roteamento dos gatilhos e suspensao (`TestSessionRequest`
em `test_main.py`), cancelamento cooperativo (`test_pipeline.py`) e a interrupcao da fala
(`test_tts.py`), a bandeja com **pystray falso** — falha logada, icone/tooltip por estado,
rotulos e acoes do menu (`test_tray.py`), a ponte do HUD (cancel, unload que suspende,
`get_memory`, fechar-para-a-bandeja — `test_gui_runtime.py`) e o subcomando do login +
`repair_autostart` (`test_hotkey.py`). No front, `npm test` cobre a facade e o mock do
HUD (o mock ROTEIA como a `Session.request` — a UI nao pode ser desenvolvida contra um
comportamento que o backend nao tem).

## Nao-metas do MVP
- Audio do sistema / reuniao. Modo conversacional em tempo real (streaming).
  Gestao de memoria Linux (zram/systemd slice) — opcional, pos-MVP.
- (RAG + memoria deixaram de ser nao-meta: implementados na v0.3 — ver 4.6.)
