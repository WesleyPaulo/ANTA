"""Testes da trava de instancia unica (anta.platform.singleton).

Duas ANTAs ao mesmo tempo = dois Whispers na RAM, dois preloads na VRAM e dois
`pynput` no mesmo atalho. A trava e do SO (flock/msvcrt), nao um pidfile: um
processo morto no tapa nao deixa trava velha para tras.
"""
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from anta.platform import singleton
from anta.platform.singleton import SingleInstance


class _Base(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._patch = mock.patch.object(singleton, "_dir",
                                        return_value=Path(self._tmp.name))
        self._patch.start()
        self.addCleanup(self._patch.stop)
        self.addCleanup(self._tmp.cleanup)


class TestTrava(_Base):
    def test_primeira_pega_segunda_nao(self):
        a, b = SingleInstance("runtime"), SingleInstance("runtime")
        self.assertTrue(a.acquire())
        self.addCleanup(a.release)
        self.assertFalse(b.acquire())

    def test_release_libera_para_a_proxima(self):
        a = SingleInstance("runtime")
        self.assertTrue(a.acquire())
        a.release()
        b = SingleInstance("runtime")
        self.assertTrue(b.acquire())
        b.release()

    def test_nomes_diferentes_nao_se_atrapalham(self):
        # o Configurador pode abrir com o HUD rodando (travas separadas)
        hud, cfg = SingleInstance("runtime"), SingleInstance("config")
        self.assertTrue(hud.acquire())
        self.addCleanup(hud.release)
        self.assertTrue(cfg.acquire())
        self.addCleanup(cfg.release)

    def test_arquivo_orfao_nao_bloqueia(self):
        # o pidfile mentia quando o processo morria no tapa; o lock do SO nao
        (Path(self._tmp.name) / "runtime.lock").write_text("999999", encoding="utf-8")
        t = SingleInstance("runtime")
        self.assertTrue(t.acquire())
        t.release()

    def test_grava_o_pid_para_diagnostico(self):
        import os

        t = SingleInstance("runtime")
        t.acquire()
        self.addCleanup(t.release)
        self.assertEqual(t.lock_path.read_text(encoding="utf-8").strip(), str(os.getpid()))

    def test_sem_permissao_nao_impede_o_app_de_abrir(self):
        # a trava e uma comodidade; falhar nela nao pode virar "a ANTA nao abre"
        with mock.patch("builtins.open", side_effect=OSError("somente leitura")):
            self.assertTrue(SingleInstance("runtime").acquire())

    def test_release_sem_acquire_e_noop(self):
        SingleInstance("runtime").release()  # nao levanta


class TestFoco(_Base):
    def test_pedido_e_consumido_uma_vez(self):
        t = SingleInstance("runtime")
        self.assertFalse(t.consume_focus())
        SingleInstance("runtime").signal_existing()  # a 2a instancia pede foco
        self.assertTrue(t.consume_focus())
        self.assertFalse(t.consume_focus())  # consumido: nao repete

    def test_watch_chama_o_callback(self):
        import threading

        t = SingleInstance("runtime")
        chamou = threading.Event()
        with mock.patch.object(singleton, "_sleep", lambda _s: None):
            t.watch_focus(chamou.set)
            SingleInstance("runtime").signal_existing()
            self.assertTrue(chamou.wait(2))

    def test_watch_limpa_pedido_velho(self):
        # sentinela esquecida de uma sessao anterior nao pode "mostrar a janela"
        # sozinha no boot seguinte
        t = SingleInstance("runtime")
        t.signal_existing()
        with mock.patch.object(singleton, "_sleep", lambda _s: None), \
             mock.patch.object(SingleInstance, "consume_focus", return_value=False):
            t.watch_focus(lambda: None)
        self.assertFalse(t.focus_path.exists())


if __name__ == "__main__":
    unittest.main()
