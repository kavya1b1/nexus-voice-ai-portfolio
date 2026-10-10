# Kavya's Voice Agent: agentic RAG, voice-first, 100% local and free

A voice assistant for a portfolio website. Visitors can **speak or type** and get answers about the owner's projects,
skills and experience, **grounded in a knowledge base**, with sources, with no paid API and no data leaving the machine.

```
 Browser (portfolio widget)                       Python backend (FastAPI)
┌──────────────────────────┐   audio   ┌────────────────────────────────────────────────────────────┐
│ mic ─ MediaRecorder ─────┼──────────►│ /transcribe  → faster-whisper (local STT)                  │
│ or Web Speech API        │   text    │                                                            │
│                          ├──────────►│ /chat  (Server-Sent Events)                                │
│ live "How I answered"    │◄──────────┤   LangGraph agent                                          │
│ trace + sources + links  │  trace    │    route ─► [contextualize] ─► retrieve ─► grade ─┐        │
│                          │  tokens   │                  ▲                                │        │
│ sentence-by-sentence TTS │           │                  └──── rewrite (retry) ◄── weak ──┤        │
│ (speechSynthesis)        │           │                                           relevant▼        │
└──────────────────────────┘           │   compose grounded prompt ─► Ollama LLM (streamed tokens)  │
   falls back to an in-browser         │   verify (numbers / emails / vocabulary vs. sources)       │
   keyword mode if backend is offline  │                                                            │
                                       │ Retrieval: ChromaDB dense  +  BM25  ─► RRF  ─► tag boost   │
                                       │            (+ optional cross-encoder re-rank)              │
                                       └────────────────────────────────────────────────────────────┘
```

## What makes it more than a chatbot

| Concept | Where |
|---|---|
| **Hybrid retrieval**: dense embeddings (ChromaDB, cosine) + BM25, merged with Reciprocal Rank Fusion | `app/retriever.py` |
| **Metadata-aware retrieval**: the router infers tag hints ("email" → `contact`) and boosts matching chunks | `app/agent.py`, `app/retriever.py` |
| **Agentic / corrective RAG**: LangGraph graph with routing, relevance grading, query rewriting and a bounded retry loop | `app/agent.py` |
| **Follow-up understanding**: pronouns ("what database does *it* use?") are resolved from chat history (LLM, or heuristic if offline) | `app/agent.py` |
| **Tool use**: live GitHub API for "latest repos", degrades gracefully when offline | `app/tools.py` |
| **Grounded generation with citations** using a local LLM (Ollama) and a strict system prompt | `app/prompts.py`, `app/llm.py` |
| **Hallucination guard**: every number and email in the answer must exist in the sources, otherwise the answer is replaced by an extractive one | `VoiceAgent.verify` |
| **Local speech-to-text** (faster-whisper) and **low-latency streaming**: SSE tokens, spoken sentence by sentence | `app/stt.py`, `app/main.py`, `js/voice-agent.js` |
| **Explainability**: the UI shows the agent's steps, similarity scores and sources for each answer | SSE `trace` / `sources` events |
| **Evaluation harness**: Hit@k, MRR, refusal accuracy, faithfulness, latency | `eval/run_eval.py` |
| **Tests**: 28 offline tests (stub LLM, no downloads), including a regression test for a real bug | `tests/` |
| **Guardrails**: input length cap, per-IP rate limit, CORS allow-list, validated history roles | `app/main.py` |

## Quick start

```bash
# 1. local LLM (free): https://ollama.com
ollama ls                          # default model is llama3:latest; use any model you already have:
                                   #   LLM_MODEL=gemma:latest uvicorn app.main:app --port 8000
                                   # (no model yet? `ollama pull llama3.2:3b`, ~2 GB)

# 2. backend
cd voice-agent
python -m venv .venv && source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m app.ingest                                      # builds the vector index (downloads the embedding model once)
uvicorn app.main:app --port 8000

# 3. website
cd ../kavya2 && python -m http.server 5500                # open http://localhost:5500 and click "Ask my AI"
```
The widget detects the backend at `http://localhost:8000` automatically. The header shows **Agent · local LLM** when it
is connected, or **Offline mode** when it falls back to the built-in keyword assistant.

**Richer answers:** broad project questions ("tell me about X") pull in the project's *whole* write-up and allow a 5 to 7 sentence answer; narrow ones ("which database does it use?") stay short. So the answer is only as detailed as the file in `knowledge/`: copy `knowledge/_project-template.md`, or paste a project's README text into a new file, then run `python -m app.ingest`.

