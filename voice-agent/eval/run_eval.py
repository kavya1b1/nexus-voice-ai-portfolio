"""Offline evaluation of the retrieval + agent pipeline.

    python -m eval.run_eval              # retrieval metrics + refusal accuracy (no LLM needed)
    python -m eval.run_eval --llm        # also measure answer faithfulness and latency with Ollama

Metrics
  Hit@1 / Hit@3 / MRR   did the right document come back first / in the top 3 (in-scope questions)
  Refusal accuracy      off-topic questions the agent correctly declined instead of guessing
  Faithfulness          share of LLM answers whose numbers/emails/vocabulary are supported by the sources
Use the printed similarity distributions to choose MIN_DENSE_SIM for your embedding model.
"""
from __future__ import annotations

import argparse
import json
import statistics as st
import time
from pathlib import Path

from app.agent import VoiceAgent
from app.config import get_settings
from app.embeddings import get_embedder
from app.ingest import ensure_index
from app.llm import OllamaLLM
from app.retriever import HybridRetriever

HERE = Path(__file__).parent


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--llm", action="store_true", help="also run generation with the local Ollama model")
    args = ap.parse_args()

    s = get_settings()
    emb = get_embedder(s)
    ret = HybridRetriever(s, emb)
    ensure_index(s, emb, ret)
    llm = OllamaLLM(s) if args.llm else None
    if args.llm and not llm.available():
        raise SystemExit(f"Ollama model '{s.llm_model}' is not available. Run: ollama pull {s.llm_model}")
    agent = VoiceAgent(ret, llm, s)

    rows = [json.loads(l) for l in (HERE / "questions.jsonl").read_text().splitlines() if l.strip()]
    inscope = [r for r in rows if not r["oos"]]
    oos = [r for r in rows if r["oos"]]

    ranks, in_sims, misses = [], [], []
    for r in inscope:
        state = agent.plan(r["q"])
        titles = [h.chunk.title for h in state.get("hits", [])]
        rank = titles.index(r["expect"]) + 1 if r["expect"] in titles else None
        ranks.append(rank)
        in_sims.append(max((h.dense_sim for h in state.get("hits", [])), default=0.0))
        if rank != 1:
            misses.append((r["q"], r["expect"], titles[:3]))

    refused, oos_sims, leaks = 0, [], []
    for r in oos:
        state = agent.plan(r["q"])
        oos_sims.append(max((h.dense_sim for h in state.get("hits", [])), default=0.0))
        if not state.get("relevant"):
            refused += 1
        else:
            leaks.append(r["q"])

    n = len(inscope)
    hit1 = sum(1 for x in ranks if x == 1) / n
    hit3 = sum(1 for x in ranks if x) / n
    mrr = sum(1 / x for x in ranks if x) / n
    lines = [
        f"# Evaluation · embeddings `{emb.name}` · {len(ret)} chunks · {n} in-scope + {len(oos)} off-topic questions", "",
        "| Metric | Value |", "|---|---|",
        f"| Hit@1 | {hit1:.1%} |", f"| Hit@3 | {hit3:.1%} |", f"| MRR | {mrr:.3f} |",
        f"| Refusal accuracy (off-topic) | {refused}/{len(oos)} = {refused / len(oos):.1%} |",
        f"| Dense similarity, in-scope (median) | {st.median(in_sims):.3f} |",
        f"| Dense similarity, off-topic (median) | {st.median(oos_sims):.3f} |",
    ]

    if args.llm:
        verified, lat, fallbacks = 0, [], 0
        for r in inscope:
            t0 = time.time()
            res = agent.answer(r["q"])
            lat.append(time.time() - t0)
            verified += res["verified"]
            fallbacks += res["mode"] == "extractive-fallback"
        lines += [f"| Faithfulness (verified answers) | {verified}/{n} = {verified / n:.1%} |",
                  f"| Answers replaced by extractive fallback | {fallbacks}/{n} |",
                  f"| Latency per answer, median / p95 | {st.median(lat):.1f}s / {sorted(lat)[int(0.95 * (len(lat) - 1))]:.1f}s |",
                  f"| LLM | `{s.llm_model}` via Ollama |"]

    if misses:
        lines += ["", "## Retrieval misses (not ranked first)", ""] + [f"- “{q}” → expected **{e}**, got {got}" for q, e, got in misses]
    if leaks:
        lines += ["", "## Off-topic questions that were NOT refused", ""] + [f"- “{q}”" for q in leaks]

    report = "\n".join(lines)
    print(report)
    (HERE / "results.md").write_text(report + "\n")


if __name__ == "__main__":
    main()
