# Frontend do ANTA

Monorepo npm (workspaces) das duas apps desktop, servidas em janelas **PyWebview**
pelo mesmo processo Python. Fase atual: **fundação (walking skeleton)** — só a casca
do Configurador, provando a costura PyWebview ↔ Vue ↔ dev/build ↔ chamada-Python.

## Estrutura

```
packages/
  bridge/    @anta/bridge  — a ponte: callApi() sobre window.pywebview.api (+ mock p/ browser)
  ui/        @anta/ui      — componentes compartilhados (StatusPill) + preset Tailwind
apps/
  configurador/ @anta/configurador — App A (Vue 3 + Vite + Tailwind, router em hash)
```

## Comandos

```bash
npm install            # na pasta frontend/ (instala o workspace todo)
npm run build          # gera apps/configurador/dist (o que a janela carrega no build)
npm test               # testes do bridge (Vitest)
npm run dev            # dev server do Vite em http://localhost:5173 (hot reload)
```

## Abrir a janela (precisa do Python)

- **Dev (hot reload):** com `npm run dev` rodando, noutro terminal
  `ANTA_GUI_DEV=1 anta config` — a janela aponta pro dev server.
- **Build (`file://`):** após `npm run build`, `anta config` (sem env) carrega o `dist/`.

> Num browser puro (sem pywebview) a UI ainda roda: o `@anta/bridge` cai num **mock**
> com dados de exemplo, então dá pra desenvolver a UI sem subir o Python.

Regras que não podem quebrar (guia do frontend): `base: './'` no Vite e router em
`createWebHashHistory()` — o history normal quebra sob `file://`.
