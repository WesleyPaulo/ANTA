"""Bootstrap da janela do Configurador (App A).

`anta config` -> abre uma janela PyWebview carregando o front do Vite (dev server
ou dist/ empacotado) e injeta a `ConfigApi` como `window.pywebview.api`.
"""
from __future__ import annotations

import sys

from anta.gui import assets
from anta.gui.bridge_config import ConfigApi

_APP = "configurador"
_TITLE = "ANTA — Configurador"


def main() -> None:
    # Erro com direcao (guia §7) em vez de janela em branco: dist ausente fora do dev.
    if assets.build_missing(_APP):
        idx = assets.dist_index(_APP)
        print(
            f"[anta] frontend nao buildado (nao achei {idx}).\n"
            f"       Rode:  cd frontend && npm install && npm run build\n"
            f"       Ou, em desenvolvimento:  ANTA_GUI_DEV=1 anta config  "
            f"(com 'npm run dev' rodando).",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        import webview  # dep nova (pywebview); import preguicoso
    except ImportError:
        print(
            "[anta] falta a dependencia 'pywebview'. Instale com:\n"
            "       pip install pywebview   (ou:  pip install -r requirements.txt)",
            file=sys.stderr,
        )
        sys.exit(1)

    api = ConfigApi()
    window = webview.create_window(
        _TITLE,
        url=assets.web_url(_APP),
        js_api=api,
        width=1040,
        height=760,
        min_size=(880, 640),
    )
    api.set_window(window)  # p/ empurrar progresso de download via evaluate_js
    # debug=True (dev) liga o devtools/inspetor; no build fica limpo.
    webview.start(debug=assets.is_dev())


if __name__ == "__main__":
    main()
