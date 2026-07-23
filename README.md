# ANTA — assistente de voz local, push-to-talk

> **ANTA** = Assistente de Notas, Textos e Ações. Pacote Python: `anta`.

Um assistente pessoal que roda **100% na sua máquina** — sem nuvem, sem conta, sem
assinatura. Você aperta um atalho, fala em português, e a ANTA transcreve, entende o
que você quis e **faz** a coisa: cria uma nota, gera um documento, adiciona uma tarefa,
abre um app, responde uma pergunta. **Nenhum áudio sai do computador.**

Ela também **lembra** ("lembre que eu prefiro docx"), **responde sobre as suas próprias
notas** ("o que eu anotei sobre o projeto?") e **resume** o que você produziu na semana —
tudo lendo só os seus arquivos, localmente.

Por que local? Porque o que você dita — ideias, tarefas, nomes, contexto de trabalho — é
seu. A ANTA foi desenhada em torno de uma restrição real: rodar bem numa **GPU de 8GB**,
sem mandar nada pra fora.

---

## O que ela faz (as ações)

Toda fala vira **uma** ação. É o LLM que decide qual, e o efeito acontece na sua máquina:

| Diga algo como… | A ANTA faz |
|---|---|
| *"Cria uma nota chamada Ideias: modo offline e instalador simples"* | escreve um `.md` no seu vault |
| *"Cria um documento em pdf chamado Proposta com o texto…"* | gera o `.md` e converte pra `docx`/`pdf` (pandoc) |
| *"Adiciona tarefa comprar café até sexta"* | anexa um checkbox no `tarefas.md` |
| *"Abre o obsidian"* / *"abre o navegador"* | abre um app da **whitelist** (nunca um comando arbitrário) |
| *"Como se escreve 'apprentice' em inglês?"* | responde (e fala, se o TTS estiver ligado) |
| *"Lembre que meu chefe se chama Ricardo"* | grava um fato durável na memória |
| *"O que eu anotei sobre o projeto X?"* | busca semântica nas suas notas e responde |
| *"Resumo da semana"* | varre o que você produziu e salva um resumo |
| *"Pesquisa na web as novidades de Y"* | busca na internet e responde citando as fontes *(opt-in, desligado por padrão)* |

O conjunto de ações é **fechado**: o LLM escolhe uma da lista, ele **nunca** gera um
comando de shell. `abrir_app` só aceita apps de uma whitelist. Segurança por construção.

---

## Como baixar e instalar

### Opção 1 — Instalador pronto (recomendado, sem Python/Node)

