"""Frontend desktop do ANTA (PyWebview + Vue).

Duas pecas independentes que conversam so pelo config (single-writer):
  - Configurador (`anta config`): unico que ESCREVE o config. Substitui a TUI
    (que fica como fallback headless). Bridge: `bridge_config.ConfigApi`.
  - App de execucao (`anta app`, fase futura): residente, so LE o config.

Esta fase (fundacao) entrega so a casca do Configurador: uma janela que chama
metodos Python reais (`get_hardware`/`get_catalog`) via `window.pywebview.api`.

O onnxruntime/detecção rodam na CPU — a VRAM segue exclusiva do LLM (principio 1).
"""
