# Checklist de validação nativa (frontend desktop)

O que **não deu** para validar na dev box (WSL2 sem display/GPU/pywebview) e precisa de
uma máquina **Windows ou Linux nativa**. Marque cada item; anote o número/erro exato
quando algo falhar (as falhas só-Windows costumam ser **silenciosas** — peça o dado antes
de teorizar). Contexto de build: [../packaging/README.md](../packaging/README.md);
fases: [frontend-fases.md](frontend-fases.md).

## ✅ Status — Windows FUNCIONAL de ponta a ponta (v0.4.3, 2026-07-22)

Validado em hardware real (Windows), na iteração v0.4.0 → v0.4.3:
- ✅ **Instalar** (`ANTA-Setup.exe`) + SmartScreen ("Executar assim mesmo")
- ✅ **Configurador**: detecção real (VRAM/RAM/disco), catálogo, downloads dos componentes,
  detecção do Ollama, salvar config
- ✅ **HUD**: máquina de estados, **atalho global + botão** gravam, transcrição correta,
  **resposta exibida na tela**, **TTS falando**
- ✅ **Descarregar modelo** (libera VRAM de fato)
- ✅ **Log** em `%APPDATA%\anta\anta.log` (app de janela não tem console)

Bugs corrigidos na iteração: instalador em `winget` sem Node (build via CI), devices
duplicados (WASAPI), badge "mock" falso, layout da revisão, versão, **crash sem-console**
(travava em "Processando"), **resposta não aparecia no HUD**, **TTS mudo** (voz por nome
não resolvia). Todos com testes.

### Polimento (próximas sessões)
- [ ] **Assinatura de código** — some com o SmartScreen e evita o Kaspersky re-perguntar a
  cada build (EV = imediato; OV/Azure Trusted Signing/SignPath = alternativas).
- [ ] **Linux nativo** (AppImage) — backend Qt do pywebview; validar abertura + áudio.
- [ ] **macOS** — não suportado hoje (gate de VRAM assume NVIDIA).
- [ ] **Polimento visual fino** — calibrar tamanhos/animações com as janelas abertas.

## 🔁 Rodada v0.4.4 — presença + parar (a validar no Windows)

Reportado na validação anterior: **a ANTA subia com o PC, ocupava RAM/VRAM e não
aparecia em lugar nenhum** (nem janela, nem bandeja). Causa: o autostart apontava para
`anta run` (headless). Também: o botão continuava "Falar" enquanto o TTS falava.

- [ ] **Autostart abre o HUD:** reiniciar → a **janela** aparece e o **ícone da bandeja**
      também. Conferir o valor em `HKCU\...\Run`: tem que terminar em `" app`.
- [ ] **Migração automática:** numa máquina com o autostart antigo, rodar `anta run` uma vez
      → avisa que corrigiu a entrada; no próximo login sobe o HUD.
- [ ] **Bandeja fala:** o ícone **muda de cor** por estado (azul pronto / vermelho ouvindo /
      verde respondendo / cinza desalocado) e o tooltip diz o estado. Menu: Mostrar / Ocultar /
      Falar↔Parar / Desalocar↔Carregar memória / Sair.
- [ ] **X esconde, Sair encerra:** fechar a janela some com ela mas o ícone fica (e o atalho
      continua funcionando); "Sair" do menu encerra o processo de verdade.
- [ ] **Sem bandeja (Wayland puro):** o app segue só com a janela e o X volta a encerrar —
      anotar o motivo logado em `anta.log` (`[anta][tray] ...`).
- [ ] **Botão Parar:** com TTS ligado, falar algo longo → durante a fala o botão fica
      **vermelho "Parar"**; clicar **corta o áudio na hora** e volta a "Pronto". Nada de
      gravação começando sozinha depois.
- [ ] **Parar antes do efeito:** pedir "cria uma nota sobre X" e apertar Parar durante
      "Processando" → a nota **não** é criada.
- [ ] **Atalho global também para:** apertar `ctrl+alt+space` enquanto responde interrompe
      (em vez de enfileirar uma gravação).
- [ ] **Desalocar memória:** o botão libera VRAM (`nvidia-smi`) **e pausa a ANTA** — apertar
      o atalho depois não grava, só avisa. "Carregar memória" volta a "Pronto".
- [ ] **Medidor:** a linha `VRAM x/y GB · RAM z GB` aparece e **cai** depois de desalocar.

---

## 0. Preparação
- [ ] `git pull` (a fase está na `main`).
- [ ] Ollama instalado e no ar (`ollama --version`, `ollama list`).
- [ ] `python -m venv .venv` + `pip install -r requirements.txt` (traz pywebview, psutil,
      pystray, Pillow, faster-whisper, piper, fastembed, sounddevice, pynput…).
