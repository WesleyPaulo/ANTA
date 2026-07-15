# Casos de uso do ANTA

O que dá pra fazer **hoje**, ancorado nas ações que o executor implementa. O
fluxo é sempre o mesmo: você aperta o atalho, fala em português, o Whisper
transcreve (CPU), o LLM via Ollama (GPU) classifica a intenção em **uma** ação,
e o executor faz o efeito — nada sai da máquina.

```
atalho (toggle) → microfone → faster-whisper → LLM (instructor) → Ação → executor → feedback
```

## Ações disponíveis

### 1. Criar nota — `criar_nota`
Escreve um `.md` no vault (`~/anta-notas/` ou o vault do Obsidian configurado;
nomes de arquivo únicos, não sobrescreve).

> *"Cria uma nota chamada Ideias de produto: precisamos de um modo offline e um instalador simples."*
> → `~/anta-notas/ideias-de-produto.md`

Uso: brainstorm mãos-livres, journaling, capturar algo enquanto lê/cozinha, PKM.

### 2. Criar documento — `criar_documento` (`md` / `docx` / `pdf`)
Escreve o `.md` e, se pedir `docx`/`pdf`, converte via **pandoc**.

> *"Cria um documento em pdf chamado Proposta comercial com o seguinte texto..."*
> → `~/anta-notas/proposta-comercial.pdf`

Uso: ditar carta/relatório/memo e já exportar pronto pra enviar.

### 3. Adicionar tarefa — `adicionar_tarefa`
Anexa um checkbox no `tarefas.md` do vault, com prazo opcional.

> *"Adiciona tarefa comprar café até sexta"*
> → `- [ ] comprar café  (prazo: sexta)`

Uso: inbox estilo GTD, capturar um to-do sem quebrar o fluxo.

### 4. Abrir aplicativo — `abrir_app`
Abre um app **da whitelist** (`anta/actions/apps.py`) — nunca um comando
arbitrário. Nomes aceitos: `obsidian`, `code`/`vscode`, `firefox`, `navegador`
(+ apelidos como `browser`, `chrome`). A whitelist é cross-platform (Linux usa
o binário, macOS `open -a`, Windows `start`).

> *"Abre o obsidian"* · *"abre o vscode"* · *"abre o navegador"*

Uso: lançar apps mãos-livres, com segurança garantida por construção. App não
instalado → feedback claro ("na whitelist, mas 'X' não está instalado").

### 5. Responder / conversar — `responder` (fala via Piper se `tts=true`)
Não altera nada no sistema; é também o *fallback* de qualquer fala que não vira
outra ação.

> *"Como se escreve 'apprentice' em inglês?"* · *"me dá 3 nomes pra um projeto de voz"*

Uso: Q&A rápido e privado, 100% offline. Para ouvir a resposta em voz, marque
**"Falar respostas (TTS)"** no instalador (baixa uma voz PT-BR do Piper) ou
ligue `tts = true` no `config.toml`.

## Cenários combinados (o valor no dia a dia)

- **Trabalho privado/offline:** nada de áudio ou texto sai da máquina — bom pra
  dados sensíveis (jurídico, saúde, pesquisa) ou pra quem quer zero nuvem.
- **PKM no Obsidian:** notas e documentos caem como `.md` no vault; depois
  *"abre o obsidian"* pra revisar.
- **Acessibilidade / mãos-livres:** ditar em vez de digitar.
- **Escrita rápida:** ditar rascunho → exportar `docx`/`pdf` sem abrir editor.

## Variação por hardware (`modes.yaml`)

| Modo | VRAM | Perfil |
|------|------|--------|
| Leve | 4GB | comandos rápidos e notas curtas (`qwen3:4b` + Whisper `turbo`) |
| Pesado | 8GB | documentos e PT-BR preciso (`qwen3:8b` + `large-v3`) |
| Ultra | 12GB | máxima qualidade (`qwen3:14b`) |

## Fronteiras — o que **não** é caso de uso hoje

- ❌ Transcrever reunião / áudio do sistema — só o seu microfone (não-meta do MVP).
- ❌ Buscar/perguntar sobre as suas próprias notas — sem RAG ainda.
- ❌ Conversa contínua em tempo real — é push-to-talk, **um comando por vez**.
- ❌ Executar app/comando arbitrário — só a whitelist (garantia de segurança).
- ❌ Integrar com Todoist/Notion/etc. — tarefas vão pra um `tarefas.md` local.

### Suporte por SO

| SO | Status |
|----|--------|
| **Linux** | Alvo **testado**. |
| **Windows** | **Implementado, não testado** — o código trata detecção, VRAM (via NVIDIA, o caso comum no Windows), atalho (`pynput` + autostart no registro, agora com o interpretador entre aspas), config em `%APPDATA%` e a whitelist. Deve rodar numa máquina Windows+NVIDIA. Checklist de validação em [docs/windows.md](windows.md). |
| **macOS** | **Não suportado** — o gating de modo por VRAM assume GPU NVIDIA e bloqueia o instalador em Apple Silicon; o atalho é só manual. |

No WSL2 o microfone é instável, então o teste real do loop de voz pede Linux/Windows nativo.

## Estender

Adicionar um 6º caso de uso é barato: nova classe em `anta/actions/schema.py` +
um arquivo em `anta/actions/handlers/` (`handle(acao, ctx) -> str`) + uma linha
em `anta/actions/registry.py`. O teste de exaustividade avisa se esquecer o
registro. Um novo app pra abrir não precisa de handler — só uma entrada em
`anta/actions/apps.py`.
