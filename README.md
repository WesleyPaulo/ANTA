# ANTA — assistente de voz local, push-to-talk

> **ANTA** = Assistente de Notas, Textos e Ações. Pacote Python: `anta`.

Assistente pessoal **100% local e offline**. Voce aperta um atalho, fala, e ele
transcreve, entende a intencao e executa uma acao segura (criar nota, gerar
documento, adicionar tarefa, abrir app). Nada de nuvem, nada de assinatura,
nenhum audio sai da maquina.

**Novo na v0.3 — memoria + busca (RAG) + resumos:** a ANTA lembra fatos duraveis sobre
voce ("lembre que prefiro docx", ou automaticamente na conversa), responde perguntas
sobre as suas proprias notas ("o que anotei sobre o projeto?") via busca semantica no
vault, e faz resumos do que voce produziu ("resumo da semana" -> salvo em `resumos/`). O
embedding roda **na CPU** — a VRAM segue exclusiva do LLM. Os prompts (persona/tom/regras)
sao editaveis em `prompts.toml`, sem tocar no codigo. Ha tambem uma **busca na web opt-in**
(`web = true`, desligada por padrao pra manter o offline) que responde citando as fontes.

## Como funciona

```
atalho (toggle) → microfone → faster-whisper (CPU) → LLM via Ollama (GPU)
                → acao estruturada (Pydantic) → executor → feedback
```

Decisao de arquitetura central: **STT na CPU, LLM na GPU.** Em placas de 8GB,
rodar Whisper e o modelo de linguagem juntos na VRAM estouraria — separar
mantem a GPU inteira para o LLM.

## Familias e modos por VRAM

No instalador voce escolhe uma **familia** de modelos open-source e depois um **modo** (tier)
por VRAM. Tudo declarativo em `modes.yaml` (tiers compartilhados × familias). O tier define o
gate de VRAM + o STT; a familia troca o modelo (LLM).

| Tier | Gate | STT | Qwen3 | Gemma | DeepSeek-R1 |
|------|------|-----|-------|-------|-------------|
| Batata | 1GB | base | qwen3:0.6b | gemma3:1b | — |
| Ultra Leve | 2GB | small | qwen3:1.7b | gemma2:2b | deepseek-r1:1.5b |
| Leve | 4GB | turbo | qwen3:4b-instruct | gemma3:4b | deepseek-r1:1.5b |
| Normal | 6GB | large-v3 | qwen3:4b-instruct | gemma3:4b | deepseek-r1:7b |
| Pesado | 8GB | large-v3 | qwen3:8b | gemma2:9b | deepseek-r1:8b |
| Muito Pesado | 10GB | large-v3 | qwen3:8b | gemma3:12b | deepseek-r1:14b |
| Ultra | 12GB | large-v3 | qwen3:14b | gemma3:12b | deepseek-r1:14b |

- **Gate** = VRAM minima que o instalador exige; o `vram_real` (consumo estimado do LLM) fica
  abaixo, com folga. STT/embedder rodam na CPU e nao contam (a VRAM e so do LLM).
- **Saida estruturada por gramatica** (`structured: "json_schema"`): o schema das acoes vai no
  `response_format` e o Ollama compila uma gramatica GBNF no llama.cpp — o modelo nao consegue
  responder fora do schema. Tool-calling **nao** serve aqui: o Ollama ignora `tool_choice`, entao
  a ferramenta nunca e obrigatoria e o modelo simplesmente conversa.
- **Raciocinio desligado** no roteamento: o Ollama liga o "thinking" sozinho em todo modelo que
  sabe pensar, e isso quebra o tool-calling (o modelo escreve a chamada como texto). A ANTA pede
  `reasoning_effort: "none"`. Nos tiers leve/normal do Qwen3 usamos `qwen3:4b-instruct` porque o
  tag `qwen3:4b` aponta pro Thinking-2507, que pensa sempre — nao ha como desligar.
- **DeepSeek-R1 sao modelos de raciocinio** (pensam antes de responder): mais lentos e menos
  confiaveis pro roteamento de comandos — melhores pra respostas/RAG. Sem `batata` (nada cabe em 1GB).
- Todos sao **open-source, gratuitos e locais** (via Ollama). Adicionar familia/tier = um bloco
  no `modes.yaml`. O instalador nao muda.

## Stack

