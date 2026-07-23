"""Icone de bandeja do App de execucao (pystray).

A ANTA e um app RESIDENTE: fica de pe com o Whisper na RAM e o LLM fixo na VRAM,
esperando o atalho. Um icone parado (ou nenhum) transforma isso num processo
fantasma comendo memoria — a bandeja e onde o app prova que esta vivo e diz o que
esta fazendo. Por isso o icone MUDA de cor e de tooltip a cada estado (assina a
`StateMachine` via `on_state`) e o menu muda de rotulo conforme o momento.

Best-effort: o pywebview nao tem tray nativa robusta. Se o pystray/Pillow faltarem
(ou nao houver system tray — comum no Wayland puro), `start()` devolve False e
LOGA o motivo no anta.log — antes era um `return None` mudo, o pior desfecho num
app sem console (o usuario ve "sumiu" e nao tem como saber por que). Roda no seu
proprio loop, em thread daemon.
"""
from __future__ import annotations

import sys
import threading

# Cor do icone por estado (mesma paleta do HUD: brand/vermelho/ambar/slate).
_CORES = {
    "carregando": (245, 158, 11),    # ambar — subindo os modelos
    "pronto": (28, 61, 110),         # brand-700 — ocioso, quente
    "ouvindo": (239, 68, 68),        # vermelho — gravando
    "processando": (59, 130, 246),   # azul — transcrevendo/decidindo
    "respondendo": (16, 185, 129),   # verde — executando/falando
    "descarregado": (100, 116, 139), # slate — memoria liberada
    "erro": (185, 28, 28),           # vermelho escuro
}
_ROTULOS = {
    "carregando": "carregando os modelos...",
    "pronto": "pronta",
    "ouvindo": "ouvindo",
    "processando": "processando",
    "respondendo": "respondendo",
    "descarregado": "memoria desalocada",
    "erro": "erro (veja o anta.log)",
}
_PARANDO = {"processando", "respondendo"}  # nesses o gatilho vira "parar"


def _log(msg: str) -> None:
    """Diagnostico da bandeja no anta.log (app de janela nao tem console)."""
    print(f"[anta][tray] {msg}", file=sys.stderr)


def _icon_image(state: str = "pronto"):
    """Icone 64x64: circulo na cor do estado com um 'A' branco no meio."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((2, 2, 62, 62), fill=_CORES.get(state, _CORES["pronto"]) + (255,))
    fonte = _fonte()
    if fonte is not None:
        d.text((32, 32), "A", fill=(255, 255, 255, 255), font=fonte, anchor="mm")
    else:  # sem fonte utilizavel: um ponto branco ainda distingue o icone
        d.ellipse((26, 26, 38, 38), fill=(255, 255, 255, 255))
    return img


def _fonte():
    """Fonte grande o suficiente para um icone de 64px. A `load_default()` antiga
    e um bitmap de ~11px: o 'A' saia como um borrao no canto. Pillow >= 10 aceita
    tamanho; em versoes antigas caimos no ponto branco."""
    try:
        from PIL import ImageFont

        return ImageFont.load_default(size=42)
    except Exception:  # noqa: BLE001 - Pillow < 10 (sem `size`) ou sem fonte
        return None


class Tray:
    """Icone da bandeja + menu, refletindo a maquina de estados.

    `api` e a `RuntimeApi` (mesmos metodos que o HUD chama — a bandeja nao tem um
    caminho proprio de execucao) e `window` e a janela pywebview.
    """

    def __init__(self, api, window, hotkey: str = "") -> None:
        self._api = api
        self._window = window
        self._hotkey = hotkey
        self._state = "carregando"
        self._icon = None
        # Sair de verdade (vs. o X, que so esconde quando ha bandeja). Lido pelo
        # handler de `closing` do runtime_app — sem isso o destroy() cairia no
        # mesmo handler, seria cancelado, e "Sair" nunca sairia.
        self.quitting = False

    # --- ciclo de vida ---
    def start(self) -> bool:
        """Sobe o icone numa thread daemon. False (com motivo no log) se nao der."""
        try:
            import pystray
        except Exception as e:  # noqa: BLE001 - dep opcional ausente
            _log(f"pystray indisponivel ({e.__class__.__name__}: {e}) — sem bandeja.")
            return False
        try:
            image = _icon_image(self._state)
        except Exception as e:  # noqa: BLE001 - sem Pillow / sem fonte
            _log(f"nao consegui desenhar o icone ({e.__class__.__name__}: {e}).")
            return False
        try:
            self._icon = pystray.Icon(
                "anta", image, self._title(), self._menu(pystray))
            threading.Thread(target=self._icon.run, daemon=True,
                             name="anta-tray").start()
        except Exception as e:  # noqa: BLE001 - sem system tray no ambiente
            _log(f"nao consegui subir a bandeja ({e.__class__.__name__}: {e}).")
            self._icon = None
            return False
        return True

    def stop(self) -> None:
        if self._icon is None:
            return
        try:
            self._icon.stop()
        except Exception:  # noqa: BLE001
            pass
        self._icon = None

    # --- ouvinte da StateMachine ---
    def on_state(self, event: dict) -> None:
        """Repinta icone + tooltip + rotulos do menu. Best-effort: nunca levanta
        (um ouvinte que estoura nao pode derrubar a transicao de estado)."""
        self._state = str(event.get("state") or self._state)
        if self._icon is None:
            return
        try:
            self._icon.icon = _icon_image(self._state)
            self._icon.title = self._title()
            self._icon.update_menu()
        except Exception:  # noqa: BLE001
            pass

    # --- textos ---
    def _title(self) -> str:
        """Tooltip: e a unica coisa que a bandeja consegue dizer sem clique."""
        rotulo = _ROTULOS.get(self._state, self._state)
        if self._state == "pronto" and self._hotkey:
            return f"ANTA — pronta ({self._hotkey})"
        return f"ANTA — {rotulo}"

    def _menu(self, pystray):
        desalocado = lambda: self._state == "descarregado"  # noqa: E731
        return pystray.Menu(
            pystray.MenuItem("Mostrar janela", self._show, default=True),
            pystray.MenuItem("Ocultar janela", self._hide),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem(
                lambda _i: "Parar" if self._state in _PARANDO else "Falar",
                self._falar, enabled=lambda _i: not desalocado()),
            pystray.MenuItem(
                lambda _i: "Carregar memoria" if desalocado() else "Desalocar memoria",
                self._memoria),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem("Sair", self._quit),
        )

    # --- acoes (delegam pra RuntimeApi; a bandeja nao tem logica propria) ---
    def _show(self, *_a) -> None:
        self._api.show()

    def _hide(self, *_a) -> None:
        self._api.hide()

    def _falar(self, *_a) -> None:
        self._api.toggle()  # request(): grava, ou PARA se ja estiver respondendo

    def _memoria(self, *_a) -> None:
        if self._state == "descarregado":
            self._api.load_model()
        else:
            self._api.unload_model()

    def _quit(self, *_a) -> None:
        self.quitting = True  # libera o `closing` a fechar de fato
        self.stop()
        try:
            self._window.destroy()
        except Exception:  # noqa: BLE001
            pass


def start_tray(api, window, hotkey: str = ""):
    """Compat: sobe a bandeja e devolve o `Tray` (ou None). Prefira `Tray` direto."""
    tray = Tray(api, window, hotkey=hotkey)
    return tray if tray.start() else None
