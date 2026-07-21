# Guia de Criação do Frontend — Assistente de IA Local

> Documento de referência para implementação (você + Claude Code).
> Escopo: **frontend das duas peças** e as costuras com o backend Python.
> Não cobre a lógica de IA em si (modelo, STT, TTS) nem a detecção de hardware — que **já existem**.

---

## 1. Visão geral

Assistente de IA **totalmente local e offline**, com processamento pesado embutido, rodando **igual em Windows e Linux** (instaladores diferentes por SO).

O produto são **duas peças independentes** que se comunicam **apenas por um arquivo de config**:

| Peça | Papel | Relação com o config |
|------|-------|----------------------|
| **Configurador** | Baixa/define modelo, STT, TTS, atalhos e áudio. É também a tela de configurações permanente. | **Único que escreve** |
| **App de execução** | Residente na memória. Carrega o modelo, escuta atalho, processa e responde por texto + áudio. | **Só lê** |

Regra de ouro: **um escritor só**. O app de execução nunca escreve no config → sem corrupção, sem condição de corrida.

---

## 2. Stack definida

- **Frontend:** Vue 3 + Tailwind + Vite (build estático) — mesma stack nas duas peças.
- **Shell/janela:** PyWebview (janela nativa carregando o `dist` do Vite).
- **Backend:** Python puro (mesmo processo; sem sidecar, sem IPC entre linguagens).
- **Empacotamento:** PyInstaller (rodar uma vez em cada SO) + instalador nativo por SO.

Por que PyWebview e não Tauri: o app é **pesado e local**, o modelo precisa viver no **mesmo processo Python** que o carregou (load/unload/VRAM), e a detecção já é Python. PyWebview mantém tudo num processo só e preserva a DX de Vue+Tailwind. Tauri exigiria Python como sidecar + IPC nos dois lados — custo alto justo no caminho quente.

---

## 3. A ponte PyWebview ↔ Vue (a única costura de verdade)

- No lugar de `fetch`/`axios`, o front chama métodos Python expostos: `window.pywebview.api.minhaFuncao(args)` → retorna **Promise**.
- Exponha uma **classe API em Python** com os métodos que o front precisa; nada de HTTP local.
- **Dev vs build:** aponte o PyWebview para o servidor do Vite (`http://localhost:5173`) em desenvolvimento (hot reload) e para o `dist/` no build. Controle por **variável de ambiente**.
- **vue-router:** use `createWebHashHistory` ou `memory history`. Como a página carrega via `file://`, o history mode normal **quebra**.
- **Assets:** garanta `base: './'` no `vite.config` para caminhos relativos funcionarem sob `file://`.
- Trate toda chamada à API como **assíncrona e falível** (o Python pode demorar ou lançar erro) — nada de travar a UI.

---

## 4. Peça 1 — Configurador

Pense nele **de trás pra frente**: o objetivo é produzir um **config válido e completo** que o app de execução consiga consumir. Se faltar um campo, o runtime quebra.

### Blocos lógicos
1. **Detecção da máquina** — *já existe*. Frontend só **consome** o resultado (GPU/RAM/VRAM/disco) pra filtrar o catálogo.
2. **Catálogo de componentes** — LLM, STT e TTS são **a mesma abstração 3×**: `catálogo → escolha → download → verificação → registra caminho no config`. Modele um componente genérico e reuse.
3. **Download resiliente e idempotente** — progresso visível, checksum de integridade, **retomar** se cair, **não rebaixar** o que já existe. Re-executar nunca pode estragar o que já funciona.
4. **Atalhos** — captura de hotkey *já existe*; aqui o front só deixa **definir** a tecla, detecta conflito e grava.
5. **Áudio e comportamento** — microfone de entrada, saída, voz do TTS, idioma, device do modelo (CPU/GPU).
6. **Teste antes de "pronto"** — validar mic captando, TTS falando e modelo carregando **durante o setup**. Só marca como configurado se passar. (Mata metade da dor de "não ouviu, verifique o microfone" no runtime.)
7. **Persistência** — escreve o config com **versão de schema**.

### Dois modos, mesma lógica
- **Primeira vez:** wizard passo a passo (sequencial).
- **Depois:** painel de abas (edita direto o que quiser).

---

## 5. Peça 2 — App de execução

Residente. Fica na **bandeja do sistema** (tray), não em terminal. A janela/HUD aparece sob demanda.

### Máquina de estados (dirige as animações)
```
inicia → carregando modelo → pronto → ouvindo → processando → respondendo → pronto
                                 ↑                                              │
                                 └──────────────────────────────────────────────┘
```
Detalhado:
1. **Inicia** → **carregando modelo** (animação "carregando").
2. **Pronto** — "aperte o botão / atalho para falar".
3. **Ouvindo** — "aperte para parar".
4. **Processando**.
5. **Resultado:**
   - ouviu → **responde por texto + áudio** → volta a *pronto*.
   - não ouviu → pede pra **escolher/verificar o microfone**.
