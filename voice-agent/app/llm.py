"""Local LLM client for Ollama (https://ollama.com), free and offline."""
from __future__ import annotations

import json
import logging
import time
from typing import Iterator

import httpx

from .config import Settings

log = logging.getLogger("voice-agent.llm")


class OllamaLLM:
    def __init__(self, settings: Settings):
        self.s = settings
        self._ok_until = 0.0
        self._ok = False

    def available(self) -> bool:
        """True if the Ollama server is up and the model is pulled. Cached for a few seconds."""
        now = time.time()
        if now < self._ok_until:
            return self._ok
        try:
            r = httpx.get(f"{self.s.llm_base_url}/api/tags", timeout=1.0)
            names = {m.get("name", "") for m in r.json().get("models", [])}
            base = self.s.llm_model.split(":")[0]
            self._ok = any(n == self.s.llm_model or n.split(":")[0] == base for n in names)
        except Exception:
            self._ok = False
        self._ok_until = now + (15 if self._ok else 5)
        return self._ok

    def _payload(self, messages: list[dict], stream: bool, max_tokens: int | None = None) -> dict:
        return {"model": self.s.llm_model, "messages": messages, "stream": stream, "keep_alive": "30m",
                "options": {"temperature": self.s.llm_temperature, "num_predict": max_tokens or self.s.llm_max_tokens}}

    def stream(self, messages: list[dict], max_tokens: int | None = None) -> Iterator[str]:
        with httpx.stream("POST", f"{self.s.llm_base_url}/api/chat", json=self._payload(messages, True, max_tokens), timeout=self.s.llm_timeout_seconds) as r:
            r.raise_for_status()
            for line in r.iter_lines():
                if not line:
                    continue
                data = json.loads(line)
                piece = data.get("message", {}).get("content", "")
                if piece:
                    yield piece
                if data.get("done"):
                    break

    def complete(self, messages: list[dict], max_tokens: int | None = None) -> str:
        r = httpx.post(f"{self.s.llm_base_url}/api/chat", json=self._payload(messages, False, max_tokens), timeout=self.s.llm_timeout_seconds)
        r.raise_for_status()
        return r.json()["message"]["content"].strip()
