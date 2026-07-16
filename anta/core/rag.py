"""RAG na CPU: busca semantica + memoria sobre o vault de notas.

Espelha stt.py/tts.py: o modelo de embedding e carregado PREGUICOSAMENTE na CPU
(fastembed/onnxruntime), com download atomico para config_dir(). NAO toca a VRAM
(Principio 1 do CLAUDE.md: a VRAM e exclusiva do LLM).

Este modulo so LE arquivos .md do vault e devolve trechos relevantes. A sintese da
resposta em linguagem natural e feita pelo LLM (Brain.answer), fora daqui — o RAG
nunca gera texto nem shell.

Store de vetores: forca-bruta com numpy (cosseno sobre uma matriz float32). Escala
pessoal (centenas de notas) roda folgado; sem faiss/chroma.
"""
from __future__ import annotations

import json
import re
import threading
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from anta.core.config import config_dir

# Modelo pequeno, multilingue, forte em PT-BR e — importante — REGISTRADO no fastembed
# (`intfloat/multilingual-e5-small` NAO esta no registro do fastembed 0.8; o e5-large e
# 1024d/pesado). O MiniLM-L12-v2 e 384d e nao usa prefixo. embed_query/embed_passage
# aplicam os prefixos "query: "/"passage: " automaticamente SE o modelo for e5 (trocar
# via constante e seguro: o Index reconstroi ao detectar mudanca de modelo/dim).
EMBED_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBED_FALLBACK = "sentence-transformers/paraphrase-multilingual-mpnet-base-v2"  # 768d, +qualidade
CHUNK_MAX_CHARS = 1000
DEFAULT_K = 5


def chunk_markdown(text: str, max_chars: int = CHUNK_MAX_CHARS) -> list[str]:
    """Divide um .md em pedacos por paragrafos, respeitando um teto de caracteres.
    Notas curtas viram um unico chunk; paragrafos gigantes sao quebrados em janelas."""
    paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    buf = ""
    for p in paras:
        if len(p) > max_chars:
            if buf:
                chunks.append(buf)
                buf = ""
            for i in range(0, len(p), max_chars):
                chunks.append(p[i:i + max_chars])
            continue
        if buf and len(buf) + len(p) + 2 > max_chars:
            chunks.append(buf)
            buf = p
        else:
            buf = f"{buf}\n\n{p}" if buf else p
    if buf:
        chunks.append(buf)
    return chunks


class Embedder:
    """fastembed na CPU. `load()` idempotente; importa o backend DENTRO de load()
    (mesmo padrao de Transcriber/PiperVoice), entao instanciar nao exige fastembed."""

    def __init__(self, model_name: str = EMBED_MODEL, cache_dir: Path | None = None) -> None:
        self.model_name = model_name
        self.cache_dir = cache_dir or (config_dir() / "embeddings")
        self._model = None

    def load(self):
        if self._model is None:
            from fastembed import TextEmbedding

            self.cache_dir.mkdir(parents=True, exist_ok=True)
            self._model = TextEmbedding(model_name=self.model_name,
                                        cache_dir=str(self.cache_dir))
        return self._model

    def _needs_prefix(self) -> bool:
        return "e5" in self.model_name.lower()

    def _embed(self, texts: list[str]) -> np.ndarray:
        model = self.load()
        vecs = np.asarray(list(model.embed(texts)), dtype=np.float32)
        return _l2_normalize(vecs)

    def embed_passage(self, texts: list[str]) -> np.ndarray:
        """Embute documentos/notas. Prefixo 'passage: ' para modelos e5."""
        if self._needs_prefix():
            texts = [f"passage: {t}" for t in texts]
        return self._embed(texts)

    def embed_query(self, text: str) -> np.ndarray:
        """Embute uma consulta -> vetor (d,). Prefixo 'query: ' para modelos e5."""
        payload = f"query: {text}" if self._needs_prefix() else text
        return self._embed([payload])[0]


