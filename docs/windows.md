# ANTA no Windows — instalação e uso

> **Status honesto:** o código é cross-platform (detecção de SO, VRAM via NVIDIA, atalho
> in-process, config em `%APPDATA%`), mas o alvo **testado** é Linux. O Windows está
> **implementado e não validado ponta-a-ponta**. Este guia é o fluxo pretendido; o
> checklist no fim serve pra registrar o que quebrar na primeira validação real.

> **Interface gráfica (novo):** este guia cobre a **TUI** (terminal), que é o caminho
> validado. Há também um **Configurador** (`anta config`) e um **HUD** na bandeja
> (`anta app`) em janela — precisam do front buildado (`cd frontend && npm ci && npm run build`;
> o WebView2 já vem no Windows). O passo a passo unificado (TUI/GUI/exe) está em
> [instalacao.md](instalacao.md). A TUI segue como fallback.

## Pré-requisitos

- Windows 10/11.
- **GPU NVIDIA com driver atualizado** — o gating de modo usa `nvidia-smi`. Sem NVIDIA,
  só o modo *Batata* fica selecionável (amarelo) e o LLM roda na **CPU** (funciona, mas lento).
- **`winget`** (o bootstrap usa pra trazer pandoc e Ollama). Sem winget, instale à mão:
  [Ollama](https://ollama.com) e [Pandoc](https://pandoc.org).

## Passo a passo

### 1. Bootstrap

Abra o PowerShell **na pasta do repo**:

```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```

O script faz **tudo isto** (não precisa rodar nada antes):
1. instala o `uv` (gerencia Python + venv);
2. via `winget`: **pandoc** + **Ollama**;
3. recarrega o PATH (winget grava no registro, não na sessão);
4. cria a `.venv` (Python 3.12) e instala o `requirements.txt`;
5. instala o próprio pacote (`uv pip install -e .`) — é o que faz o `anta` funcionar
   **de qualquer pasta** (e cria o comando `anta`);
6. abre o **instalador TUI**.

### 2. Configurar na TUI

1. **Família**: Qwen3 (recomendado — tool-calling mais confiável), Gemma ou DeepSeek-R1.
2. **Modo**: escolha uma linha **verde** (ou amarela = apertado). Vermelho = não roda.
   A tabela mostra `VRAM min` (gate) e `VRAM uso~` (consumo estimado do LLM).
3. **Microfone**: escolha no dropdown.
4. **TTS**: marque "Falar respostas" se quiser voz (baixa uma voz PT-BR do Piper).
5. Clique em **Instalar**.

Isso executa: `ollama pull <llm>`, baixa o modelo Whisper, baixa o embedder (RAG),
baixa a voz (se TTS), salva `%APPDATA%\anta\config.toml` e `prompts.toml`, e registra o
daemon no autostart (`HKCU\...\Run`).

> Se o `ollama pull` falhar: o Ollama precisa estar **rodando** (após o winget ele sobe como
> app na bandeja). Abra o Ollama e repita a instalação.

### 3. Rodar o daemon

**Isto é o que você roda além do `install.ps1`:**

```powershell
.\.venv\Scripts\anta.exe run
```
(ou `.\.venv\Scripts\python.exe -m anta run` — equivalente)

#### Digitar só `anta run`, de qualquer pasta

O `anta.exe` já existe; falta o diretório dele no PATH do usuário:

```powershell
$s = "C:\PROJETOS\ANTA\.venv\Scripts"     # ajuste se o repo estiver noutro lugar
$p = [Environment]::GetEnvironmentVariable('Path','User')
if ($p -notlike "*$s*") { [Environment]::SetEnvironmentVariable('Path', "$p;$s", 'User') }
```

Abra um terminal **novo** e `anta run` / `anta mic` funcionam de qualquer lugar.

> **Não** use `setx PATH "%PATH%;..."`: o `setx` trunca em 1024 caracteres e expande as
> variáveis, o que corrompe/apaga o PATH. O bloco acima escreve só o escopo do usuário,
> sem expandir.

Deixe a janela aberta. Ela:
- carrega o Whisper (CPU) e **fixa o LLM na VRAM** (keep-alive no boot);
- passa a ouvir **`ctrl+alt+space`** in-process (via `pynput`);
- **mostra o feedback** — no Windows não há `notify-send`, o retorno sai no terminal.

#### Inicialização automática no login

O instalador **já registra** o daemon em `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`.
Confira e, se faltar, registre à mão:

```powershell
# ver o que está registrado (deve sair o caminho do python.exe do .venv + "-m anta run")
reg query "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v anta

# registrar/corrigir (aspas no interpretador são obrigatórias)
reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v anta /t REG_SZ `
  /d '"C:\PROJETOS\ANTA\.venv\Scripts\python.exe" -m anta run' /f

# desativar
reg delete "HKCU\Software\Microsoft\Windows\CurrentVersion\Run" /v anta /f
```

Faça logoff/logon: a ANTA sobe sozinha e o `ctrl+alt+space` funciona sem abrir terminal.

> **Uma janela de console vai aparecer** e precisa ficar aberta — ela É o canal de feedback
> no Windows (não há `notify-send`; é lá que saem o `ouvi:`, a ação e a resposta). Trocar
> `python.exe` por `pythonw.exe` esconde a janela, mas aí você fica **sem retorno nenhum** —
> só o TTS falando, se estiver ligado. Minimize a janela em vez de escondê-la.

### 4. Usar

`ctrl+alt+space` (começa a gravar) → fale → `ctrl+alt+space` (encerra) → ele transcreve,
decide a ação e executa. Exemplos: *"cria uma nota chamada ideias: ..."*, *"adiciona
tarefa comprar café até sexta"*, *"o que anotei sobre o contrato?"*, *"resumo da semana"*,
*"abre o obsidian"*.

### 5. Onde ficam as coisas

Sem `obsidian_vault` configurado, o vault padrão é `C:\Users\<voce>\anta-notas`:

```
C:\Users\<voce>\anta-notas\
├── <titulo>.md      notas (criar_nota) e documentos (criar_documento)
├── tarefas.md       adicionar_tarefa acrescenta uma linha aqui
├── memoria/         lembrar + o canal automático de memória
└── resumos/         resumir (dia/semana/mês)
```

Para usar seu vault real do Obsidian, edite `%APPDATA%\anta\config.toml`:

```toml
obsidian_vault = "C:/Users/<voce>/Documents/MeuVault"   # barras normais
```

O RAG (`consultar`) indexa esse vault — apontá-lo pras suas notas de verdade é o que faz
a busca semântica valer a pena. Config e estado ficam em `%APPDATA%\anta\`:
`config.toml`, `prompts.toml`, `index/` (RAG), `embeddings/` (modelo do embedder).

> **`prompts.toml`**: cada campo comentado segue o padrão do código (que melhora a cada
> versão); ao descomentar, aquele campo congela no que você escreveu. Se você instalou
> antes de 2026-07-16, o arquivo saiu com uma **cópia** dos padrões e por isso ignora as
> melhorias — apague-o (`del %APPDATA%\anta\prompts.toml`) para voltar a acompanhar.

### 6. Trocar a voz (TTS)

```powershell
anta vozes                      # lista o catálogo PT + as instaladas + a em uso
anta vozes pt_BR-cadu-medium    # baixa, ativa e salva na config
```

O catálogo oficial do Piper tem **5 vozes em português**; há mais duas da comunidade, em
qualidade `high` (acima das `medium` oficiais):

| Voz | Qualidade | F0 medido | Origem |
|---|---|---|---|
| `pt_BR-faber-medium` | 22 kHz, media | ~170 Hz | oficial — padrão da ANTA |
| `pt_BR-cadu-medium` | 22 kHz, media | ~134 Hz | oficial |
| `pt_BR-jeff-medium` | 22 kHz, media | ~150 Hz | oficial |
| `pt_BR-edresson-low` | 16 kHz, baixa | ~158 Hz | oficial — mais leve/rápida |
| `pt_PT-tugão-medium` | 22 kHz, media | ~170 Hz | oficial — Portugal |
| `pt_BR-dii-high` | 22 kHz, **alta** | **~197 Hz** | comunidade — sem licença declarada |
| `pt_BR-miro-high` | 22 kHz, **alta** | ~118 Hz | comunidade — sem licença declarada |

> **Nenhuma fonte informa o gênero das vozes** — nem o `voices.json`, nem os `MODEL_CARD`,
> nem os cards dos repos da comunidade. Deduzir pelo nome do speaker é chute. O **F0**
> (frequência fundamental) acima foi **medido** das amostras/sínteses: é registro
> grave/agudo, um dado objetivo, e **não prova gênero**. Referência da literatura: fala
> adulta masculina ~85-155 Hz, feminina ~165-255 Hz. Para decidir, **ouça**:
> **https://rhasspy.github.io/piper-samples/** (filtre por "Portuguese").

#### Importar uma voz que não é do catálogo

O Piper só precisa do par **`<voz>.onnx` + `<voz>.onnx.json`** — não existe catálogo fechado.
Qualquer voz nesse formato serve, venha de onde vier:

```powershell
anta vozes C:\caminho\minha-voz.onnx        # arquivo local (o .json tem que estar ao lado)
anta vozes https://.../voz.onnx             # direto de uma URL
```

Há vozes PT-BR **fora** do repo oficial, em qualidade `high` (melhor que as `medium`
oficiais) — ex.: `pt_BR-miro-high` e `pt_BR-dii-high` em
`huggingface.co/csukuangfj/vits-piper-pt_BR-dii-high`. Confira a licença de cada repo antes
de usar; nem todos declaram uma (o `TarcisoAmorim/piper-pt_BR-miro-high`, por exemplo, é
CC BY-NC-SA — não comercial).

Para uma voz **sua**, o caminho é treinar/afinar com o Piper (`piper-train` + Piper Recording
Studio) e importar o `.onnx` resultante. Modelos de outros motores (Coqui, XTTS, Tortoise)
**não** funcionam sem conversão: o Piper carrega um VITS no formato dele.

## Notas e limitações

- **`anta toggle` não é pro Windows** — lá o próprio `run` captura a tecla. O `toggle` existe
  pro Wayland (Linux), onde apps não capturam teclas globais.
- **pandoc** só é necessário para exportar `docx`/`pdf` (`criar_documento`).
- **Notificações**: só `print` no terminal do daemon (toast nativo fica pra depois).
- **Caminho com espaços**: o autostart grava o interpretador **entre aspas**
  (`"C:\Users\Nome Sobrenome\...\python.exe" -m anta run`) — sem aspas quebraria.
- **macOS** não é suportado (o gating de VRAM assume NVIDIA).

## Checklist de validação (registrar bugs aqui)

1. `install.ps1` roda limpo: uv, winget (pandoc+Ollama), `.venv`, deps, `-e .`, TUI abre.
2. TUI: troca de **família** repovoa a tabela; modo vermelho é bloqueado; Instalar conclui.
3. `config.toml` + `prompts.toml` em `%APPDATA%\anta\`; Run-key com o interpretador aspado.
4. `anta run` sobe, fixa o LLM na VRAM, ouve `ctrl+alt+space`.
5. **Autostart**: fazer logoff/logon e confirmar que o daemon sobe sozinho
   (depende do pacote instalado com `-e .` e do `modes.yaml` resolvido pela raiz do repo).
6. Ações por voz: nota, documento (pandoc), abrir app da whitelist, pergunta (+voz se TTS).
7. RAG: criar uma nota e perguntar sobre ela na mesma sessão (o índice reconcilia no query).
