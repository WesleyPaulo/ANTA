"""Testes do nucleo RAG (anta/core/rag.py) SEM baixar fastembed nem rede.

O embedder e falso: mapeia texto -> vetor por palavras-chave, deterministico. Assim
testamos chunking, ranking por cosseno, reconcile incremental (mtime/size), persistencia
e o roteamento de prefixo e5 — tudo na CPU, sem GPU/Ollama/modelo real.
"""
import sys
import tempfile
import unittest
import unittest.mock
import warnings
from pathlib import Path

import numpy as np

from anta.core import rag
from anta.core.rag import Embedder

_KEYS = ["cafe", "reuniao", "projeto", "prazo"]


class FakeEmbedder:
    """Vetor por presenca de palavra-chave (+ um eixo constante p/ evitar norma zero)."""
    model_name = "fake-model"

    def __init__(self) -> None:
        self.passage_calls: list[list[str]] = []
        self.query_calls: list[str] = []

    def _vec(self, t: str) -> np.ndarray:
        low = t.lower()
        v = np.array([1.0 if k in low else 0.0 for k in _KEYS] + [0.1], np.float32)
        return rag._l2_normalize(v)[0]

    def embed_passage(self, texts):
        self.passage_calls.append(list(texts))
        return np.vstack([self._vec(t) for t in texts]).astype(np.float32)

    def embed_query(self, text):
        self.query_calls.append(text)
        return self._vec(text)


def _write(vault: Path, name: str, body: str) -> Path:
    vault.mkdir(parents=True, exist_ok=True)
    p = vault / name
    p.write_text(body, encoding="utf-8")
    return p


class TestChunking(unittest.TestCase):
    def test_nota_curta_vira_um_chunk(self):
        self.assertEqual(rag.chunk_markdown("# Titulo\n\ncorpo curto"),
                         ["# Titulo\n\ncorpo curto"])

    def test_paragrafos_agrupam_ate_o_teto(self):
        text = "a" * 400 + "\n\n" + "b" * 400 + "\n\n" + "c" * 400
        chunks = rag.chunk_markdown(text, max_chars=1000)
        # 400+400 cabem juntos (804 < 1000); o terceiro estoura -> vai pro proximo
        self.assertEqual(len(chunks), 2)

    def test_paragrafo_gigante_quebra_em_janelas(self):
        chunks = rag.chunk_markdown("x" * 2500, max_chars=1000)
        self.assertEqual([len(c) for c in chunks], [1000, 1000, 500])

    def test_vazio(self):
        self.assertEqual(rag.chunk_markdown("   \n\n  "), [])


class TestNormalize(unittest.TestCase):
    def test_l2_unit(self):
        out = rag._l2_normalize(np.array([3.0, 4.0], np.float32))
        self.assertAlmostEqual(float(np.linalg.norm(out[0])), 1.0, places=5)

    def test_vetor_zero_nao_estoura(self):
        out = rag._l2_normalize(np.zeros((1, 3), np.float32))
        self.assertTrue(np.all(np.isfinite(out)))


