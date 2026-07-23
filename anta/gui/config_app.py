"""Bootstrap da janela do Configurador (App A).

`anta config` -> abre uma janela PyWebview carregando o front do Vite (dev server
ou dist/ empacotado) e injeta a `ConfigApi` como `window.pywebview.api`.

Uma janela por vez (`SingleInstance`): o Configurador e o UNICO writer do config
(ver bridge_config), e duas janelas editando o mesmo TOML fazem a ultima a salvar
apagar a outra em silencio. A segunda tentativa traz a janela existente pra frente.
"""
from __future__ import annotations

import sys

from anta.gui import assets
from anta.gui.bridge_config import ConfigApi

_APP = "configurador"
_TITLE = "ANTA — Configurador"

# Tamanho pedido / minimo aceitavel. O pedido cabe o wizard inteiro sem rolagem em
# tela cheia HD; a `window_size` reduz ate caber na tela do usuario.
_PREFERIDO = (1180, 900)
_MINIMO = (880, 640)


def window_size(preferido=_PREFERIDO, minimo=_MINIMO, margem: float = 0.92):
    """(largura, altura) inicial que CABE na tela — nunca maior que ela.

    Pedir 1180x900 numa tela de 1366x768 abre uma janela mais alta que o monitor:
    o rodape (onde ficam Voltar/Avancar e o botao de salvar) nasce fora da area
    visivel. Aqui o pedido e cortado pela tela real e so entao pelo minimo, que
    e o piso abaixo do qual o layout quebra de qualquer jeito."""
    largura, altura = preferido
    try:
        import webview

        tela = webview.screens[0]
        largura = min(largura, int(tela.width * margem))
        altura = min(altura, int(tela.height * margem))
    except Exception:  # noqa: BLE001 - sem screens (backend/versao): fica o pedido
        pass
    return max(largura, minimo[0]), max(altura, minimo[1])


def main() -> None:
    from anta.gui.log import redirect_std_to_log

    redirect_std_to_log()  # app de janela: sem isso print/traceback crasham (stdout None)
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

    from anta.platform.singleton import SingleInstance

    trava = SingleInstance("config")
    if not trava.acquire():
        trava.signal_existing()
        print("[anta] o Configurador ja esta aberto — trouxe a janela pra frente.")
        sys.exit(0)

    api = ConfigApi()
    largura, altura = window_size()
    window = webview.create_window(
        _TITLE,
        url=assets.web_url(_APP),
        js_api=api,
        width=largura,
        height=altura,
        min_size=_MINIMO,
    )
    api.set_window(window)  # p/ empurrar progresso de download via evaluate_js
    trava.watch_focus(lambda: _mostrar(window))
    try:
        # debug=True (dev) liga o devtools/inspetor; no build fica limpo.
        webview.start(debug=assets.is_dev())
    finally:
        trava.release()


def _mostrar(window) -> None:
    """Traz a janela pra frente (outra instancia tentou abrir)."""
    for metodo in ("show", "restore"):
        try:
            getattr(window, metodo)()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    main()
