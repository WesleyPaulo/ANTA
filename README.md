# ANTA — assistente de voz local, push-to-talk

> **ANTA** = Assistente de Notas, Textos e Ações. Pacote Python: `anta`.

Assistente pessoal **100% local e offline**. Voce aperta um atalho, fala, e ele
transcreve, entende a intencao e executa uma acao segura (criar nota, gerar
documento, adicionar tarefa, abrir app). Nada de nuvem, nada de assinatura,
nenhum audio sai da maquina.

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

| Modo | VRAM | LLM | STT |
|------|------|-----|-----|
| Leve | 4GB | qwen3:4b | large-v3-turbo |
| Pesado | 8GB | qwen3.5:9b | large-v3 |
| Ultra Esforco | 12GB | qwen3.5:14b | large-v3 |

Adicionar um tier = um bloco novo no `modes.yaml`. O instalador nao muda.

## Stack

- **Instalador**: Python + [Textual](https://textual.textualize.io) — TUI que
  roda identica em Windows e Linux; parece um painel mas vive no terminal.
- **Deteccao de VRAM**: `nvidia-smi` (principal) com fallback `pynvml`.
- **Captura de audio**: `sounddevice` — microfone, cross-platform (MVP so mic).
- **STT**: `faster-whisper` (CTranslate2), int8 na CPU.
- **LLM**: [Ollama](https://ollama.com) servindo a API compativel com OpenAI.
- **Saida estruturada**: `instructor` + `pydantic` (conjunto fechado de acoes).
- **Documentos**: `pandoc` (Markdown → docx/pdf).
- **Atalho global**: automatico no Windows e Linux/X11; no Wayland/KDE via
  compositor, com fallback documentado.

Externos (nao via pip): **Ollama** e **pandoc**.

## Escopo do MVP (v0.1)

- **So microfone** (sem audio do sistema / reuniao).
- **So Linux** como alvo de execucao — o instalador ja e cross-platform e
  detecta VRAM nos dois SOs; Windows fica marcado como "planejado".
- Atalho: instrucao correta por SO; automacao onde e confiavel, doc onde nao e.

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
  core/        capture · stt · brain · pipeline · config
  actions/     schema Pydantic · executor (fachada) · registry · apps (whitelist)
    handlers/  um arquivo por acao (criar_nota, criar_documento, ...)
  platform/    detect (SO/sessao) · hotkey (atalho por SO)
modes.yaml     manifesto dos modos
docs/atalhos.md instrucoes de atalho por sistema
```

## Roadmap

- v0.1: MVP mic-only, Linux, instalador cross-platform, 3 modos.
- v0.2: automacao de atalho no Wayland; Windows runtime; TTS (Piper).
- v0.3: modo reuniao (audio do sistema via PipeWire/WASAPI); RAG sobre notas.

## Licenca

MIT.