- **Instalador**: Python + [Textual](https://textual.textualize.io) — TUI que
  roda identica em Windows e Linux; parece um painel mas vive no terminal.
- **Deteccao de VRAM**: `nvidia-smi` (principal) com fallback `pynvml`.
- **Captura de audio**: `sounddevice` — microfone, cross-platform (MVP so mic).
- **STT**: `faster-whisper` (CTranslate2), int8 na CPU.
- **LLM**: [Ollama](https://ollama.com) servindo a API compativel com OpenAI.
- **Saida estruturada**: `instructor` + `pydantic` (conjunto fechado de acoes).
- **Documentos**: `pandoc` (Markdown → docx/pdf).
- **Voz (TTS)**: `piper-tts` — voz PT-BR local, reproduzida pelo `sounddevice`
  (opcional, so quando `tts = true`).
- **Memoria + RAG**: `fastembed` (onnxruntime) — embedding multilingue **na CPU**;
  store por cosseno em `numpy` (sem faiss/chroma). Opcional, so quando `rag = true`.
- **Busca na web (opt-in)**: `ddgs` (DuckDuckGo, keyless) ou SearXNG (JSON, stdlib).
  Desligada por padrao (`web = false`) pra preservar o offline; so quando `web = true`.
- **Atalho global**: automatico no Windows e Linux/X11; no Wayland/KDE o
  instalador tenta configurar via compositor, com fallback manual documentado.

Externos (nao via pip): **Ollama** e **pandoc**.

## Escopo do MVP (v0.1)

- **So microfone** (sem audio do sistema / reuniao).
- **Linux** e o alvo testado. **Windows** e cross-platform no codigo (deteccao,
  VRAM via NVIDIA, atalho, config em %APPDATA%) e deve rodar em Windows+NVIDIA,
  mas ainda nao foi testado. **macOS** nao e suportado: o gating por VRAM assume
  GPU NVIDIA e bloqueia o instalador em Apple Silicon.
- Atalho: instrucao correta por SO; automacao onde e confiavel, doc onde nao e.

## Instalacao (usuario)

Um comando instala os pre-requisitos (libs nativas, pandoc, Ollama), prepara o
ambiente com [uv](https://docs.astral.sh/uv/) e abre o instalador TUI:

```bash
./install.sh                                              # Linux e macOS
powershell -ExecutionPolicy Bypass -File .\install.ps1    # Windows
```

## Instalacao (dev)

```bash
pip install -r requirements.txt
pip install -e . --no-deps   # instala o pacote: `anta` roda de qualquer pasta
anta                         # abre o instalador (TUI)   (ou: python -m anta)
anta run                     # roda o assistente (apos configurar)
anta mic                     # diagnostico: qual mic foi resolvido + nivel do sinal
```

O `anta mic` existe porque um microfone mudo e indistinguivel de um LLM burro pelo lado de
fora: o Whisper **alucina** em cima do silencio (devolve "E ai", "Obrigado" — frases que
ninguem falou), o modelo responde a alucinacao, e a culpa parece ser do modelo. O `anta mic`
mostra o pico do sinal, sem interpretacao. O `anta run` tambem exibe `ouvi: "..."` a cada
comando e recusa audio silencioso em vez de deixar o STT inventar.

O `-e .` importa: sem ele, `python -m anta` so funciona com o CWD na raiz do repo — e o
autostart do login roda com outro CWD.

## Estrutura

```
anta/
  installer/   TUI Textual + deteccao de VRAM (hardware.py)
  core/        capture · stt · brain · pipeline · config · rag · prompts · websearch
  actions/     schema Pydantic · executor (fachada) · registry · apps (whitelist)
    handlers/  um arquivo por acao (criar_nota, ..., consultar, resumir, buscar_web)
  platform/    detect (SO/sessao) · hotkey (atalho por SO)
modes.yaml     manifesto dos modos
docs/atalhos.md instrucoes de atalho por sistema
```

## Roadmap

- v0.1: MVP mic-only, Linux, instalador cross-platform, 3 modos.
- v0.2: TTS por voz (Piper, PT-BR); automacao best-effort do atalho no
  Wayland/KDE (com fallback manual); runtime Windows validado; correcoes
  cross-platform (mic por nome, tags de modelo, keep-alive no boot).
- v0.3 (atual): **memoria + RAG + resumos + prompts editaveis + busca web opt-in +
  familias de modelos** — busca semantica nas notas (`consultar`), memoria automatica +
  explicita (`lembrar`), resumos de atividade dia/semana/mes (`resumir`), busca na internet
  opcional (`buscar_web`, `web=true`), continuidade de conversa na sessao; embedding na CPU
  via `fastembed` (VRAM intacta); prompts em `prompts.toml` editavel; escolha de familia
  (Qwen3/Gemma/DeepSeek) + modo por VRAM, com `structured` tools/json por familia.
- v0.4: modo reuniao (audio do sistema via PipeWire/WASAPI).

### TODO

- **Busca academica (arXiv) como `web_engine`.** Motivo: pedir "os artigos mais importantes
  sobre X" pelo DuckDuckGo devolve conteudo de blog/SEO (DataCamp, IBM, LinkedIn), nao
  papers. O arXiv tem API publica e keyless — encaixa no mesmo contrato `search(query, ...)
  -> [Result]` de `websearch.py`, entao e um bloco novo la e uma opcao a mais em
  `web_engine`. Alternativa ja disponivel hoje: SearXNG com os engines academicos ligados.

## Licenca

MIT.