- [ ] `pip install -e . --no-deps` (para `anta ...` resolver o pacote de qualquer CWD).
- [ ] `cd frontend && npm ci && npm run build` (gera os dois `dist/`).
- [ ] Testes verdes: `.venv/bin/python -m unittest discover -s tests` + `cd frontend && npm test`.

## 1. Configurador — `anta config`
- [ ] A **janela abre** (dev: `ANTA_GUI_DEV=1 anta config` com `npm run dev`; build: `anta config`).
- [ ] **Detecção real:** VRAM/RAM/disco batem com a máquina (RAM via psutil; VRAM só com NVIDIA).
- [ ] **Catálogo:** o gate de cor (verde/amarelo/vermelho) condiz com a VRAM; troca de família repovoa.
- [ ] **Download com progresso:** baixar o LLM do modo mostra a barra andando (`ollama pull`);
      re-baixar não estraga (idempotente); STT/embedding/voz idem.
- [ ] **Testar microfone:** o nível (pico/rms) responde à fala; mudo → aviso claro.
- [ ] **Testar voz (TTS):** com TTS ligado, "Testar voz" fala pela saída escolhida.
- [ ] **Atalho:** "Gravar atalho" captura a combinação; validação rejeita sem modificador.
- [ ] **Salvar:** grava `config.toml` com `configured = true` (ver `%APPDATA%\anta` / `~/.config/anta`);
      cria `prompts.toml`; chama o autostart/atalho do SO.
- [ ] **Modo edição:** reabrir com config já salva → passos viram abas livres; salva alterações.
- [ ] **Paleta:** preto/branco + azul escuro renderiza bem no claro **e** no escuro do SO.

## 2. App de execução — `anta app`
- [ ] **Bandeja:** ícone aparece (pystray) e **muda de cor/tooltip** com o estado; menu
      Mostrar/Ocultar/Falar↔Parar/Desalocar↔Carregar/Sair funciona.
      (No **Wayland puro** pode não haver tray — o app segue só com a janela; o motivo fica
      logado como `[anta][tray] ...` no `anta.log`; anotar.)
- [ ] **Máquina de estados anima:** carregando → pronto → (atalho) ouvindo → processando →
      respondendo → pronto. O orb muda por estado (ping/spin/pulse).
- [ ] **Atalho global dispara o ciclo:**
  - [ ] **X11 / Windows:** in-process (pynput) — apertar o atalho grava/encerra.
  - [ ] **Wayland/KDE:** vincular o atalho do SO a `anta toggle` (ver `docs/atalhos.md`); dispara via SIGUSR1.
  - [ ] **Botão Falar/Parar** do HUD faz o mesmo (converge no mesmo gatilho).
- [ ] **Resposta:** texto aparece no HUD e (se TTS) sai por áudio.
- [ ] **Desalocar memória:** o botão libera VRAM — confirmar com `nvidia-smi` (a memória do LLM cai);
      estado vira "memória desalocada" e o **atalho para de gravar**; **Carregar memória** volta a "pronto".
- [ ] **"Não ouviu":** falar em silêncio → estado erro (code=mic) → botão **Abrir Configurador**
      abre o Configurador (o runtime nunca escreve o config).
- [ ] **`anta run` intacto:** o daemon headless antigo funciona igual (sem GUI).

## 3. Empacotamento
- [ ] **Build gera o exe:** `packaging/build.sh` (Linux) / `packaging/build.ps1` (Windows) → `dist/anta/anta`.
      Anotar quaisquer `ModuleNotFoundError` no 1º run (ajustar `hiddenimports` no `anta.spec`).
- [ ] **Launcher roteia:** exe **sem argumento** → 1ª vez abre o Configurador; com config salva → HUD.
- [ ] **Exe como CLI:** `anta config` / `anta app` / `anta run` / `anta toggle` funcionam a partir do exe.
- [ ] **Caminhos frozen:** `modes.yaml` e os dois `web/` carregam (resolvidos por `sys._MEIPASS`).
- [ ] **Instalador:**
  - [ ] **Windows:** `build.ps1 -Inno` → `ANTA-Setup.exe`; instala, "run after install" abre o Configurador,
        autostart (HKCU\Run) sobe o HUD no login.
  - [ ] **Linux:** `build.sh --appimage` → `ANTA-x86_64.AppImage` roda; `.desktop` no autostart sobe o HUD.

## Armadilhas a vigiar (histórico)
- **Windows = falha silenciosa.** Se algo "não faz nada", capture stdout/erro — não teorize sem o dado.
- **cp1252 no `ollama pull`:** o streaming já força UTF-8; conferir que o progresso não quebra.
- **Ollama ignora campo desconhecido:** raciocínio fica desligado via `reasoning_effort:'none'` — se o
  roteamento (decide) degradar, é sinal de thinking ligado.
- **Wayland restringe atalho global:** o caminho `anta toggle` é o robusto, não um plano B.
- **VRAM sem NVIDIA = 0.0:** em AMD/Intel/CPU o catálogo fica todo vermelho (esperado).