def _l2_normalize(vecs: np.ndarray) -> np.ndarray:
    """Normaliza L2 por linha (cosseno = produto interno). Idempotente e barato."""
    vecs = np.atleast_2d(vecs).astype(np.float32)
    norms = np.linalg.norm(vecs, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vecs / norms


@dataclass
class Chunk:
    path: str
    chunk_id: int
    texto: str


class Index:
    """Matriz float32 (N, d) + metadados de chunk, persistida em config_dir()/index.

    reconcile(vault) e incremental por (mtime, size): reindexa novos/alterados e
    remove sumidos. Mismatch de model_name/dim ao carregar => descarta e reconstroi."""

    def __init__(self, embedder: Embedder, index_dir: Path | None = None) -> None:
        self.embedder = embedder
        self.dir = index_dir or (config_dir() / "index")
        self.vectors: np.ndarray | None = None      # (N, d) ou None quando vazio
        self.chunks: list[Chunk] = []
        self.files: dict[str, dict] = {}            # path -> {"mtime", "size"}
        self._loaded = False

    # -- persistencia -------------------------------------------------------
    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        self._loaded = True
        man_path = self.dir / "manifest.json"
        vec_path = self.dir / "vectors.npy"
        if not (man_path.exists() and vec_path.exists()):
            return
        try:
            manifest = json.loads(man_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        if manifest.get("model_name") != self.embedder.model_name:
            return  # modelo trocou -> trata como vazio (reconcile reconstroi)
        try:
            with open(vec_path, "rb") as f:
                vecs = np.load(f)
        except (OSError, ValueError):
            return
        chunks = [Chunk(**c) for c in manifest.get("chunks", [])]
        if len(chunks) != len(vecs):
            return  # inconsistente -> reconstroi
        self.vectors = vecs if len(vecs) else None
        self.chunks = chunks
        self.files = manifest.get("files", {})

    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        arr = self.vectors if self.vectors is not None else np.zeros((0, 0), np.float32)
        vec_tmp = self.dir / "vectors.npy.part"
        with open(vec_tmp, "wb") as f:              # file-handle: np.save nao renomeia a extensao
            np.save(f, arr)
        vec_tmp.replace(self.dir / "vectors.npy")
        manifest = {
            "model_name": self.embedder.model_name,
            "dim": int(arr.shape[1]) if arr.size else 0,
            "files": self.files,
            "chunks": [{"path": c.path, "chunk_id": c.chunk_id, "texto": c.texto}
                       for c in self.chunks],
        }
        man_tmp = self.dir / "manifest.json.part"
        man_tmp.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
        man_tmp.replace(self.dir / "manifest.json")

    # -- indexacao ----------------------------------------------------------
    @staticmethod
    def _scan(vault: Path) -> dict[str, dict]:
        """Estado atual do corpus: vault/*.md + memoria/*.md + resumos/*.md."""
        vault = Path(vault)
        files: dict[str, dict] = {}
        for d in (vault, vault / "memoria", vault / "resumos"):
            if not d.exists():
                continue
            for fp in d.glob("*.md"):
                try:
                    st = fp.stat()
                except OSError:
                    continue
                files[str(fp)] = {"mtime": st.st_mtime, "size": st.st_size}
        return files

    def reconcile(self, vault: Path) -> None:
        self._ensure_loaded()
        current = self._scan(vault)
        changed = {p for p, meta in current.items() if self.files.get(p) != meta}
        removed = set(self.files) - set(current)
        if not changed and not removed:
            return
        drop = changed | removed
        keep_idx = [i for i, c in enumerate(self.chunks) if c.path not in drop]
        kept_chunks = [self.chunks[i] for i in keep_idx]
        kept_vecs = self.vectors[keep_idx] if (self.vectors is not None and keep_idx) else None

        new_chunks: list[Chunk] = []
        new_texts: list[str] = []
        for p in sorted(changed):
            fp = Path(p)
            if not fp.exists():
                continue
            try:
                text = fp.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for cid, ct in enumerate(chunk_markdown(text)):
                new_chunks.append(Chunk(path=p, chunk_id=cid, texto=ct))
                new_texts.append(ct)
        new_vecs = self.embedder.embed_passage(new_texts) if new_texts else None

        self.chunks = kept_chunks + new_chunks
        parts = [v for v in (kept_vecs, new_vecs) if v is not None and len(v)]
        self.vectors = np.vstack(parts) if parts else None
        self.files = current
        self.save()

    # -- consulta -----------------------------------------------------------
    def search(self, qvec: np.ndarray, k: int = DEFAULT_K) -> list[Chunk]:
        self._ensure_loaded()
        if self.vectors is None or not self.chunks:
            return []
        sims = self.vectors @ np.asarray(qvec, dtype=np.float32)
        k = min(k, len(sims))
        top = np.argpartition(-sims, k - 1)[:k]
        top = top[np.argsort(-sims[top])]
        return [self.chunks[i] for i in top]


class RAG:
    """Fachada: indexa o vault e responde consultas. `ensure_ready()` e lazy e
    idempotente (protegido por Lock, espelhando o load() do Whisper/Piper) — a
    corretude NAO depende do pre-aquecimento em warm()."""

    def __init__(self, vault: Path, embedder: Embedder | None = None,
                 index: Index | None = None) -> None:
        self.vault = Path(vault)
        # embedder unico compartilhado com o Index (evita baixar/carregar 2x): se um
        # Index for passado sem embedder explicito, reusa o embedder dele.
        self.embedder = embedder or (index.embedder if index is not None else None) or Embedder()
        self.index = index or Index(self.embedder)
        self._lock = threading.Lock()
        self._ready = False

    def ensure_ready(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            self.index.reconcile(self.vault)
            self._ready = True

    def query(self, pergunta: str, k: int = DEFAULT_K) -> list[Chunk]:
        # Reconcilia ANTES de buscar: o daemon e de vida longa e notas/documentos
        # criados na sessao (ou editados por fora) precisam aparecer na consulta. O
        # reconcile e incremental por (mtime,size) — so re-embute o que mudou —, entao
        # o custo com o vault estavel e apenas um scan (stat) barato.
        with self._lock:
            self.index.reconcile(self.vault)
            self._ready = True
        qvec = self.embedder.embed_query(pergunta)
        return self.index.search(qvec, k)
