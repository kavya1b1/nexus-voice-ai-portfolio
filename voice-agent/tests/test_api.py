import json
import os
import tempfile

os.environ["FORCE_HASHING_EMBEDDER"] = "1"
os.environ["DATA_DIR"] = tempfile.mkdtemp()
os.environ["LLM_BASE_URL"] = "http://127.0.0.1:9"  # nothing listens here → LLM offline

import pytest
from fastapi.testclient import TestClient

from app.main import app
from tests.test_pipeline import StubLLM


def parse_sse(text):
    events = []
    for block in text.strip().split("\n\n"):
        lines = dict(l.split(": ", 1) for l in block.splitlines() if ": " in l)
        events.append((lines["event"], json.loads(lines["data"])))
    return events


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as c:
        yield c


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok" and body["chunks"] > 15 and body["llm"] is False
    assert "stt_ready" in body and "stt_error" in body


def test_chat_streams_trace_sources_tokens_done(client):
    r = client.post("/chat", json={"message": "give me her email ID"})
    assert r.headers["content-type"].startswith("text/event-stream")
    ev = parse_sse(r.text)
    kinds = [k for k, _ in ev]
    assert kinds[0] == "trace" and "sources" in kinds and "links" in kinds and kinds[-1] == "done"
    answer = "".join(d for k, d in ev if k == "token")
    assert "kavya1b1@gmail.com" in answer
    assert any(l["href"].startswith("mailto:") for k, d in ev if k == "links" for l in d)


def test_chat_with_llm_streams_and_verifies(client):
    app.state.llm = StubLLM("The ensemble model reaches 91.3% prediction accuracy [1].")
    ev = parse_sse(client.post("/chat", json={"message": "what is the proposal evaluator accuracy"}).text)
    done = ev[-1][1]
    assert done["mode"] == "llm" and done["verified"] is True
    assert any(k == "trace" and d["node"] == "verify" and "✓" in d["detail"] for k, d in ev)


def test_chat_replaces_hallucinated_stream(client):
    app.state.llm = StubLLM("She won a Nobel prize and scored 12.5% accuracy.")
    ev = parse_sse(client.post("/chat", json={"message": "what is the proposal evaluator accuracy"}).text)
    assert any(k == "replace" and "91.3" in d for k, d in ev)
    assert ev[-1][1]["verified"] is False


def test_validation_and_limits(client):
    assert client.post("/chat", json={"message": "   "}).status_code == 400
    assert client.post("/chat", json={"message": "hi", "history": [{"role": "system", "content": "x"}]}).status_code == 422


def test_transcribe_requires_whisper(client):
    r = client.post("/transcribe", files={"audio": ("a.webm", b"123", "audio/webm")})
    assert r.status_code in (200, 501, 503)
