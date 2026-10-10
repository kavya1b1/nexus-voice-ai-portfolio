"""Reliability regression tests that do not require a live Ollama server."""
import os

def test_evaluation_dataset_has_100_cases():
    import json
    from pathlib import Path
    rows=[json.loads(x) for x in (Path(__file__).parents[1]/"eval"/"questions.jsonl").read_text().splitlines() if x.strip()]
    assert len(rows)==100
    assert all({"q","expect","oos"}.issubset(r) for r in rows)
    assert all(isinstance(r["q"],str) and r["q"].strip() for r in rows)

def test_request_id_in_sse_done_event():
    # API test suite uses a TestClient and offline hashing embeddings.
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        response=client.post("/chat",json={"message":"give me her email ID"})
    assert response.status_code==200
    assert 'event: done' in response.text
    assert '"request_id"' in response.text

def test_empty_message_rejected():
    from fastapi.testclient import TestClient
    from app.main import app
    with TestClient(app) as client:
        assert client.post("/chat",json={"message":"   "}).status_code==400