Um binário nativo que **já traz** a UI, o STT, o TTS e o RAG. Baixe o arquivo do seu
sistema na página de **[Releases](https://github.com/WesleyPaulo/ANTA/releases/latest)**:

- **Windows:** `ANTA-Setup.exe` — instala, cria o atalho e o item de inicialização.
- **Linux:** `ANTA-x86_64.AppImage` — dê permissão de execução e rode.

Na primeira vez abre o **Configurador** (uma janela): ele detecta seu hardware, você
escolhe o modelo e o microfone, e ele baixa o que falta. A **única** coisa que não vem no
pacote é o **[Ollama](https://ollama.com)** (o motor que roda o LLM) — mas o próprio
Configurador detecta se ele está instalado e **oferece instalar** ali mesmo.

### Opção 2 — A partir do código (Windows e Linux)

Precisa de `git`. O script traz o resto (libs nativas, pandoc, Ollama, Python via
[uv](https://docs.astral.sh/uv/)) e abre o instalador:

```bash
git clone https://github.com/WesleyPaulo/ANTA.git
cd ANTA
./install.sh                                             # Linux
powershell -ExecutionPolicy Bypass -File .\install.ps1  # Windows
```

Isso abre a **TUI** (instalador de terminal). Se quiser a janela gráfica em vez do
terminal, veja o Configurador (`anta config`) em **[docs/instalacao.md](docs/instalacao.md)**
— o passo a passo completo por SO, incluindo os pré-requisitos da GUI (Node + WebKit).

> **Hardware:** uma **GPU NVIDIA** é recomendada (o LLM roda nela). Sem NVIDIA, só o
> modo mais leve fica liberado e o LLM cai na CPU (mais lento). **macOS** não é suportado
> hoje — o gate de VRAM assume NVIDIA.

---

## Como funciona

O uso é **push-to-talk**: aperte o atalho (`ctrl+alt+space`), fale, aperte de novo pra
encerrar. A ANTA processa e responde — na tela e, opcionalmente, por voz.

```
atalho → microfone → faster-whisper (CPU) → LLM via Ollama (GPU)
       → ação estruturada (Pydantic) → executor → resposta (tela + voz)
```

A decisão de arquitetura central é **STT na CPU, LLM na GPU**. Numa placa de 8GB, rodar
o Whisper (transcrição) e o modelo de linguagem juntos na VRAM estouraria — então o
Whisper e o embedder de busca ficam na CPU, e a **VRAM inteira é do LLM**. A ANTA fica
residente (modelo quente na memória) esperando o atalho, com um ícone na bandeja que
mostra o estado (pronta / ouvindo / respondendo) e um botão pra **desalocar a memória**
quando você quiser a GPU de volta.

### Escolha do modelo (família × modo)

No instalador você escolhe uma **família** de modelos open-source e um **modo** por VRAM.
Tudo é declarativo em [`modes.yaml`](modes.yaml):

| Modo | VRAM mín. | STT | Qwen3 | Gemma | DeepSeek-R1 |
|------|-----------|-----|-------|-------|-------------|
| Batata | 1 GB | base | qwen3:0.6b | gemma3:1b | — |
| Ultra Leve | 2 GB | small | qwen3:1.7b | gemma2:2b | deepseek-r1:1.5b |
| Leve | 4 GB | turbo | qwen3:4b-instruct | gemma3:4b | deepseek-r1:1.5b |
| Normal | 6 GB | large-v3 | qwen3:4b-instruct | gemma3:4b | deepseek-r1:7b |
| Pesado | 8 GB | large-v3 | qwen3:8b | gemma2:9b | deepseek-r1:8b |
| Muito Pesado | 10 GB | large-v3 | qwen3:8b | gemma3:12b | deepseek-r1:14b |
| Ultra | 12 GB | large-v3 | qwen3:14b | gemma3:12b | deepseek-r1:14b |

Todos os modelos são **open-source, gratuitos e locais** (via Ollama). O instalador pinta
cada modo de verde/amarelo/vermelho conforme a sua VRAM, e bloqueia o que não cabe.

### O que roda por baixo

- **Captura de áudio:** `sounddevice` (só microfone — sem áudio do sistema, por ora).
- **Transcrição (STT):** `faster-whisper`, int8, na CPU.
- **Cérebro (LLM):** [Ollama](https://ollama.com) servindo a API compatível com OpenAI.
- **Saída estruturada:** `instructor` + `pydantic` — o schema das ações vira uma gramática
  no llama.cpp, então o modelo **não consegue** responder fora do conjunto de ações.
- **Voz (TTS):** `piper-tts` — voz PT-BR local (opcional, `tts = true`).
- **Memória + busca (RAG):** `fastembed` na CPU + busca por cosseno em `numpy` — lê só as
  suas notas (opcional, `rag = true`).
- **Busca na web (opt-in):** `ddgs` (DuckDuckGo) ou SearXNG — **desligada por padrão**
  (`web = false`) pra preservar o offline.
- **Documentos:** `pandoc` (Markdown → docx/pdf).
- **Interface:** apps desktop em Vue 3 + PyWebview (Configurador e HUD), com uma TUI
  (Textual) de fallback pra quem não quer a janela gráfica.

Externos, não instalados via pip: **Ollama** e **pandoc**.

---

## Comandos

| Comando | O que faz |
|---|---|
| `anta config` | **Configurador** (janela; wizard de configuração) |
| `anta app` | **App de execução** — o HUD na bandeja (push-to-talk) |
| `anta run` | Daemon **headless** (push-to-talk, sem janela) |
| `anta` | Instalador **TUI** (terminal) — fallback |
| `anta toggle` | Alterna a gravação (usado pelo atalho do SO no Wayland) |
| `anta mic` | Diagnóstico do microfone (device + nível do sinal) |
| `anta vozes` | Lista/instala vozes do TTS (Piper) |

> **Por que existe o `anta mic`:** um microfone mudo é indistinguível de um "LLM burro"
> pelo lado de fora — o Whisper **alucina** em cima do silêncio (devolve "E aí", "Obrigado"
> — frases que ninguém falou) e o modelo responde a alucinação com confiança. O `anta mic`
> mostra o pico do sinal, sem interpretação; e a ANTA recusa áudio silencioso em vez de
> deixar o STT inventar.

Configuração e estado ficam em `~/.config/anta/` (Linux) ou `%APPDATA%\anta\` (Windows):
`config.toml`, `prompts.toml` (persona e regras **editáveis**), índice do RAG, vozes.

---

## Para desenvolvedores

```bash
pip install -r requirements.txt
pip install -e . --no-deps                        # `anta` roda de qualquer pasta
cd frontend && npm ci && npm run build && cd ..   # front (para a GUI)

anta config          # Configurador (GUI)      anta app   # HUD na bandeja
anta run             # daemon headless          anta       # TUI (fallback)

# testes
.venv/bin/python -m unittest discover -s tests    # backend (Python)
cd frontend && npm test                           # ponte (Vitest)
```

UI com hot reload: `cd frontend && npm run dev` e, noutro terminal, `ANTA_GUI_DEV=1 anta
config`. Sem pywebview a UI roda no browser com dados de mock.

A arquitetura e os invariantes (por que cada decisão existe) estão em
**[CLAUDE.md](CLAUDE.md)**. Empacotamento em [packaging/README.md](packaging/README.md).

### Estrutura

```
anta/
  installer/   TUI Textual (fallback) + detecção de VRAM
  gui/         apps desktop (PyWebview): configurador · HUD · bandeja · bridge
  core/        capture · stt · brain · pipeline · config · rag · prompts · tts · websearch
  actions/     schema Pydantic · executor · registry · whitelist de apps
    handlers/  um arquivo por ação (criar_nota … consultar, resumir, buscar_web)
  platform/    detect (SO/sessão) · hotkey (atalho por SO) · singleton (instância única)
frontend/      monorepo Vue 3 + Vite + Tailwind (configurador + runtime)
packaging/     PyInstaller + instaladores (Inno/AppImage)
modes.yaml     manifesto dos modelos por VRAM
docs/          instalacao · atalhos · windows · validacao-nativa · casos-de-uso
```

---

## Estado do projeto

- **Windows:** validado ponta a ponta (v0.4.x) — instalador `.exe`, Configurador, HUD,
  atalho, transcrição, resposta na tela e por voz.
- **Linux:** alvo primário; a suíte de testes roda aqui. O loop de voz completo ainda não
  foi exercitado em Linux nativo.
- **macOS:** não suportado (o gate de VRAM assume NVIDIA).

Roadmap e detalhes de cada versão em [docs/](docs/). Próximo grande item: **modo reunião**
(áudio do sistema via PipeWire/WASAPI).

## Licença

MIT.