**Knowledge base:** put Markdown, `.txt` or **PDF** files (your resume!) in `knowledge/` and run `python -m app.ingest`
(the server also re-indexes automatically at start-up when files change). Markdown front matter (`tags`, `anchor`,
`links`) controls tag boosting and the buttons shown under answers.

## Evaluate (run this on your machine and quote *your* numbers)

```bash
python -m eval.run_eval            # retrieval + refusal metrics, no LLM needed
python -m eval.run_eval --llm      # adds faithfulness and latency with your Ollama model
pytest                             # 28 tests
```
`eval/questions.jsonl` has 43 in-scope paraphrased questions and 10 off-topic ones. Add your own. The report prints the
similarity distribution of on-topic vs off-topic queries so you can set `MIN_DENSE_SIM` for your embedding model.

## Making it available to portfolio visitors, for free

The backend needs a machine that can run a small LLM. Options at zero cost:
1. **Demo from your laptop**: run it locally and share the portfolio live or screen-record it for your resume/LinkedIn.
2. **Cloudflare Quick Tunnel**: `cloudflared tunnel --url http://localhost:8000` gives a temporary public HTTPS URL; put it in
   `CONFIG.apiBase` in `js/voice-agent.js` and set `ALLOWED_ORIGINS` to your site. Works while your machine is on.
3. **No backend at all**: the site still works in Offline mode (keyword matching, browser TTS/STT).

## Design decisions (good interview material)

* **Why hybrid search?** Dense embeddings handle paraphrase ("college" ↔ "education"); BM25 nails exact tokens (names, "DP-900", "91.3%").
  RRF fuses ranks, so no score calibration is needed between the two.
* **Why LangGraph only for planning, with generation outside the graph?** Token streaming and post-hoc verification are
  simpler and faster outside the state machine, and the graph stays deterministic and unit-testable.
* **Why a rule-based router?** Small local LLMs are unreliable at tool-calling; a deterministic router is instant, testable
  and never mis-routes "hello" through the LLM. The LLM is used where it is strong: rewriting and phrasing.
* **Why verify numbers instead of trusting the model?** For a portfolio, a wrong metric is worse than no answer.
* **Known limits:** the verifier checks numbers, emails and vocabulary, not full entailment; the router is regex-based;
  English only; CPU inference with a 3B model takes a few seconds per answer.
* **Next steps:** NLI-based faithfulness check, multilingual (Hindi/Hinglish) via Whisper `small`, Piper for local neural TTS, conversation memory.


## GenAI engineering roadmap and acceptance criteria

### Run the 100-case offline retrieval evaluation

```bash
# activate the virtual environment and install requirements first
python -m eval.run_eval
```

This writes `eval/results.md`. The 100 cases include the original labeled portfolio questions plus paraphrased variants derived from them. Treat this as a starter regression set, not an independently authored gold benchmark: review the `derived_from` labels and add manually verified expected facts/relevant chunk IDs before using it to report headline scores. The retrieval evaluator currently reports document ranking and refusal behaviour; it does not prove semantic answer correctness by itself.

### Test suite

```bash
pytest -q
```

The suite includes pipeline, API, speech adapter, and evaluation dataset checks. A successful syntax compile is not equivalent to a successful test run; run tests in the same Python environment used for the demo.

### Observability and request boundaries
- `/chat` streams `trace`, `sources`, `links`, `token`/`replace`, and `done` SSE events. `done` includes a request ID and elapsed milliseconds.
- Logs emit structured JSON events for chat start/completion. Avoid logging prompts, full transcripts, audio bytes, or personal data.
- History is request-scoped and bounded. The server does not use a global shared chat-memory object.
- Ollama connect/read timeout is configurable through `LLM_TIMEOUT_SECONDS`; history size is controlled by `MAX_HISTORY_TURNS`.
- Audio uploads are capped at 8 MB and empty uploads are rejected.

### Manual release checklist
- [ ] Run `pytest -q` successfully in a clean environment.
- [ ] Test the widget on desktop and mobile.
- [ ] Verify citations against the underlying knowledge files.
- [ ] Test unsupported questions and confirm the graph abstains.
- [ ] Test timeouts, cancellation, and concurrent sessions.
- [ ] Run the benchmark on the target Mac and commit the methodology plus results (not machine-specific databases).
- [ ] Inspect Git status and scan for secrets before publishing.

See `ARCHITECTURE.md` for the system diagram and trust boundaries.


### Profile updates

The portfolio knowledge base uses he/him pronouns for Kavya. If you edit files under `knowledge/`, rebuild the local retrieval index with `python -m app.ingest` before testing. The browser-side portfolio knowledge in `kavya2/js/kb.js` is maintained separately and should be kept in sync.
