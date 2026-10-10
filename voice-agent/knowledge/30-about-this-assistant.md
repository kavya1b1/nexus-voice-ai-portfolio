---
title: About this voice assistant
tags: [meta, assistant, rag, agentic-ai, voice]
anchor: "#top"
links: []
---
## What this assistant is
This voice assistant is one of Kavya's own AI projects. It is an agentic RAG system that answers questions about him using only a curated knowledge base, and it runs fully locally with free, open-source components.

## How it works
Questions go through a LangGraph agent that routes the request, retrieves evidence with hybrid search, grades whether the evidence is relevant, rewrites the query and retries if it is not, and then generates a grounded, cited answer with a local LLM served by Ollama. A verification step checks numbers and emails in the answer against the retrieved sources before it is spoken.

## Retrieval stack
Retrieval combines dense sentence embeddings stored in ChromaDB with BM25 keyword search, merged using reciprocal rank fusion and boosted by metadata tags. Optionally a cross-encoder re-ranks the candidates.

## Voice stack
Speech input can be transcribed locally with faster-whisper, or with the browser's speech recognition. Answers stream from a FastAPI server using server-sent events and are spoken sentence by sentence as they are generated, which keeps latency low. If the backend is offline, the website falls back to a lightweight in-browser mode.
