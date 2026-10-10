"""Embedding backends.

Default: a real sentence-transformers model (downloaded once, then fully offline).
Fallback: a deterministic hashing embedder so the pipeline (and the test-suite)
still runs with zero downloads. The fallback is lexical, not semantic.
"""
from __future__ import annotations

import logging
import re
import zlib
from typing import Protocol

import numpy as np

from .config import Settings

log = logging.getLogger("voice-agent.embeddings")
_WORD = re.compile(r"[a-z0-9]+")


class Embedder(Protocol):
    name: str
    dim: int
    default_min_sim: float  # cosine similarity above which a top hit counts as "on topic"

    def embed(self, texts: list[str], is_query: bool = False) -> np.ndarray: ...


class SentenceTransformerEmbedder:
    default_min_sim = 0.30

    def __init__(self, model_name: str):
        from sentence_transformers import SentenceTransformer  # lazy: heavy import

        self._model = SentenceTransformer(model_name)
        self.name = model_name
        self.dim = int(self._model.get_sentence_embedding_dimension())

    def embed(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        vecs = self._model.encode(texts, normalize_embeddings=True, show_progress_bar=False)
        return np.asarray(vecs, dtype="float32")


class HashingEmbedder:
    """Feature-hashing bag of unigrams + bigrams, L2-normalised."""

    default_min_sim = 0.12

    def __init__(self, dim: int = 512):
        self.name = f"hashing-{dim}"
        self.dim = dim

    @staticmethod
    def _stem(w: str) -> str:
        return w[:-1] if len(w) > 3 and w.endswith("s") and not w.endswith("ss") else w

    def _vec(self, text: str) -> np.ndarray:
        v = np.zeros(self.dim, dtype="float32")
        words = [self._stem(w) for w in _WORD.findall(text.lower())]
        grams = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
        for g in grams:
            h = zlib.crc32(g.encode())
            v[h % self.dim] += 1.0 if (h >> 16) & 1 else -1.0  # signed hashing
        n = np.linalg.norm(v)
        return v / n if n else v

    def embed(self, texts: list[str], is_query: bool = False) -> np.ndarray:
        return np.vstack([self._vec(t) for t in texts]) if texts else np.zeros((0, self.dim), dtype="float32")


def get_embedder(settings: Settings) -> Embedder:
    if settings.force_hashing_embedder:
        return HashingEmbedder()
    try:
        return SentenceTransformerEmbedder(settings.embed_model)
    except Exception as exc:  # missing package or no cached model
        log.warning("sentence-transformers unavailable (%s). Falling back to the hashing embedder.", exc)
        return HashingEmbedder()
