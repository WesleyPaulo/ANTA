"""Testes do bootstrap do Configurador (anta.gui.config_app).

Foco no dimensionamento da janela: ela nasce grande o bastante para o wizard e,
ao mesmo tempo, NUNCA maior que a tela — senao o rodape (Voltar/Avancar/Salvar)
nasce fora da area visivel.
"""
import sys
import unittest
from unittest import mock

from anta.gui import config_app


def _fake_webview(largura, altura):
    fake = mock.MagicMock()
    fake.screens = [mock.Mock(width=largura, height=altura)]
    return mock.patch.dict(sys.modules, {"webview": fake})


class TestWindowSize(unittest.TestCase):
    def test_tela_grande_usa_o_preferido(self):
        with _fake_webview(2560, 1440):
            self.assertEqual(config_app.window_size(), config_app._PREFERIDO)

    def test_tela_pequena_corta_para_caber(self):
        with _fake_webview(1366, 768):
            largura, altura = config_app.window_size()
        self.assertLessEqual(largura, 1366)
        self.assertLessEqual(altura, 768)
        self.assertEqual(altura, int(768 * 0.90))  # sobra pra barra de tarefas

    def test_cabe_em_1080p_com_escala_de_125(self):
        """O caso comum do Windows: o WinForms re-escala a janela por DPI (96 ->
        120), entao a altura pedida vira altura*1.25 em pixels fisicos. E o mesmo
        clamp precisa valer tanto se `screens` reportar logico quanto fisico."""
        for tela in ((1536, 864), (1920, 1080)):  # leitura logica e fisica
            with _fake_webview(*tela):
                _l, altura = config_app.window_size()
            self.assertLessEqual(altura * 1.25, 1080, f"estourou em {tela}")

    def test_nunca_abaixo_do_minimo(self):
        # tela minuscula: o layout quebra abaixo do minimo de qualquer jeito, e uma
        # janela redimensionavel e melhor do que uma inutilizavel
        with _fake_webview(800, 480):
            self.assertEqual(config_app.window_size(), config_app._MINIMO)

    def test_sem_screens_cai_no_preferido(self):
        fake = mock.MagicMock()
        type(fake).screens = mock.PropertyMock(side_effect=RuntimeError("backend velho"))
        with mock.patch.dict(sys.modules, {"webview": fake}):
            self.assertEqual(config_app.window_size(), config_app._PREFERIDO)

    def test_preferido_cabe_o_wizard(self):
        # regressao: 1040x760 nao comportava o passo 'Modelo' inteiro (cards de
        # hardware + tabela de 6 modos) — a janela ja abria com rolagem
        self.assertGreaterEqual(config_app._PREFERIDO[1], 820)


class TestMostrar(unittest.TestCase):
    def test_show_e_restore(self):
        win = mock.MagicMock()
        config_app._mostrar(win)
        win.show.assert_called_once()
        win.restore.assert_called_once()

    def test_backend_sem_restore_nao_quebra(self):
        class _Velha:
            def __init__(self):
                self.mostrou = False

            def show(self):
                self.mostrou = True

        win = _Velha()
        config_app._mostrar(win)  # restore ausente -> engole
        self.assertTrue(win.mostrou)


if __name__ == "__main__":
    unittest.main()
