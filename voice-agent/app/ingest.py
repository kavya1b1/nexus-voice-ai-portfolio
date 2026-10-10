"""Build (or rebuild) the vector index:  python -m app.ingest"""
from __future__ import annotations

import json
import logging

from .chunking import chunk_documents, knowledge_fingerprint, load_documents
from .config import Settings, get_settings
from .embeddings import Embedder, get_embedder
from .retriever import HybridRetriever

log = logging.getLogger("voice-agent.ingest")


def ensure_index(settings: Settings, embedder: Embedder, retriever: HybridRetriever, force: bool = False) -> int:
    """Re-index only when knowledge files, chunking settings or the embedding model changed."""
    marker = settings.data_dir / "index.json"
    fp = knowledge_fingerprint(settings.knowledge_dir, embedder.name, settings.chunk_chars, settings.chunk_overlap)
    if not force and marker.exists() and json.loads(marker.read_text()).get("fingerprint") == fp and len(retriever):
        return len(retriever)
    docs = load_documents(settings.knowledge_dir)
    chunks = chunk_documents(docs, settings.chunk_chars, settings.chunk_overlap)
    n = retriever.index(chunks)
    marker.write_text(json.dumps({"fingerprint": fp, "chunks": n, "embedder": embedder.name}))
    log.info("indexed %d chunks from %d documents with %s", n, len(docs), embedder.name)
    return n


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    s = get_settings()
    emb = get_embedder(s)
    n = ensure_index(s, emb, HybridRetriever(s, emb), force=True)
    print(f"Indexed {n} chunks using {emb.name}")
