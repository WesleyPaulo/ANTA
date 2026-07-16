"""Regressao do streaming de subprocesso do instalador (o `ollama pull`).

Bug real, so-Windows: `subprocess.Popen(..., text=True)` sem `encoding` decodifica
pelo locale — cp1252 no Windows. O `ollama pull` escreve um spinner braille
(U+280F = b'\\xe2\\xa0\\x8f') mesmo num pipe, entao o decode levantava
UnicodeDecodeError NO MEIO do download: o worker do Textual morria e o instalador
seguia dizendo que estava tudo certo, com o LLM ausente. No Linux nunca reproduz
(locale UTF-8), por isso os bytes exatos do traceback viram teste aqui.
"""
import subprocess
import unittest
import unittest.mock

from anta.installer.app import InstallerApp, _log_lines

# Chunk exato que o ollama emitiu na maquina do usuario (do traceback).
_CHUNK_OLLAMA = b"\x1b[?2026h\x1b[?25l\x1b[1Gpulling manifest \xe2\xa0\x8f \x1b[K\x1b[?25h\x1b[?2026l"


class TestLogLines(unittest.TestCase):
    def test_tira_ansi_e_mantem_o_texto(self):
        self.assertEqual(_log_lines(_CHUNK_OLLAMA.decode("utf-8")), ["pulling manifest ⠏"])

    def test_quebra_no_carriage_return(self):
        # o progresso redesenha com \r e sem \n; sem quebrar aqui virava uma linha gigante
        self.assertEqual(_log_lines("a\rb\nc"), ["a", "b", "c"])

    def test_escapa_markup_do_rich(self):
        # RichLog(markup=True): colchetes vindos de fora nao podem virar tag
        self.assertEqual(_log_lines("[red]nao sou tag[/]"), [r"\[red]nao sou tag\[/]"])

    def test_ignora_linhas_vazias(self):
        self.assertEqual(_log_lines("\x1b[K\n  \n"), [])


class TestRunStreamDecode(unittest.TestCase):
    """O ponto do bug: os kwargs do Popen. Sem encoding explicito, o mesmo chunk
    quebra de novo em qualquer maquina com locale nao-UTF-8."""

    def _run(self, saida: bytes):
        app = InstallerApp.__new__(InstallerApp)  # sem event loop: so exercitamos _run_stream
        logado: list[str] = []
        app.call_from_thread = lambda fn, *a: logado.append(a[0] if a else "")
        app._log = lambda m: None

        capturado = {}
        real_popen = subprocess.Popen

        def fake_popen(argv, **kw):
            capturado.update(kw)
            # subprocesso de verdade cuspindo os bytes crus: exercita o decode real
            import sys
            return real_popen(
                [sys.executable, "-c",
                 f"import sys; sys.stdout.buffer.write({saida!r}); sys.stdout.buffer.write(b'\\n')"],
                **kw,
            )

        with unittest.mock.patch.object(subprocess, "Popen", fake_popen):
            code = app._run_stream(["ollama", "pull", "qwen3:4b"])
        return code, logado, capturado

    def test_spinner_utf8_nao_quebra_o_pull(self):
        code, logado, kw = self._run(_CHUNK_OLLAMA)
        self.assertEqual(code, 0)  # antes: UnicodeDecodeError matava o worker
        self.assertIn("pulling manifest", " ".join(logado))

    def test_popen_forca_utf8_e_nao_locale(self):
        _, _, kw = self._run(b"oi")
        self.assertEqual(kw.get("encoding"), "utf-8")
        self.assertEqual(kw.get("errors"), "replace")

    def test_bytes_invalidos_nao_derrubam(self):
        code, logado, _ = self._run(b"antes \xff\xfe depois")  # nem UTF-8 e
        self.assertEqual(code, 0)
        self.assertIn("antes", " ".join(logado))

    def test_progresso_repetido_nao_spama_o_log(self):
        _, logado, _ = self._run(b"pulling\rpulling\rpulling\rdone")
        self.assertEqual([l.strip() for l in logado], ["pulling", "done"])


if __name__ == "__main__":
    unittest.main()
