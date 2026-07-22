"""Icone de bandeja do App de execucao (pystray).

Best-effort: o pywebview nao tem tray nativa robusta. Se o pystray/Pillow faltarem
(ou nao houver system tray — comum no Wayland puro), retorna None e o app segue so
com a janela. Roda no seu proprio loop, em thread daemon.
"""
from __future__ import annotations

import threading


def _icon_image():
    """Um icone simples 64x64 (circulo azul-escuro com 'A'). Best-effort."""
    from PIL import Image, ImageDraw

    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.ellipse((4, 4, 60, 60), fill=(28, 61, 110, 255))  # brand-700 (#1c3d6e)
    d.text((24, 20), "A", fill=(255, 255, 255, 255))
    return img


def start_tray(api, window):
    """Sobe o icone da bandeja numa thread daemon. Retorna o icon (p/ .stop()) ou None."""
    try:
        import pystray
    except Exception:  # noqa: BLE001 - dep opcional / sem tray no ambiente
        return None
    try:
        image = _icon_image()
    except Exception:  # noqa: BLE001 - sem Pillow
        return None

    menu = pystray.Menu(
        pystray.MenuItem("Mostrar", lambda icon, item: api.show()),
        pystray.MenuItem("Falar / parar", lambda icon, item: api.toggle()),
        pystray.MenuItem("Descarregar modelo", lambda icon, item: api.unload_model()),
        pystray.MenuItem("Sair", lambda icon, item: _quit(icon, window)),
    )
    try:
        icon = pystray.Icon("anta", image, "ANTA", menu)
        threading.Thread(target=icon.run, daemon=True).start()
        return icon
    except Exception:  # noqa: BLE001
        return None


def _quit(icon, window) -> None:
    try:
        icon.stop()
    except Exception:  # noqa: BLE001
        pass
    try:
        window.destroy()
    except Exception:  # noqa: BLE001
        pass
