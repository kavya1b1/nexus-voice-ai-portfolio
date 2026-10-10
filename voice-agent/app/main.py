"""FastAPI server: /chat (SSE streaming agent), /transcribe (local Whisper), /health."""
from __future__ import annotations

import json
import logging
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from typing import Iterator

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from .agent import VoiceAgent
from .config import get_settings
from .embeddings import get_embedder
from .ingest import ensure_index
from .llm import OllamaLLM
from .retriever import HybridRetriever
from .stt import Transcriber

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
log = logging.getLogger("voice-agent")
settings = get_settings()


class Turn(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=1200)


class ChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=1200)
    history: list[Turn] = Field(default_factory=list, max_length=40)


@asynccontextmanager
async def lifespan(app: FastAPI):
    embedder = get_embedder(settings)
    retriever = HybridRetriever(settings, embedder)
    ensure_index(settings, embedder, retriever)
    llm = OllamaLLM(settings)
    app.state.agent = VoiceAgent(retriever, llm, settings)
    app.state.llm, app.state.retriever, app.state.embedder = llm, retriever, embedder
    app.state.stt = Transcriber(settings)
    app.state.stt.warmup_async()  # loads Whisper in the background and self-tests it
    log.info("ready · embeddings=%s · chunks=%d · llm=%s (%s)", embedder.name, len(retriever), settings.llm_model,
             "online" if llm.available() else "offline → extractive answers")
    yield


app = FastAPI(title="Kavya's Voice Agent", version="1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=list(settings.allowed_origins), allow_methods=["GET", "POST"], allow_headers=["*"])

_hits: dict[str, deque] = defaultdict(deque)


def rate_limit(request: Request) -> None:
    ip = request.client.host if request.client else "unknown"
    q, now = _hits[ip], time.time()
    while q and now - q[0] > 60:
        q.popleft()
    if len(q) >= settings.rate_limit_per_min:
        raise HTTPException(429, "Too many requests, please slow down.")
    q.append(now)


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


@app.get("/health")
def health():
    return {"status": "ok", "embeddings": app.state.embedder.name, "chunks": len(app.state.retriever),
            "llm": app.state.llm.available(), "model": settings.llm_model, "stt": app.state.stt.available(),
            "stt_ready": app.state.stt.ready, "stt_error": app.state.stt.error}


@app.post("/chat")
def chat(req: ChatRequest, request: Request):
    rate_limit(request)
    request_id = uuid.uuid4().hex[:12]
    question = req.message.strip()
    if not question:
        raise HTTPException(400, "Empty message")
    question = question[: settings.max_question_chars]
    history = [t.model_dump() for t in req.history][-settings.max_history_turns:]
    agent: VoiceAgent = app.state.agent

    def stream() -> Iterator[str]:
        t0 = time.time()
        log.info(json.dumps({"event":"chat_start","request_id":request_id,"chars":len(question),"history_turns":len(history)}))
        state: dict = {"question": question, "history": history}
        for node, update in agent.plan_stream(question, history):
            agent.merge(state, update)
            for step in update.get("trace", []):
                yield sse("trace", step)

        links = list((state.get("tool") or {}).get("links", []))
        hits = state.get("hits") or []
        if state.get("relevant"):
            seen = set()
            for h in hits[:1]:  # buttons come from the best-matching passage only, so they always match the answer
                for ln in h.chunk.links:
                    if ln["href"] not in seen:
                        seen.add(ln["href"]); links.append(ln)
            yield sse("sources", [h.brief() for h in hits])
        yield sse("links", links[:6])

        if state.get("direct"):
            yield sse("token", state["direct"])
            yield sse("done", {"request_id": request_id, "mode": "direct", "relevant": bool(state.get("relevant")), "verified": True, "ms": int((time.time() - t0) * 1000)})
            log.info(json.dumps({"event":"chat_done","request_id":request_id,"mode":"direct","elapsed_ms":int((time.time()-t0)*1000)}))
            return

        llm: OllamaLLM = app.state.llm
        if llm.available():
            text, ok = "", True
            try:
                for piece in llm.stream(state["messages"], max_tokens=state.get("max_tokens")):
                    text += piece
                    yield sse("token", piece)
            except Exception as exc:
                log.warning("LLM stream failed: %s", exc)
                ok = False
            verdict = agent.verify(text, hits) if ok and text else None
            if verdict is None or not verdict.ok:
                safe = agent.extractive_answer(question, hits, 6 if state.get("detail") else 3)
                yield sse("trace", {"node": "verify", "detail": "failed: " + "; ".join(verdict.issues) + " → replaced with extractive answer"
                                     if verdict else "LLM unavailable → extractive answer"})
                yield sse("replace", safe)
                yield sse("done", {"request_id": request_id, "mode": "extractive-fallback", "relevant": True, "verified": False, "ms": int((time.time() - t0) * 1000)})
            else:
                yield sse("trace", {"node": "verify", "detail": "all numbers, emails and vocabulary supported by sources ✓"})
                yield sse("done", {"request_id": request_id, "mode": "llm", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})
        else:
            yield sse("trace", {"node": "generate", "detail": f"Ollama model '{settings.llm_model}' not running → extractive answer from top passage"})
            yield sse("token", agent.extractive_answer(question, hits, 6 if state.get("detail") else 3))
            yield sse("done", {"request_id": request_id, "mode": "extractive", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})

    return StreamingResponse(stream(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/transcribe")
async def transcribe(request: Request, audio: UploadFile = File(...)):
    rate_limit(request)
    stt: Transcriber = app.state.stt
    if not stt.available():
        raise HTTPException(501, "faster-whisper is not installed on the server")
    if not stt.ready:
        raise HTTPException(503, "Local speech-to-text is not ready: " + (stt.error or "still loading the model"))
    data = await audio.read()
    if not data:
        raise HTTPException(400, "Empty audio upload")
    if len(data) > 8_000_000:
        raise HTTPException(413, "Audio too large")
    import anyio

    text = await anyio.to_thread.run_sync(stt.transcribe, data, ".webm")
    return {"text": text}