6. **Descarregar modelo da memória** — controle explícito (libera RAM/VRAM). Estado "modelo descarregado" ≠ "app fechado".

### Frontend
- Cada estado = uma **animação/visual** (CSS resolve pulso de "escutando", etc.).
- O front reage a **eventos vindos do Python** (mudou de estado) — a máquina de estados de verdade vive no backend; o Vue só **reflete**.

---

## 6. O config (contrato entre as peças)

Campos mínimos que o runtime lê (ajuste conforme sua lógica):
- Versão de schema
- Caminhos: modelo LLM, STT, TTS
- Atalhos: falar, parar (e o que mais existir)
- Áudio: device de entrada, device de saída, voz do TTS, idioma
- Device do modelo: CPU/GPU

**Onde guardar (cross-platform):** uma função só resolve o caminho —
- Windows: `%APPDATA%`
- Linux: `~/.config`

**Flag de "configurado":** o runtime precisa saber se o setup foi concluído (existência + validade do config, ou flag explícita).

---

## 7. Coisas pra ficar atento (pegadinhas)

- [ ] **Caminhos cross-platform** centralizados numa função única (`%APPDATA%` vs `~/.config`); nunca hardcode.
- [ ] **vue-router em hash/memory history** (senão quebra sob `file://`).
- [ ] **Toggle dev/build** do PyWebview (Vite server vs `dist`) por env var.
- [ ] **`base: './'`** no Vite pra assets relativos.
- [ ] **Bundle do `dist` no PyInstaller** — o build do Vue precisa entrar no pacote (ajustar `datas`/spec).
- [ ] **Hotkeys no Linux:** X11 funciona liso; **Wayland restringe** captura global (pode exigir portal/config extra). Testar nas duas máquinas cedo.
- [ ] **Unload de modelo** de verdade liberando VRAM (GPU costuma segurar memória se malfeito).
- [ ] **Downloads grandes** (GB): não embutir no instalador — baixar no setup, com retomada e checksum.
- [ ] **Single writer no config** — só o configurador escreve.
- [ ] **Chamadas à API async** — nunca travar a UI esperando Python.
- [ ] **Erros com direção** — mensagem diz o que fazer (ex.: "verifique o microfone"), não só "erro".

---

## 8. Empacotamento (contexto pro frontend)

- **PyInstaller** rodado **uma vez em cada SO** → binário nativo por sistema (mesmo código-fonte).
- **Instaladores:** Windows via Inno Setup/NSIS (opção "run after install"); Linux via `.deb`/`.rpm` ou **AppImage**.
- **Autostart** (assistente sempre pronto): registro de inicialização no Windows; serviço de usuário systemd ou `.desktop` no autostart do Linux — o instalador configura.

---

## 9. Checklist de implementação

### Base compartilhada
- [ ] Projeto Vite + Vue 3 + Tailwind configurado (`base: './'`, router em hash/memory).
- [ ] Módulo Python de **caminhos cross-platform** e leitura/escrita do config (com versão de schema).
- [ ] Classe **API PyWebview** (métodos expostos ao front) + toggle dev/build.

### Configurador
- [ ] Consumir resultado da detecção (já existe) e filtrar catálogo.
- [ ] Componente genérico "item baixável" reusado pra LLM/STT/TTS.
- [ ] Download com progresso, checksum e retomada.
- [ ] Tela de atalhos (definir + detectar conflito).
- [ ] Tela de áudio/comportamento.
- [ ] Rotina de **teste antes de pronto** (mic, TTS, load do modelo).
- [ ] Fluxo wizard (1ª vez) + modo painel (depois).
- [ ] Escrita do config + flag de configurado.

### App de execução
- [ ] Ícone e menu na bandeja (tray).
- [ ] Máquina de estados no backend + eventos pro front.
- [ ] HUD com animação por estado (carregando/pronto/ouvindo/processando/respondendo).
- [ ] Integrar hotkey existente aos estados.
- [ ] Resposta por texto + áudio.
- [ ] Botão de **descarregar modelo da memória** (liberar VRAM/RAM).
- [ ] Fluxo de "não ouviu → verificar microfone".

### Divisão sugerida
- **Você:** lógica de IA já pronta (modelo/STT/TTS), detecção, integração da hotkey, decisões de UX.
- **Claude Code:** scaffolding Vite/Vue, ponte PyWebview, componentes de UI, máquina de estados no backend, spec do PyInstaller, scripts de instalador.
