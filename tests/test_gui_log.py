import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from anta.gui import log


class TestLogPath(unittest.TestCase):
    def test_termina_em_anta_log(self):
        self.assertEqual(log.log_path().name, "anta.log")


class TestRedirect(unittest.TestCase):
    def test_noop_quando_ha_console(self):
        # dev/console: stdout e stderr existem -> nao mexe
        antes_out, antes_err = sys.stdout, sys.stderr
        log.redirect_std_to_log()
        self.assertIs(sys.stdout, antes_out)
        self.assertIs(sys.stderr, antes_err)

    def test_redireciona_quando_none(self):
        # app de janela: stderr=None -> vira um stream gravavel (nao crasha print/traceback)
        with TemporaryDirectory() as d:
            with mock.patch.object(log, "log_path", return_value=Path(d) / "anta.log"), \
                 mock.patch.object(sys, "stderr", None):
                log.redirect_std_to_log()
                self.assertIsNotNone(sys.stderr)
                sys.stderr.write("ok\n")  # nao pode crashar
                import traceback

                try:
                    raise RuntimeError("boom")
                except RuntimeError:
                    traceback.print_exc()  # tem que ir pro arquivo sem crashar
            # o mock.patch restaurou sys.stderr; o log deve conter o traceback
            conteudo = (Path(d) / "anta.log").read_text(encoding="utf-8")
        self.assertIn("boom", conteudo)


if __name__ == "__main__":
    unittest.main()
