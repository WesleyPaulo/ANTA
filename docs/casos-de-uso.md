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

### 6. Lembrar um fato — `lembrar` (memória, novo na v0.3)
Grava um fato durável sobre você numa nota em `~/anta-notas/memoria/`, que passa a
ser recuperável pela busca. Além do pedido explícito, a ANTA também **anota sozinha**
fatos duráveis que aparecem na conversa (canal automático).

> *"Lembre que eu prefiro documentos em docx"* · *"Anota que meu chefe se chama Ricardo"*
> → `~/anta-notas/memoria/prefiro-documentos-em-docx.md`

Uso: ensinar preferências e contexto pessoal uma vez e a ANTA lembrar depois.

### 7. Consultar suas notas — `consultar` (RAG, novo na v0.3)
Faz uma busca semântica no vault inteiro (notas + documentos + memória), recupera os
trechos mais relevantes e o LLM **responde ancorado neles** (não inventa; se não achar,
diz que não achou). O embedding roda na **CPU** — a VRAM segue exclusiva do LLM.

> *"O que eu anotei sobre o projeto de voz?"* · *"Qual era o prazo que eu registrei?"*
> → busca no vault → responde com base nas suas notas

Uso: transformar o vault num segundo cérebro consultável por voz, 100% local. Ligado
por padrão (`rag = true`); desligue com `rag = false` no `config.toml`.

**Continuidade da conversa:** a ANTA também guarda os últimos comandos da sessão (em
memória, some ao reiniciar) para resolver referências — *"cria outra igual"*, *"e o
prazo disso?"*.

### 8. Resumo de atividade — `resumir` (dia / semana / mês, novo na v0.3)
Varre o que você **produziu** no período (notas, documentos, tarefas e memória — por
data de modificação; tarefas pelo timestamp da linha), o LLM sintetiza um resumo curto
e ele é **salvo em `~/anta-notas/resumos/`** (indexado pelo RAG, então você pode
consultar resumos antigos depois). Janelas: dia = hoje, semana = 7 dias, mês = 30 dias.

> *"Me faz um resumo do que eu fiz hoje"* · *"resumo da semana"* · *"o que produzi esse mês?"*
> → `~/anta-notas/resumos/2026-07-15-semana.md` (falado + salvo)

Uso: fechamento de dia/semana, relatório de atividade mãos-livres, retomar o fio depois.

### 9. Buscar na web — `buscar_web` (OPT-IN, novo na v0.3)
Busca na internet e o LLM sintetiza a resposta com as fontes. **Rompe o offline** — por
isso é desligado por padrão (`web = false`). Ligue com `web = true` no `config.toml`.
Backend keyless por padrão (DuckDuckGo, sem chave); ou aponte uma instância **SearXNG**
(`web_engine = "searxng"` + `web_searxng_url`). Só é acionado por pedido explícito de
busca ou pergunta que exige a internet.

> *"Pesquisa na web quem ganhou o jogo ontem"* · *"procura na internet o preço do dólar hoje"*
> → busca → o LLM responde citando as fontes

Uso: informação atual/factual que o modelo local não tem. Quem não ligar segue 100%
offline — nada de web sem opt-in.

## Cenários combinados (o valor no dia a dia)

- **Trabalho privado/offline:** nada de áudio ou texto sai da máquina — bom pra
  dados sensíveis (jurídico, saúde, pesquisa) ou pra quem quer zero nuvem. (A única
  exceção é a busca web, que é **opt-in** e desligada por padrão.)
- **PKM no Obsidian:** notas e documentos caem como `.md` no vault; depois
  *"abre o obsidian"* pra revisar.
- **Acessibilidade / mãos-livres:** ditar em vez de digitar.
- **Escrita rápida:** ditar rascunho → exportar `docx`/`pdf` sem abrir editor.

## Variação por hardware (`modes.yaml`)

Você escolhe uma **família** (Qwen3 / Gemma / DeepSeek-R1) e depois um **modo** (tier) por
VRAM. O `vram_gb` é o **gate** (card mínimo que o instalador exige); o `vram_real` é o
**consumo estimado** do LLM já carregado (STT e embedder são CPU e não contam). O perfil de
cada tier é o mesmo em toda família — só o modelo muda:

| Tier | Gate | Perfil |
|------|------|--------|
| Batata | 1GB | roda em quase qualquer GPU; modelo minúsculo (roteamento erra mais) |
| Ultra Leve | 2GB | comandos simples |
| Leve | 4GB | comandos rápidos e notas curtas (STT `turbo`, rápido) |
| Normal | 6GB | uso geral com STT `large-v3` (PT-BR mais preciso) |
| Pesado | 8GB | documentos e PT-BR preciso |
| Muito Pesado | 10GB | modelo grande com folga p/ contexto (`OLLAMA_CONTEXT_LENGTH`) |
| Ultra | 12GB | máxima qualidade |

Modelos por família em [modes.yaml](../modes.yaml) e na tabela do [README](../README.md).
**Qwen3** usa tool-calling (mais confiável no roteamento); **Gemma** e **DeepSeek** usam JSON.
**DeepSeek-R1 são modelos de raciocínio** — mais lentos por comando, melhores pra respostas/RAG.
Todos open-source, gratuitos e locais (via Ollama).

## Ajustando o tom e as regras (prompts editáveis)

O comportamento da ANTA (persona/tom, como ela decide a ação, como responde e resume)
vive em prompts editáveis. O instalador cria `~/.config/anta/prompts.toml` (ou
`%APPDATA%\anta\prompts.toml`) com os padrões comentados — edite `persona` para mudar a
voz em tudo, ou `decide`/`answer`/`resumo` para regras específicas. Apague uma chave (ou
o arquivo) para voltar ao padrão do código. Os padrões ficam em `anta/core/prompts.py`.

## Fronteiras — o que **não** é caso de uso hoje

- ❌ Transcrever reunião / áudio do sistema — só o seu microfone (não-meta do MVP).
- ❌ Conversa contínua em tempo real — é push-to-talk, **um comando por vez** (mas há
  memória curta de sessão para resolver referências entre comandos).
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

Adicionar mais um caso de uso é barato: nova classe em `anta/actions/schema.py` +
um arquivo em `anta/actions/handlers/` (`handle(acao, ctx) -> str`) + uma linha
em `anta/actions/registry.py`. O teste de exaustividade avisa se esquecer o
registro. Um novo app pra abrir não precisa de handler — só uma entrada em
`anta/actions/apps.py`.
