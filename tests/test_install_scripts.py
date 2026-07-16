"""Regressao dos bootstraps.

O Windows PowerShell 5.1 (o `powershell.exe` padrao) le .ps1 SEM BOM usando o codepage
ANSI (CP1252). Um caractere UTF-8 multibyte vira mojibake; se o resultado contiver uma
aspa "inteligente" (U+201D), o parser do PowerShell a trata como DELIMITADOR DE STRING e
o script quebra com "Token inesperado" — numa linha que parece perfeita. Aconteceu com um
em-dash dentro de `Log "ANTA - bootstrap (Windows)"`. Solucao: ASCII puro no .ps1.
"""
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


class TestInstallPs1(unittest.TestCase):
    def test_e_ascii_puro(self):
        data = (REPO / "install.ps1").read_bytes()
        try:
            data.decode("ascii")
        except UnicodeDecodeError as e:
            trecho = data[max(0, e.start - 40):e.start + 10].decode("utf-8", "replace")
            self.fail(f"install.ps1 tem caractere nao-ASCII (byte {e.start}): ...{trecho!r}. "
                      f"PowerShell 5.1 le .ps1 sem BOM como ANSI e quebra o parse.")

    def test_aspas_duplas_balanceadas_por_linha(self):
        # heuristica simples: nenhuma linha de codigo deve ter numero impar de aspas
        # (foi assim que o mojibake se manifestou — string aberta vazando pro resto).
        for i, line in enumerate((REPO / "install.ps1").read_text(encoding="ascii").splitlines(), 1):
            code = line.split("#", 1)[0] if not line.lstrip().startswith("#") else ""
            self.assertEqual(code.count('"') % 2, 0, f"install.ps1 linha {i}: aspas impares -> {line!r}")


if __name__ == "__main__":
    unittest.main()
