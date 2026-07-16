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

## Modos por VRAM

O instalador detecta sua VRAM e recomenda o modo. Definidos em `modes.yaml`:

| Modo | VRAM min (gate) | VRAM uso~ | LLM | STT |
|------|-----------------|-----------|-----|-----|
| Batata | 1GB | ~0.7-1 GB | qwen3:0.6b | base |
| Ultra Leve | 2GB | ~1.5-1.8 GB | qwen3:1.7b | small |
| Leve | 4GB | ~3.3-3.6 GB | qwen3:4b | large-v3-turbo |
| Normal | 6GB | ~3.3-3.6 GB | qwen3:4b | large-v3 |
| Pesado | 8GB | ~6-6.5 GB | qwen3:8b | large-v3 |
| Muito Pesado | 10GB | ~6-6.5 GB | qwen3:8b | large-v3 |
| Ultra Esforco | 12GB | ~10-11 GB | qwen3:14b | large-v3 |

`VRAM min` e o gate (card minimo); `VRAM uso~` e o consumo estimado do LLM ja carregado
(STT/embedder rodam na CPU e nao contam). Adicionar um tier = um bloco novo no
`modes.yaml`. O instalador nao muda.

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
python -m anta            # abre o instalador (TUI)
python -m anta run        # roda o assistente (apos configurar)
```

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
- v0.3 (atual): **memoria + RAG + resumos + prompts editaveis + busca web opt-in** —
  busca semantica nas notas (`consultar`), memoria automatica + explicita (`lembrar`),
  resumos de atividade dia/semana/mes (`resumir`), busca na internet opcional
  (`buscar_web`, `web=true`), continuidade de conversa na sessao; embedding na CPU via
  `fastembed` (VRAM intacta); prompts (persona/tom/regras) em `prompts.toml` editavel.
- v0.4: modo reuniao (audio do sistema via PipeWire/WASAPI).

## Licenca

MIT.