class TestIndexSearch(unittest.TestCase):
    def _rag(self, vault: Path, emb: FakeEmbedder) -> rag.RAG:
        idx_dir = vault / ".idx"
        return rag.RAG(vault, embedder=emb, index=rag.Index(emb, index_dir=idx_dir))

    def test_ranking_por_cosseno(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            _write(vault, "a.md", "comprar cafe hoje")
            _write(vault, "b.md", "reuniao de projeto amanha")
            emb = FakeEmbedder()
            r = self._rag(vault, emb)
            top = r.query("cafe", k=1)
            self.assertEqual(len(top), 1)
            self.assertTrue(top[0].path.endswith("a.md"))
            self.assertEqual(emb.query_calls, ["cafe"])

    def test_memoria_subpasta_e_indexada(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            _write(vault / "memoria", "pref.md", "prazo do projeto e sexta")
            emb = FakeEmbedder()
            r = self._rag(vault, emb)
            top = r.query("prazo", k=1)
            self.assertTrue(top and "memoria" in top[0].path)

    def test_vault_inexistente_devolve_vazio(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "nao-existe"
            emb = FakeEmbedder()
            r = self._rag(vault, emb)
            self.assertEqual(r.query("cafe"), [])

    def test_query_ve_notas_criadas_na_sessao(self):
        # regressao (review #2): daemon de vida longa. Uma nota criada DEPOIS do
        # primeiro query precisa aparecer no proximo (query reconcilia o vault).
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            _write(vault, "a.md", "comprar cafe")
            emb = FakeEmbedder()
            r = self._rag(vault, emb)
            self.assertTrue(r.query("cafe", k=1)[0].path.endswith("a.md"))
            _write(vault, "b.md", "reuniao de projeto")   # criada apos o 1o query
            top = r.query("reuniao", k=1)
            self.assertTrue(top and top[0].path.endswith("b.md"))


class TestReconcileIncremental(unittest.TestCase):
    def _index(self, vault: Path, emb: FakeEmbedder) -> rag.Index:
        return rag.Index(emb, index_dir=vault / ".idx")

    def test_novo_arquivo_e_incorporado(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            emb = FakeEmbedder()
            idx = self._index(vault, emb)
            _write(vault, "a.md", "cafe")
            idx.reconcile(vault)
            self.assertEqual(len(idx.chunks), 1)
            _write(vault, "b.md", "reuniao")
            emb.passage_calls.clear()
            idx.reconcile(vault)
            self.assertEqual(len(idx.chunks), 2)
            # so o arquivo novo foi re-embutido
            self.assertEqual(emb.passage_calls, [["reuniao"]])

    def test_arquivo_alterado_e_reindexado(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            emb = FakeEmbedder()
            idx = self._index(vault, emb)
            p = _write(vault, "a.md", "cafe")
            idx.reconcile(vault)
            # muda o conteudo (tamanho diferente => detectado mesmo se mtime igual)
            p.write_text("reuniao de projeto", encoding="utf-8")
            emb.passage_calls.clear()
            idx.reconcile(vault)
            self.assertEqual(emb.passage_calls, [["reuniao de projeto"]])
            self.assertTrue(any("reuniao" in c.texto for c in idx.chunks))

    def test_arquivo_removido_some_do_indice(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            emb = FakeEmbedder()
            idx = self._index(vault, emb)
            _write(vault, "a.md", "cafe")
            p = _write(vault, "b.md", "reuniao")
            idx.reconcile(vault)
            self.assertEqual(len(idx.chunks), 2)
            p.unlink()
            idx.reconcile(vault)
            self.assertEqual(len(idx.chunks), 1)
            self.assertTrue(idx.chunks[0].path.endswith("a.md"))

    def test_sem_mudanca_nao_reembute(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            emb = FakeEmbedder()
            idx = self._index(vault, emb)
            _write(vault, "a.md", "cafe")
            idx.reconcile(vault)
            emb.passage_calls.clear()
            idx.reconcile(vault)
            self.assertEqual(emb.passage_calls, [])


class TestPersistence(unittest.TestCase):
    def test_save_load_roundtrip(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            emb = FakeEmbedder()
            idx_dir = vault / ".idx"
            _write(vault, "a.md", "reuniao de projeto")
            rag.Index(emb, index_dir=idx_dir).reconcile(vault)
            # nova instancia carrega do disco e responde
            idx2 = rag.Index(emb, index_dir=idx_dir)
            top = idx2.search(emb.embed_query("projeto"), k=1)
            self.assertTrue(top and top[0].path.endswith("a.md"))

    def test_mismatch_de_modelo_reconstroi(self):
        with tempfile.TemporaryDirectory() as d:
            vault = Path(d) / "vault"
            idx_dir = vault / ".idx"
            _write(vault, "a.md", "cafe")
            rag.Index(FakeEmbedder(), index_dir=idx_dir).reconcile(vault)

            class OtherEmbedder(FakeEmbedder):
                model_name = "outro-modelo"

            other = OtherEmbedder()
            idx2 = rag.Index(other, index_dir=idx_dir)
            idx2._ensure_loaded()
            self.assertEqual(idx2.chunks, [])   # descartou o indice do modelo antigo
            idx2.reconcile(vault)               # reconstroi com o novo embedder
            self.assertEqual(other.passage_calls, [["cafe"]])


class TestPrefixRouting(unittest.TestCase):
    """Modelos e5 precisam de 'query: '/'passage: '; MiniLM nao. Trocar isso
    degrada recall em silencio, entao travamos com teste."""

    def _fake_model(self, captured):
        class FakeModel:
            def embed(self, texts):
                texts = list(texts)
                captured.append(texts)
                return iter([np.array([1.0, 0.0], np.float32) for _ in texts])
        return FakeModel()

    def test_e5_recebe_prefixo(self):
        captured = []
        emb = rag.Embedder(model_name="intfloat/multilingual-e5-small")
        emb._model = self._fake_model(captured)  # evita load()/fastembed
        emb.embed_query("prazo")
        emb.embed_passage(["nota"])
        self.assertEqual(captured[0], ["query: prazo"])
        self.assertEqual(captured[1], ["passage: nota"])

    def test_minilm_sem_prefixo(self):
        captured = []
        emb = rag.Embedder(model_name="sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2")
        emb._model = self._fake_model(captured)
        emb.embed_query("prazo")
        emb.embed_passage(["nota"])
        self.assertEqual(captured[0], ["prazo"])
        self.assertEqual(captured[1], ["nota"])


class TestWarningDoFastembed(unittest.TestCase):
    """O fastembed avisa sobre mean pooling ao carregar o MiniLM e isso vazava no console
    NO MEIO de um comando de voz. Ja errei este fix uma vez: filtrei por
    `module="fastembed.*"`, mas o warning e emitido com stacklevel apontando pro CHAMADOR,
    entao o modulo que o filtro ve e "anta.core.rag". Por isso o teste imita o stacklevel."""

    def _fastembed_falso(self):
        import types

        mod = types.ModuleType("fastembed")

        def TextEmbedding(model_name=None, cache_dir=None):
            warnings.warn(f"The model {model_name} now uses mean pooling instead of CLS "
                          f"embedding. In order to preserve the previous behaviour...",
                          UserWarning, stacklevel=2)  # <- culpa o chamador, como o real
            return "MODELO"

        mod.TextEmbedding = TextEmbedding
        return mod

    def test_nao_vaza_pro_console(self):
        with unittest.mock.patch.dict(sys.modules, {"fastembed": self._fastembed_falso()}):
            with warnings.catch_warnings(record=True) as vistos:
                warnings.simplefilter("always")
                Embedder(cache_dir=Path(tempfile.mkdtemp())).load()
        self.assertEqual([str(w.message) for w in vistos], [])

    def test_outros_warnings_do_fastembed_continuam_visiveis(self):
        # silenciar TUDO esconderia um aviso que importa; so o do mean pooling e ruido
        import types

        mod = types.ModuleType("fastembed")

        def TextEmbedding(model_name=None, cache_dir=None):
            warnings.warn("modelo depreciado, sera removido", UserWarning, stacklevel=2)
            return "MODELO"

        mod.TextEmbedding = TextEmbedding
        with unittest.mock.patch.dict(sys.modules, {"fastembed": mod}):
            with warnings.catch_warnings(record=True) as vistos:
                warnings.simplefilter("always")
                Embedder(cache_dir=Path(tempfile.mkdtemp())).load()
        self.assertIn("depreciado", str(vistos[0].message))


if __name__ == "__main__":
    unittest.main()
