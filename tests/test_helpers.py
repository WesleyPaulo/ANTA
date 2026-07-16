"""Helpers do resumo de atividade: janelas de tempo e coleta do que o usuario produziu."""
import os
import tempfile
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from anta.actions import helpers


def _age(path: Path, days: float) -> None:
    """Envelhece o mtime de um arquivo em `days` dias (para simular atividade antiga)."""
    t = (datetime.now() - timedelta(days=days)).timestamp()
    os.utime(path, (t, t))


class TestWindowStart(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 7, 15, 14, 30, 0)

    def test_dia_e_meia_noite_de_hoje(self):
        self.assertEqual(helpers.window_start("dia", self.now),
                         datetime(2026, 7, 15, 0, 0, 0))

    def test_semana_sete_dias(self):
        self.assertEqual(helpers.window_start("semana", self.now),
                         self.now - timedelta(days=7))

    def test_mes_trinta_dias(self):
        self.assertEqual(helpers.window_start("mes", self.now),
                         self.now - timedelta(days=30))


class TestGatherActivity(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.vault = Path(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_pega_notas_recentes_ignora_antigas(self):
        (self.vault / "hoje.md").write_text("# Hoje\n\nescrevi isto agora", encoding="utf-8")
        antiga = self.vault / "antiga.md"
        antiga.write_text("# Antiga\n\ncoisa velha", encoding="utf-8")
        _age(antiga, 40)
        since = helpers.window_start("semana", datetime.now())
        out = helpers.gather_activity(self.vault, since)
        self.assertIn("escrevi isto agora", out)
        self.assertNotIn("coisa velha", out)

    def test_inclui_memoria_e_ignora_resumos(self):
        (self.vault / "memoria").mkdir()
        (self.vault / "memoria" / "m.md").write_text("# Memoria\n\nprefere docx", encoding="utf-8")
        (self.vault / "resumos").mkdir()
        (self.vault / "resumos" / "r.md").write_text("# Resumo\n\nresumo anterior", encoding="utf-8")
        since = helpers.window_start("dia", datetime.now())
        out = helpers.gather_activity(self.vault, since)
        self.assertIn("prefere docx", out)
        self.assertNotIn("resumo anterior", out)  # nao resume resumos

    def test_tarefas_por_timestamp_da_linha(self):
        hoje = datetime.now().strftime("%Y-%m-%d %H:%M")
        (self.vault / "tarefas.md").write_text(
            f"- [ ] comprar cafe  <!-- {hoje} -->\n"
            "- [ ] tarefa velha  <!-- 2020-01-01 09:00 -->\n", encoding="utf-8")
        since = helpers.window_start("semana", datetime.now())
        out = helpers.gather_activity(self.vault, since)
        self.assertIn("comprar cafe", out)
        self.assertNotIn("tarefa velha", out)

    def test_vazio_quando_nada_recente(self):
        antiga = self.vault / "x.md"
        antiga.write_text("velho", encoding="utf-8")
        _age(antiga, 100)
        out = helpers.gather_activity(self.vault, helpers.window_start("mes", datetime.now()))
        self.assertEqual(out, "")


class TestWriteSummaryNote(unittest.TestCase):
    def test_salva_em_resumos(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d)
            now = datetime(2026, 7, 15, 10, 0, 0)
            path = helpers.write_summary_note(vault, "semana", now, "fiz X e Y")
            self.assertEqual(path.parent.name, "resumos")
            self.assertIn("2026-07-15", path.name)
            texto = path.read_text(encoding="utf-8")
            self.assertIn("fiz X e Y", texto)
            self.assertIn("semana", texto)


if __name__ == "__main__":
    unittest.main()
