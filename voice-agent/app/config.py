"""Central configuration. Every value can be overridden with an environment variable."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _bool(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Settings:
    # data
    knowledge_dir: Path = Path(os.getenv("KNOWLEDGE_DIR", ROOT / "knowledge"))
    data_dir: Path = Path(os.getenv("DATA_DIR", ROOT / "data"))
    # embeddings / retrieval
    embed_model: str = os.getenv("EMBED_MODEL", "sentence-transformers/all-MiniLM-L6-v2")
    force_hashing_embedder: bool = _bool("FORCE_HASHING_EMBEDDER")  # offline fallback, used by tests
    rerank: bool = _bool("RERANK")  # cross-encoder re-ranking (extra model download)
    rerank_model: str = os.getenv("RERANK_MODEL", "cross-encoder/ms-marco-MiniLM-L-6-v2")
    top_k: int = int(os.getenv("TOP_K", "3"))
    candidates: int = int(os.getenv("CANDIDATES", "10"))
    rrf_k: int = int(os.getenv("RRF_K", "60"))
    tag_boost: float = float(os.getenv("TAG_BOOST", "0.6"))
    min_dense_sim: float | None = float(os.environ["MIN_DENSE_SIM"]) if "MIN_DENSE_SIM" in os.environ else None
    max_rewrites: int = int(os.getenv("MAX_REWRITES", "1"))
    # chunking
    chunk_chars: int = int(os.getenv("CHUNK_CHARS", "700"))
    chunk_overlap: int = int(os.getenv("CHUNK_OVERLAP", "80"))
    # LLM (Ollama)
    llm_base_url: str = os.getenv("LLM_BASE_URL", "http://localhost:11434")
    llm_model: str = os.getenv("LLM_MODEL", "llama3:latest")
    llm_temperature: float = float(os.getenv("LLM_TEMPERATURE", "0.2"))
    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "220"))
    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))
    max_history_turns: int = int(os.getenv("MAX_HISTORY_TURNS", "6"))
    max_graph_steps: int = int(os.getenv("MAX_GRAPH_STEPS", "12"))
    # speech to text (faster-whisper)
    whisper_model: str = os.getenv("WHISPER_MODEL", "base.en")
    # tools
    github_user: str = os.getenv("GITHUB_USER", "kavya1b1")
    # api
    allowed_origins: tuple[str, ...] = tuple(o.strip() for o in os.getenv("ALLOWED_ORIGINS", "*").split(",") if o.strip())
    max_question_chars: int = int(os.getenv("MAX_QUESTION_CHARS", "400"))
    rate_limit_per_min: int = int(os.getenv("RATE_LIMIT_PER_MIN", "30"))


def get_settings() -> Settings:
    return Settings()
