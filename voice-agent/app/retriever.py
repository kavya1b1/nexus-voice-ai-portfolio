"""Hybrid retriever: dense (ChromaDB) + lexical (BM25) fused with Reciprocal Rank Fusion,
metadata tag boosting, and optional cross-encoder re-ranking."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass

import chromadb
from rank_bm25 import BM25Okapi

from .chunking import Chunk
from .config import Settings
from .embeddings import Embedder

log = logging.getLogger("voice-agent.retriever")

STOP = set("""a an the is are was were be been am do does did of to in on at for with and or but if so as by from about tell me you
your her she he his hers what whats which who whom how when where we it its this that these those i my give show please can could
would should there them they any some also just very much have has had will shall may might must let lets ok okay yes no not""".split())
_WORD = re.compile(r"[a-z0-9]+")


def tokenize(text: str) -> list[str]:
    toks = []
    for w in _WORD.findall(text.lower().replace("c++", "cpp")):
        if w in STOP or len(w) < 2:
            continue
        toks.append(w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w)
    return toks


@dataclass
class Hit:
    chunk: Chunk
    dense_sim: float = 0.0
    bm25: float = 0.0
    fused: float = 0.0
    rerank: float | None = None

    @property
    def text(self) -> str:
        return self.chunk.text

    def brief(self) -> dict:
        c = self.chunk
        return {"id": c.id, "title": c.title, "section": c.section, "anchor": c.anchor, "links": c.links,
                "dense": round(self.dense_sim, 3), "bm25": round(self.bm25, 2), "score": round(self.fused, 4)}


class HybridRetriever:
    COLLECTION = "kavya_knowledge"

    def __init__(self, settings: Settings, embedder: Embedder):
        self.s = settings
        self.embedder = embedder
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(path=str(settings.data_dir / "chroma"))
        self.collection = self.client.get_or_create_collection(self.COLLECTION, metadata={"hnsw:space": "cosine"})
        self._chunks: list[Chunk] = []
        self._bm25: BM25Okapi | None = None
        self._reranker = None
        self.min_sim = settings.min_dense_sim if settings.min_dense_sim is not None else embedder.default_min_sim
        if self.collection.count():
            self._load_lexical()

    # ── indexing ──────────────────────────────────────────
    def index(self, chunks: list[Chunk]) -> int:
        self.client.delete_collection(self.COLLECTION)
        self.collection = self.client.get_or_create_collection(self.COLLECTION, metadata={"hnsw:space": "cosine"})
        if chunks:
            vecs = self.embedder.embed([c.embed_text for c in chunks])
            self.collection.add(ids=[c.id for c in chunks], documents=[c.text for c in chunks],
                                metadatas=[c.to_metadata() for c in chunks], embeddings=vecs.tolist())
        self._load_lexical()
        return len(chunks)

    def _load_lexical(self) -> None:
        data = self.collection.get(include=["documents", "metadatas"])
        self._chunks = [Chunk.from_store(i, d, m) for i, d, m in zip(data["ids"], data["documents"], data["metadatas"])]
        corpus = [tokenize(c.embed_text) for c in self._chunks]
        self._bm25 = BM25Okapi(corpus) if corpus else None

    def __len__(self) -> int:
        return len(self._chunks)

    def doc_chunks(self, source: str) -> list[Chunk]:
        """All chunks of one source document, in reading order (parent-document retrieval)."""
        def order(c: Chunk) -> int:
            m = re.search(r"-(\d+)$", c.id)
            return int(m.group(1)) if m else 0
        return sorted((c for c in self._chunks if c.source == source), key=order)

    # ── search ────────────────────────────────────────────
    def search(self, query: str, k: int | None = None, tags: set[str] | None = None) -> list[Hit]:
        k = k or self.s.top_k
        if not self._chunks:
            return []
        n = min(self.s.candidates, len(self._chunks))
        by_id = {c.id: c for c in self._chunks}
        hits: dict[str, Hit] = {}

        # dense
        qv = self.embedder.embed([query], is_query=True)
        res = self.collection.query(query_embeddings=qv.tolist(), n_results=n, include=["distances"])
        dense_rank = {}
        for rank, (cid, dist) in enumerate(zip(res["ids"][0], res["distances"][0])):
            dense_rank[cid] = rank
            hits.setdefault(cid, Hit(by_id[cid])).dense_sim = float(1.0 - dist)

        # lexical
        bm_rank = {}
        qt = tokenize(query)
        if qt and self._bm25:
            scores = self._bm25.get_scores(qt)
            order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)[:n]
            for rank, i in enumerate(o for o in order if scores[o] > 0):
                cid = self._chunks[i].id
                bm_rank[cid] = rank
                hits.setdefault(cid, Hit(self._chunks[i])).bm25 = float(scores[i])

        # reciprocal rank fusion + metadata boost
        for cid, h in hits.items():
            h.fused = sum(1.0 / (self.s.rrf_k + r[cid]) for r in (dense_rank, bm_rank) if cid in r)
            if tags and tags & set(h.chunk.tags):
                h.fused *= 1.0 + self.s.tag_boost
        ranked = sorted(hits.values(), key=lambda h: h.fused, reverse=True)

        if self.s.rerank:
            ranked = self._rerank(query, ranked[: max(k * 3, 6)])
        return ranked[:k]

    def _rerank(self, query: str, hits: list[Hit]) -> list[Hit]:
        try:
            if self._reranker is None:
                from sentence_transformers import CrossEncoder

                self._reranker = CrossEncoder(self.s.rerank_model)
            scores = self._reranker.predict([(query, h.chunk.embed_text) for h in hits])
            for h, s in zip(hits, scores):
                h.rerank = float(s)
            return sorted(hits, key=lambda h: h.rerank, reverse=True)
        except Exception as exc:
            log.warning("re-ranking skipped: %s", exc)
            return hits
