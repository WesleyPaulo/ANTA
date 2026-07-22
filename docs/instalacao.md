# Instalação — passo a passo

Guia específico por SO. A ANTA tem **duas formas de configurar** (produzem o mesmo
`config.toml`) e **três formas de rodar**:

| Configurar | Rodar |
|---|---|
| **GUI** `anta config` (janela; wizard) — *novo* | **HUD** `anta app` (janela na bandeja) — *novo* |
| **TUI** `anta` (terminal; validado) | **Headless** `anta run` (daemon, sem GUI) |

A **GUI** precisa do frontend buildado (Node) e de um backend WebKit (pywebview). Se não
quiser isso, use a **TUI** — é o caminho já validado e vem pronto no bootstrap.

> **Empacotado (sem Python/Node):** dá pra gerar um instalador `.exe`/AppImage — pule pra
> [seção "Executável empacotado"](#executável-empacotado-exe--appimage).

---

## Pré-requisitos

**Comuns:** `git`; **Ollama** (o bootstrap instala); **GPU NVIDIA** recomendada (o gate de
modo usa `nvidia-smi`; sem NVIDIA só o modo *Batata* fica liberado e o LLM roda na CPU).

**Só para a GUI:**
- **Node.js 20 LTS+** (build do front com Vite).
- **Linux:** backend WebKit do pywebview — ex. (Debian/Ubuntu):
  `sudo apt install python3-gi gir1.2-gtk-3.0 gir1.2-webkit2-4.1`. (Fedora:
  `python3-gobject gtk3 webkit2gtk4.1`. Varia por distro — ver docs do pywebview.)
- **Windows:** o WebView2 já vem no Windows 10/11 (nada a instalar).

---

## Linux — passo a passo

### 1. Clonar e rodar o bootstrap
```bash
git clone https://github.com/WesleyPaulo/ANTA.git
cd ANTA
./install.sh
```
O `install.sh` faz tudo do lado Python (não precisa rodar mais nada antes):
libs nativas (portaudio, libsndfile, pandoc, espeak-ng, build-essential) → **Ollama** →
`uv` → `.venv` (Python 3.12) → `pip install -r requirements.txt` → `pip install -e . --no-deps`
→ abre a **TUI**.

### 2. Configurar — escolha UM caminho

**2a. TUI (padrão, já abriu):** escolha **família** (Qwen3 recomendado) → um **modo**
verde/amarelo → **microfone** → marque TTS se quiser voz → **Instalar**. Ele baixa o LLM
(`ollama pull`), o Whisper, o embedder (RAG) e a voz (se TTS), e grava a config.

**2b. GUI (janela):** instale os pré-requisitos da GUI (acima), depois:
```bash
cd frontend && npm ci && npm run build && cd ..
anta config          # abre o Configurador (wizard: Modelo → Áudio → Ajustes → Instalar)
```
No fim do wizard, **Salvar e concluir** grava o `config.toml` (com `configured = true`).

> Ollama precisa estar **no ar** para o download do LLM. `ollama list` confirma; se não,
> inicie o serviço (`systemctl --user start ollama` ou `ollama serve`).

### 3. Rodar
```bash
anta app             # HUD na bandeja (janela) — precisa do front buildado
# ou
anta run             # daemon headless (sem GUI)
```
Fale com o atalho **`ctrl+alt+space`** (aperta, fala, aperta de novo).
- **X11:** o daemon captura a tecla sozinho (in-process).
- **Wayland/KDE:** vincule o atalho do SO ao comando `anta toggle` — ver [atalhos.md](atalhos.md).

### 4. Autostart (opcional)
O `setup_hotkey` (chamado ao salvar) cria `~/.config/autostart/anta.desktop` no X11. Para o
HUD subir no login, aponte o `Exec` desse `.desktop` para `anta app` (ou use o AppImage).

---

## Windows — passo a passo

Detalhes finos (PATH, autostart HKCU, cp1252) estão em [windows.md](windows.md). Fluxo curto:

### 1. Bootstrap (PowerShell, na pasta do repo)
```powershell
powershell -ExecutionPolicy Bypass -File .\install.ps1
```
Instala `uv`, via **winget** o **pandoc** + **Ollama**, recarrega o PATH, cria a `.venv`
(3.12), instala as deps + o pacote (`-e .`) e abre a **TUI**.

### 2. Configurar — escolha UM caminho

**2a. TUI (padrão):** igual ao Linux (família → modo → mic → TTS → Instalar). Grava
`%APPDATA%\anta\config.toml` e registra o autostart em `HKCU\...\Run`.

**2b. GUI (janela):**
```powershell
winget install OpenJS.NodeJS.LTS          # se ainda nao tiver Node
cd frontend; npm ci; npm run build; cd ..
anta config                               # abre o Configurador
```

### 3. Rodar
```powershell
.\.venv\Scripts\anta.exe app              # HUD (janela)
# ou
.\.venv\Scripts\anta.exe run              # daemon headless
```
Para digitar só `anta ...` de qualquer pasta, adicione `...\.venv\Scripts` ao PATH do
usuário (ver [windows.md](windows.md#digitar-só-anta-run-de-qualquer-pasta)). Atalho:
`ctrl+alt+space`, capturado in-process.

---

## Executável empacotado (.exe / AppImage)

Gera um **binário nativo** (sem exigir Python/Node do usuário final). Roda **uma vez em
cada SO**. Detalhes: [../packaging/README.md](../packaging/README.md).

```bash
# Linux
./packaging/build.sh --appimage      # -> dist/ANTA-x86_64.AppImage
# Windows
powershell -ExecutionPolicy Bypass -File packaging\build.ps1 -Inno   # -> dist\ANTA-Setup.exe
```
O exe é **um só**: sem argumento roteia por `configured` (1ª vez abre o Configurador; já
configurado sobe o HUD); com argumento age como CLI (`anta config`/`app`/`run`/`toggle`).

---

## Instalação para desenvolvimento

```bash
python -m venv .venv && . .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
pip install -e . --no-deps                        # `anta` roda de qualquer pasta

cd frontend && npm ci && npm run build && cd ..    # front (para a GUI)

# rodar
anta                 # TUI (fallback)      anta config   # Configurador GUI
anta app             # HUD                 anta run      # daemon headless
anta mic             # diagnostico de microfone

# testes
.venv/bin/python -m unittest discover -s tests     # backend
cd frontend && npm test                            # ponte (Vitest)
```
Desenvolvendo a UI com hot reload: `cd frontend && npm run dev` e, noutro terminal,
`ANTA_GUI_DEV=1 anta config` (aponta a janela pro dev server do Vite). Sem pywebview a UI
ainda roda no browser (usa dados de mock).

---

## Comandos

| Comando | O que faz |
|---|---|
| `anta` | Instalador **TUI** (terminal) — fallback headless |
| `anta config` | **Configurador GUI** (janela; único que escreve o config) |
| `anta app` | **App de execução** — HUD na bandeja (janela) |
| `anta run` | Daemon **headless** (push-to-talk, sem GUI) |
| `anta toggle` | Alterna a gravação do daemon (usado pelo atalho do SO no Wayland) |
| `anta mic` | Diagnóstico do microfone (device resolvido + nível do sinal) |
| `anta vozes` | Lista/instala vozes do TTS (Piper) |

## Onde ficam config e estado

`~/.config/anta/` (Linux) ou `%APPDATA%\anta\` (Windows):
`config.toml` (contrato entre as peças), `prompts.toml` (persona/regras editáveis),
`index/` (RAG), `embeddings/` (modelo do embedder), `voices/` (vozes do Piper),
`anta.pid` (daemon).

## Validação

Depois de instalar numa máquina real, rode a [validação nativa](validacao-nativa.md) —
o checklist cobre as janelas, o atalho por SO, o unload de VRAM e o empacotamento.
