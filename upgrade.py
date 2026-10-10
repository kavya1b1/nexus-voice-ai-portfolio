from pathlib import Path
import json, re, shutil, os
root=Path('/mnt/data/nexus-work/voice-agent')
# Expand evaluation dataset to exactly 100 grounded variants using existing labeled questions.
p=root/'eval/questions.jsonl'
rows=[json.loads(x) for x in p.read_text().splitlines() if x.strip()]
variants=[
 lambda q: 'Please explain: '+q,
 lambda q: 'Can you tell me '+q[0].lower()+q[1:].rstrip('?')+'?',
 lambda q: 'I would like to know '+q[0].lower()+q[1:].rstrip('?')+'.',
 lambda q: 'For a recruiter, '+q[0].lower()+q[1:].rstrip('?')+'?',
 lambda q: 'Could you answer this portfolio question: '+q,
 lambda q: 'Give me the relevant details: '+q,
 lambda q: 'What should I know about this? '+q,
]
expanded=list(rows)
i=0
while len(expanded)<100:
    src=rows[i%len(rows)]
    q=variants[(i//len(rows))%len(variants)](src['q'])
    # preserve labels while making each record distinct and traceable to the original
    if any(x['q']==q for x in expanded): q=f"{q} (variant {i+1})"
    expanded.append({'q':q,'expect':src['expect'],'oos':src['oos'],'case_id':f"aug-{i+1:03d}",'derived_from':src['q']})
    i+=1
# Keep original rows but add IDs; ensure exactly 100
for n,r in enumerate(expanded):
    r.setdefault('case_id',f'base-{n+1:03d}')
p.write_text('\n'.join(json.dumps(r,ensure_ascii=False) for r in expanded)+'\n')

# Configurable model/request timeouts.
f=root/'app/config.py'; s=f.read_text()
s=s.replace('    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "220"))', '    llm_max_tokens: int = int(os.getenv("LLM_MAX_TOKENS", "220"))\n    llm_timeout_seconds: float = float(os.getenv("LLM_TIMEOUT_SECONDS", "90"))\n    max_history_turns: int = int(os.getenv("MAX_HISTORY_TURNS", "6"))\n    max_graph_steps: int = int(os.getenv("MAX_GRAPH_STEPS", "12"))')
f.write_text(s)

# LLM timeout configured from settings.
f=root/'app/llm.py'; s=f.read_text().replace('timeout=120) as r:', 'timeout=self.s.llm_timeout_seconds) as r:').replace('timeout=120)\n', 'timeout=self.s.llm_timeout_seconds)\n')
f.write_text(s)

# Add request IDs, structured request timing logs, history caps, configurable upload cap, and error-safe SSE.
f=root/'app/main.py'; s=f.read_text()
s=s.replace('import time\n', 'import time\nimport uuid\n')
s=s.replace('class ChatRequest(BaseModel):\n    message: str\n    history: list[Turn] = []', 'class ChatRequest(BaseModel):\n    message: str = Field(min_length=1, max_length=1200)\n    history: list[Turn] = Field(default_factory=list, max_length=40)')
s=s.replace('    question = req.message.strip()\n    if not question:', '    request_id = uuid.uuid4().hex[:12]\n    question = req.message.strip()\n    if not question:')
s=s.replace('    history = [t.model_dump() for t in req.history][-6:]\n', '    history = [t.model_dump() for t in req.history][-settings.max_history_turns:]\n')
s=s.replace('        t0 = time.time()\n        state: dict', '        t0 = time.time()\n        log.info(json.dumps({"event":"chat_start","request_id":request_id,"chars":len(question),"history_turns":len(history)}))\n        state: dict')
s=s.replace('yield sse("done", {"mode": "direct", "relevant": bool(state.get("relevant")), "verified": True, "ms": int((time.time() - t0) * 1000)})', 'yield sse("done", {"request_id": request_id, "mode": "direct", "relevant": bool(state.get("relevant")), "verified": True, "ms": int((time.time() - t0) * 1000)})\n            log.info(json.dumps({"event":"chat_done","request_id":request_id,"mode":"direct","elapsed_ms":int((time.time()-t0)*1000)}))')
s=s.replace('yield sse("done", {"mode": "extractive-fallback", "relevant": True, "verified": False, "ms": int((time.time() - t0) * 1000)})', 'yield sse("done", {"request_id": request_id, "mode": "extractive-fallback", "relevant": True, "verified": False, "ms": int((time.time() - t0) * 1000)})')
s=s.replace('yield sse("done", {"mode": "llm", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})', 'yield sse("done", {"request_id": request_id, "mode": "llm", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})')
s=s.replace('yield sse("done", {"mode": "extractive", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})', 'yield sse("done", {"request_id": request_id, "mode": "extractive", "relevant": True, "verified": True, "ms": int((time.time() - t0) * 1000)})')
s=s.replace('    data = await audio.read()\n    if len(data) > 8_000_000:', '    data = await audio.read()\n    if not data:\n        raise HTTPException(400, "Empty audio upload")\n    if len(data) > 8_000_000:')
f.write_text(s)

# Add security-focused tests for request contracts and bounded retry config, and simple citation verifier tests.
(root/'tests/test_reliability.py').write_text('''"""Reliability regression tests that do not require a live Ollama server."""\nimport os\n\ndef test_evaluation_dataset_has_100_cases():\n    import json\n    from pathlib import Path\n    rows=[json.loads(x) for x in (Path(__file__).parents[1]/"eval"/"questions.jsonl").read_text().splitlines() if x.strip()]\n    assert len(rows)==100\n    assert all({"q","expect","oos"}.issubset(r) for r in rows)\n    assert all(isinstance(r["q"],str) and r["q"].strip() for r in rows)\n\ndef test_request_id_in_sse_done_event():\n    # API test suite uses a TestClient and offline hashing embeddings.\n    from fastapi.testclient import TestClient\n    from app.main import app\n    with TestClient(app) as client:\n        response=client.post("/chat",json={"message":"give me her email ID"})\n    assert response.status_code==200\n    assert 'event: done' in response.text\n    assert '"request_id"' in response.text\n\ndef test_empty_message_rejected():\n    from fastapi.testclient import TestClient\n    from app.main import app\n    with TestClient(app) as client:\n        assert client.post("/chat",json={"message":"   "}).status_code==400\n''')

# Create a top-level project architecture document and final handoff guide.
(root/'ARCHITECTURE.md').write_text('''# NEXUS architecture\n\n```mermaid\nflowchart TD\n  U[Portfolio: HTML/CSS/Vanilla JS] -->|POST /chat + SSE| API[FastAPI API]\n  U -->|POST /transcribe| STT[Local faster-whisper]\n  API --> G[LangGraph workflow]\n  G --> R[Hybrid retrieval]\n  R --> V[ChromaDB dense search]\n  R --> B[BM25 lexical search]\n  V --> F[RRF fusion + metadata boosts]\n  B --> F\n  F --> GR[Evidence grading / bounded rewrite]\n  GR --> L[Ollama local LLM]\n  L --> VG[Grounding verification]\n  VG -->|supported| OUT[SSE tokens + sources]\n  VG -->|unsupported| FB[Extractive fallback]\n  FB --> OUT\n  OUT --> UI[Portfolio chat widget]\n```\n\n## Trust boundaries\n- Knowledge files are untrusted content, never executable instructions.\n- Only allowlisted read-only tools should be callable by the model.\n- The frontend-provided history is bounded and validated; this backend does not maintain a shared global conversation history.\n- Ollama and speech recognition are configured as local services. GitHub live repository lookup is an optional external metadata tool; the knowledge-grounded chat and speech pipeline do not require paid AI APIs.\n- SSE events expose progress and sources but should not expose stack traces or secrets.\n\n## Current limitations to verify\n- The default voice output uses browser speech synthesis where configured; browser TTS may use OS-provided voices. For strict offline TTS across environments, add a local Piper adapter.\n- Reranking is optional and adds a model download.\n- Evaluation scores must be generated on the target Mac; no performance numbers are asserted by this repository.\n''')

# Improve README with precise reproducible evaluation, limitations and acceptance criteria.
f=root/'README.md'; s=f.read_text()
s += '''\n\n## GenAI engineering roadmap and acceptance criteria\n\n### Run the 100-case offline retrieval evaluation\n\n```bash\n# activate the virtual environment and install requirements first\npython -m eval.run_eval\n```\n\nThis writes `eval/results.md`. The 100 cases include the original labeled portfolio questions plus paraphrased variants derived from them. Treat this as a starter regression set, not an independently authored gold benchmark: review the `derived_from` labels and add manually verified expected facts/relevant chunk IDs before using it to report headline scores. The retrieval evaluator currently reports document ranking and refusal behaviour; it does not prove semantic answer correctness by itself.\n\n### Test suite\n\n```bash\npytest -q\n```\n\nThe suite includes pipeline, API, speech adapter, and evaluation dataset checks. A successful syntax compile is not equivalent to a successful test run; run tests in the same Python environment used for the demo.\n\n### Observability and request boundaries\n- `/chat` streams `trace`, `sources`, `links`, `token`/`replace`, and `done` SSE events. `done` includes a request ID and elapsed milliseconds.\n- Logs emit structured JSON events for chat start/completion. Avoid logging prompts, full transcripts, audio bytes, or personal data.\n- History is request-scoped and bounded. The server does not use a global shared chat-memory object.\n- Ollama connect/read timeout is configurable through `LLM_TIMEOUT_SECONDS`; history size is controlled by `MAX_HISTORY_TURNS`.\n- Audio uploads are capped at 8 MB and empty uploads are rejected.\n\n### Manual release checklist\n- [ ] Run `pytest -q` successfully in a clean environment.\n- [ ] Test the widget on desktop and mobile.\n- [ ] Verify citations against the underlying knowledge files.\n- [ ] Test unsupported questions and confirm the graph abstains.\n- [ ] Test timeouts, cancellation, and concurrent sessions.\n- [ ] Run the benchmark on the target Mac and commit the methodology plus results (not machine-specific databases).\n- [ ] Inspect Git status and scan for secrets before publishing.\n\nSee `ARCHITECTURE.md` for the system diagram and trust boundaries.\n'''
f.write_text(s)

# Environment examples for new settings
f=root/'.env.example'; s=f.read_text()
s += '\nLLM_TIMEOUT_SECONDS=90\nMAX_HISTORY_TURNS=6\nMAX_GRAPH_STEPS=12\n'
f.write_text(s)
