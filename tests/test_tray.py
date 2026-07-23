"""Testes da bandeja (anta.gui.tray) com um pystray FALSO.

A dev box nao tem system tray (nem pystray instalado): o teste injeta um modulo
falso via sys.modules, no mesmo padrao dos outros testes de I/O da suite.

O que importa aqui e o que o usuario relatou: a ANTA subia no login, ocupava
RAM/VRAM e nao aparecia em lugar nenhum. Entao a bandeja precisa (1) falhar
FALANDO quando nao da pra subir e (2) refletir o estado — icone e tooltip — em
vez de ficar um icone mudo.
"""
import sys
import unittest
from unittest import mock

from anta.gui import tray


class _FakeMenuItem:
    SEPARATOR = object()

    def __init__(self, text, action=None, **kw):
        self.text = text
        self.action = action
        self.kw = kw

    def rotulo(self):
        return self.text(self) if callable(self.text) else self.text


class _FakeMenu:
    SEPARATOR = _FakeMenuItem.SEPARATOR

    def __init__(self, *items):
        self.items = list(items)


class _FakeIcon:
    instancias: list["_FakeIcon"] = []

    def __init__(self, name, image, title, menu):
        self.name = name
        self.icon = image
        self.title = title
        self.menu = menu
        self.running = False
        self.stopped = False
        self.menu_updates = 0
        _FakeIcon.instancias.append(self)

    def run(self):
        self.running = True

    def stop(self):
        self.stopped = True

    def update_menu(self):
        self.menu_updates += 1


def _fake_pystray(icon_cls=_FakeIcon):
    mod = mock.MagicMock()
    mod.Icon = icon_cls
    mod.Menu = _FakeMenu
    mod.MenuItem = _FakeMenuItem
    return mock.patch.dict(sys.modules, {"pystray": mod})


class _FakeApi:
    def __init__(self):
        self.chamadas = []

    def show(self):
        self.chamadas.append("show")

    def hide(self):
        self.chamadas.append("hide")

    def toggle(self):
        self.chamadas.append("toggle")

    def load_model(self):
        self.chamadas.append("load")

    def unload_model(self):
        self.chamadas.append("unload")


class TestStart(unittest.TestCase):
    def setUp(self):
        _FakeIcon.instancias.clear()

    def test_sobe_e_para(self):
        t = tray.Tray(_FakeApi(), mock.MagicMock(), hotkey="ctrl+alt+space")
        with _fake_pystray():
            self.assertTrue(t.start())
        icon = _FakeIcon.instancias[-1]
        self.assertIn("ANTA", icon.title)
        t.stop()
        self.assertTrue(icon.stopped)

    def test_sem_pystray_devolve_false_e_LOGA(self):
        # regressao: antes era `return None` mudo — num app de janela isso e invisivel
        t = tray.Tray(_FakeApi(), mock.MagicMock())
        with mock.patch.dict(sys.modules, {"pystray": None}), \
             mock.patch.object(tray, "_log") as log:
            self.assertFalse(t.start())
        self.assertTrue(log.called)

    def test_falha_ao_criar_o_icone_e_reportada(self):
        class _Explode(_FakeIcon):
            def __init__(self, *a, **k):
                raise RuntimeError("sem system tray")

        t = tray.Tray(_FakeApi(), mock.MagicMock())
        with _fake_pystray(_Explode), mock.patch.object(tray, "_log") as log:
            self.assertFalse(t.start())
        self.assertIn("bandeja", log.call_args[0][0])

    def test_stop_sem_start_e_noop(self):
        tray.Tray(_FakeApi(), mock.MagicMock()).stop()  # nao levanta


class TestEstado(unittest.TestCase):
    def setUp(self):
        _FakeIcon.instancias.clear()
        self.api = _FakeApi()
        self.tray = tray.Tray(self.api, mock.MagicMock(), hotkey="ctrl+alt+space")
        with _fake_pystray():
            self.tray.start()
        self.icon = _FakeIcon.instancias[-1]

    def test_tooltip_e_cor_mudam_com_o_estado(self):
        antes = self.icon.icon
        self.tray.on_state({"state": "ouvindo"})
        self.assertIn("ouvindo", self.icon.title)
        self.assertIsNot(self.icon.icon, antes)  # repintou
        self.assertEqual(self.icon.menu_updates, 1)

    def test_pronto_mostra_o_atalho(self):
        self.tray.on_state({"state": "pronto"})
        self.assertIn("ctrl+alt+space", self.icon.title)

    def test_cores_distintas_por_estado(self):
        # o icone e a unica pista quando a janela esta escondida: dois estados nao
        # podem ficar da mesma cor
        cores = {tray._CORES[e] for e in ("pronto", "ouvindo", "respondendo", "descarregado")}
        self.assertEqual(len(cores), 4)

    def test_on_state_nunca_levanta(self):
        self.tray._icon = mock.MagicMock()
        type(self.tray._icon).icon = mock.PropertyMock(side_effect=RuntimeError("x"))
        self.tray.on_state({"state": "erro"})  # engole: nao derruba a transicao

    def test_sem_icone_ainda_guarda_o_estado(self):
        t = tray.Tray(self.api, mock.MagicMock())
        t.on_state({"state": "processando"})
        self.assertEqual(t._state, "processando")


class TestMenu(unittest.TestCase):
    def setUp(self):
        _FakeIcon.instancias.clear()
        self.api = _FakeApi()
        self.tray = tray.Tray(self.api, mock.MagicMock())
        with _fake_pystray():
            self.tray.start()
        self.itens = [i for i in _FakeIcon.instancias[-1].menu.items
                      if isinstance(i, _FakeMenuItem)]

    def _item(self, prefixo):
        for i in self.itens:
            if i.rotulo().lower().startswith(prefixo):
                return i
        self.fail(f"item nao encontrado: {prefixo}")

    def test_rotulo_de_memoria_inverte_quando_desalocado(self):
        self.assertTrue(any(i.rotulo() == "Desalocar memória" for i in self.itens))
        self.tray.on_state({"state": "descarregado"})
        self.assertTrue(any(i.rotulo() == "Carregar memória" for i in self.itens))

    def test_falar_vira_parar_durante_a_resposta(self):
        self.assertEqual(self._item("falar").rotulo(), "Falar")
        self.tray.on_state({"state": "respondendo"})
        self.assertEqual(self._item("parar").rotulo(), "Parar")

    def test_acoes_delegam_pra_api(self):
        self._item("mostrar").action()
        self._item("ocultar").action()
        self._item("falar").action()
        self._item("desalocar").action()
        self.assertEqual(self.api.chamadas, ["show", "hide", "toggle", "unload"])

    def test_memoria_carrega_quando_desalocado(self):
        self.tray.on_state({"state": "descarregado"})
        self._item("carregar").action()
        self.assertEqual(self.api.chamadas, ["load"])

    def test_sair_para_a_bandeja_e_destroi_a_janela(self):
        janela = self.tray._window
        self._item("sair").action()
        janela.destroy.assert_called_once()


if __name__ == "__main__":
    unittest.main()
