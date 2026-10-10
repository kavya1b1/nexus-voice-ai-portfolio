"""The agent: a LangGraph state machine for *planning and retrieval*, then grounded generation and verification.

    route ─┬─ smalltalk ─────────────────────────────► END   (instant reply, no LLM)
           ├─ github ──► tool (live GitHub API) ─────► END
           ├─ followup ─► contextualize (resolve "it"/"that" from history) ─┐
           └─ kb ───────────────────────────────────────────────────────────┴► retrieve ──► grade ─┬─ relevant ──────────► compose ─► END
                        ▲                ├─ weak, retries left ─► rewrite ─┐
                        └────────────────┴──────────────────────────────◄──┘
                                         └─ weak, no retries ──► compose (polite "I don't know")

`compose` builds the grounded prompt. The API layer then streams the LLM's tokens and finally runs `verify`,
which checks numbers / emails / vocabulary in the answer against the retrieved sources. If the check fails the
answer is replaced with an extractive one taken straight from the sources.
"""
from __future__ import annotations

import operator
import re
from dataclasses import dataclass, field
from typing import Annotated, Any, Iterator, TypedDict

from langgraph.graph import END, StateGraph

from . import tools
from .config import Settings
from .prompts import DETAILED_PROMPT, NO_ANSWER, REWRITE_PROMPT, SYSTEM_PROMPT
from .retriever import Hit, HybridRetriever, tokenize

# ── routing rules ─────────────────────────────────────────
GREET = re.compile(r"^(hi+|hello+|hey+|hola|namaste|yo|good\s(morning|afternoon|evening))\b[\s!.,]*$", re.I)
THANKS = re.compile(r"^(thanks|thank you|thx|great|awesome|cool|nice|perfect|wonderful|got it|ok|okay)(\s+(a lot|so much))?\W*$", re.I)
BYE = re.compile(r"^(bye|goodbye|see you|that'?s all|no thanks|nothing else|quit|exit)\W*$", re.I)
# Explicitly route common unsupported live/personal facts to a safe refusal.
OUT_OF_SCOPE = re.compile(
    r"\b(time right now|what time is it|current time|today'?s date|current date|"
    r"weather today|current weather|forecast|favourite colour|favorite color|"
    r"favourite color|favorite colour|his favourite|his favorite|latest news|stock price)\b",
    re.I,
)
GITHUB_LIVE = re.compile(r"(latest|recent|newest|updated).*(repo|repos|repositories|github)|github (repos|repositories|activity)", re.I)
HELP = re.compile(r"(what (can|could|should|do) (i|we) (ask|say)|what (can|do) you (do|know|answer|help)|how can you help|what (topics|questions)|suggest.{0,20}question|example questions?|^help\W*$)", re.I)
HELP_TEXT = ("You can ask me about Kavya's background and education, his hackathon achievements and leadership, his skills and tech stack, "
             "his certifications, and his four main projects in detail: the AI Proposal Evaluation System, Autonomous ColdMail AI, the n8n Workflow Generator "
             "and SafeSphere. You can also ask how I was built, for his latest GitHub repositories, or how to contact him. "
             "For example: tell me about ColdMail AI, which databases does he use, how accurate is the proposal evaluator, or is he open to internships?")
# questions that ask for one specific fact get a short answer; broad ones about a project get the full write-up
NARROW = re.compile(r"\b(accura\w*|how (fast|many|much|long|accurate|big)|which|what (stack|database|model|api|llm|language)|stack|tech\w*|latency|speed|number|metric\w*|github|link|repo\w*|cost|time|database\w*|framework\w*|language\w*|librar\w*|tools?|uses?|used)\b", re.I)
DETAIL_WORDS = re.compile(r"\b(in detail|detailed|elaborate|in depth|walk me through|explain (more|further)|full (story|picture)|deep dive)\b", re.I)
PRONOUN = re.compile(r"\b(it|its|that|this|those|these|that one|this one|the same|more)\b", re.I)

# keyword → tag hints used to boost metadata-matching chunks (self-query style)
TAG_HINTS: list[tuple[re.Pattern, str]] = [
    (re.compile(r"\b(e-?mail (id|address)|mail id|(his|your|the) e-?mail\b|phone|number|linkedin|contact|reach|connect|resume|cv|hire|hiring|intern(ship)?|available|availability|opportunit)", re.I), "contact"),
    (re.compile(r"\b(certif|credential|ibm|oracle|azure|microsoft)", re.I), "certifications"),
    (re.compile(r"\b(skill|stack|technolog|language|framework|database|tools?)\b", re.I), "skills"),
    (re.compile(r"\b(project|built|build|github|repo)\b", re.I), "project"),
    (re.compile(r"\b(education|college|university|cgpa|gpa|degree|vit)\b", re.I), "education"),
    (re.compile(r"\b(hackathon|achievement|award|won|sih|cybershield)", re.I), "achievements"),
    (re.compile(r"\b(this (ai )?(assistant|agent|bot|chatbot)|you work|are you|your (stack|architecture)|voice agent)\b", re.I), "meta"),
]


class AgentState(TypedDict, total=False):
    question: str
    history: list[dict]
    route: str  # smalltalk | github | followup | kb
    tags: list[str]
    query: str
    attempts: int
    hits: list[Hit]
    relevant: bool
    direct: str | None
    tool: dict | None
    messages: list[dict]
    detail: bool
    max_tokens: int
    trace: Annotated[list, operator.add]


@dataclass
class Verdict:
    ok: bool
    issues: list[str] = field(default_factory=list)


def _tags_for(text: str) -> list[str]:
    return sorted({tag for rx, tag in TAG_HINTS if rx.search(text)})


def _content_tokens(text: str) -> list[str]:
    return tokenize(text)


class VoiceAgent:
    def __init__(self, retriever: HybridRetriever, llm: Any, settings: Settings):
        self.retriever = retriever
        self.llm = llm
        self.s = settings
        self.graph = self._build_graph()

    # ── graph nodes ───────────────────────────────────────
    def _route(self, st: AgentState) -> dict:
        q = st["question"].strip()
        if GREET.match(q):
            route, direct = "smalltalk", "Hello! I'm Kavya's AI assistant. Ask me about his projects, skills, achievements, or say 'give me a quick intro'."
        elif THANKS.match(q):
            route, direct = "smalltalk", "You're welcome! Anything else you'd like to know about Kavya?"
        elif BYE.match(q):
            route, direct = "smalltalk", "Thanks for stopping by! If you'd like to talk to Kavya, the contact form is at the bottom of the page."
        elif HELP.search(q):
            route, direct = "smalltalk", HELP_TEXT
        elif OUT_OF_SCOPE.search(q):
            route, direct = "smalltalk", NO_ANSWER
        elif GITHUB_LIVE.search(q):
            route, direct = "github", None
        elif st.get("history") and PRONOUN.search(q):
            route, direct = "followup", None
        else:
            route, direct = "kb", None
        tags = _tags_for(q)
        return {"route": route, "direct": direct, "tags": tags, "query": q, "attempts": 0,
                "trace": [{"node": "route", "detail": f"{route}" + (f" · tag hints: {', '.join(tags)}" if tags and route in ("kb", "followup") else "")}]}

    def _tool(self, st: AgentState) -> dict:
        try:
            repos = tools.github_repos(self.s.github_user)
            return {"direct": tools.speakable_repo_list(repos),
                    "tool": {"name": "github_repos", "links": [{"label": r["name"], "href": r["url"]} for r in repos]},
                    "trace": [{"node": "tool", "detail": f"github_repos → {len(repos)} repositories (live API)"}]}
        except Exception as exc:
            return {"direct": f"I couldn't reach GitHub right now, but all of Kavya's code is at github.com slash {self.s.github_user}.",
                    "tool": {"name": "github_repos", "links": [{"label": "GitHub", "href": f"https://github.com/{self.s.github_user}"}]},
                    "trace": [{"node": "tool", "detail": f"github_repos failed: {type(exc).__name__}"}]}

    def _retrieve(self, st: AgentState) -> dict:
        hits = self.retriever.search(st["query"], tags=set(st.get("tags", [])))
        top = hits[0].brief() if hits else None
        detail = (f"hybrid search (dense + BM25 → RRF) for “{st['query']}” → top: {top['title']} · {top['section']}" if top else "no results")
        return {"hits": hits, "trace": [{"node": "retrieve", "detail": detail}]}

    def _grade(self, st: AgentState) -> dict:
        hits = st.get("hits", [])
        if not hits:
            return {"relevant": False, "trace": [{"node": "grade", "detail": "no evidence found"}]}
        qtok = set(_content_tokens(st["query"]))
        # Score each passage independently; unrelated chunks must not combine to
        # manufacture keyword overlap for an out-of-scope question.
        candidates = []
        for hit in hits:
            ctok = set(_content_tokens(hit.chunk.embed_text))
            overlap = len(qtok & ctok) / len(qtok) if qtok else 0.0
            candidates.append((hit, overlap))
        best_hit, best_overlap = max(candidates, key=lambda item: item[1])
        sim = best_hit.dense_sim
        semantic_ok = sim >= self.retriever.min_sim
        lexical_ok = best_overlap >= 0.40
        exact_match_ok = best_overlap >= 0.75
        relevant = bool(qtok) and ((semantic_ok and lexical_ok) or exact_match_ok)
        return {"relevant": relevant,
                "trace": [{"node": "grade", "detail": f"{'relevant' if relevant else 'weak evidence'} · best passage similarity {sim:.2f} (threshold {self.retriever.min_sim:.2f}) · best-passage keyword overlap {best_overlap:.0%}"}]}

    def _resolve(self, question: str, history: list[dict]) -> tuple[str, str]:
        """Turn a follow-up ("what databases does it use?") into a standalone query using the chat history."""
        try:
            if self.llm is not None and self.llm.available():
                convo = "\n".join(f"{t['role']}: {t['content']}" for t in history[-4:])
                out = self.llm.complete([{"role": "system", "content": REWRITE_PROMPT},
                                         {"role": "user", "content": f"{convo}\nuser: {question}"}]).strip().strip('"')
                if out:
                    return out, "LLM rewrite"
        except Exception:
            pass
        last_user = next((t["content"] for t in reversed(history) if t["role"] == "user"), "")
        return f"{question} {last_user}".strip(), "heuristic: appended previous question"

    def _contextualize(self, st: AgentState) -> dict:
        new, how = self._resolve(st["question"], st.get("history", []))
        return {"query": new, "trace": [{"node": "contextualize", "detail": f"follow-up detected ({how}) → “{new}”"}]}

    def _rewrite(self, st: AgentState) -> dict:
        """Retry path after weak evidence: reformulate the query, then search again."""
        q = st["query"]
        if st.get("history"):
            new, how = self._resolve(st["question"], st["history"])
        else:
            new, how = " ".join(_content_tokens(q)) or q, "keyword reformulation"
        return {"query": new, "attempts": st.get("attempts", 0) + 1,
                "trace": [{"node": "rewrite", "detail": f"{how} → “{new}”"}]}

    def _wants_detail(self, question: str, hits: list[Hit]) -> bool:
        """Broad question about a project (or an explicit 'in detail') -> give the full write-up."""
        top = hits[0].chunk
        if len(self.retriever.doc_chunks(top.source)) < 2:
            return False
        if DETAIL_WORDS.search(question):
            return True
        return "project" in top.tags and not NARROW.search(question)

    def _compose(self, st: AgentState) -> dict:
        if not st.get("relevant"):
            return {"direct": NO_ANSWER, "trace": [{"node": "compose", "detail": "no grounded evidence → polite refusal (no hallucination)"}]}
        hits = st["hits"]
        detail = self._wants_detail(st["question"], hits)
        note = f"grounded prompt with {len(hits)} passages"
        if detail:  # parent-document retrieval: pull in every section of the matched document
            by_id = {h.chunk.id: h for h in hits}
            hits = [by_id.get(c.id) or Hit(c) for c in self.retriever.doc_chunks(hits[0].chunk.source)]
            note = f"detailed answer → expanded to the full write-up ({len(hits)} passages)"
        ctx = "\n\n".join(f"[{i}] {h.chunk.title} - {h.chunk.section}: {h.text}" for i, h in enumerate(hits, 1))
        msgs = [{"role": "system", "content": DETAILED_PROMPT if detail else SYSTEM_PROMPT}]
        msgs += [{"role": t["role"], "content": t["content"]} for t in st.get("history", [])[-4:]]
        msgs.append({"role": "user", "content": f"Context passages:\n{ctx}\n\nQuestion: {st['question']}"})
        return {"messages": msgs, "hits": hits, "detail": detail, "max_tokens": 480 if detail else self.s.llm_max_tokens,
                "trace": [{"node": "compose", "detail": note}]}

    # ── graph wiring ──────────────────────────────────────
    def _build_graph(self):
        g = StateGraph(AgentState)
        for name, fn in [("route", self._route), ("tool", self._tool), ("contextualize", self._contextualize), ("retrieve", self._retrieve),
                         ("grade", self._grade), ("rewrite", self._rewrite), ("compose", self._compose)]:
            g.add_node(name, fn)
        g.set_entry_point("route")
        g.add_conditional_edges("route", lambda s: s["route"],
                                {"smalltalk": END, "github": "tool", "kb": "retrieve", "followup": "contextualize"})
        g.add_edge("contextualize", "retrieve")
        g.add_edge("tool", END)
        g.add_edge("retrieve", "grade")
        g.add_conditional_edges("grade", lambda s: "compose" if s["relevant"] or s["attempts"] >= self.s.max_rewrites else "rewrite",
                                {"compose": "compose", "rewrite": "rewrite"})
        g.add_edge("rewrite", "retrieve")
        g.add_edge("compose", END)
        return g.compile()

    # ── public API ────────────────────────────────────────
    def plan_stream(self, question: str, history: list[dict] | None = None) -> Iterator[tuple[str, dict]]:
        """Yield (node_name, state_update) as the graph executes, so the UI can show live progress."""
        init = {"question": question, "history": history or [], "trace": []}
        for step in self.graph.stream(init, stream_mode="updates"):
            for node, update in step.items():
                yield node, update

    @staticmethod
    def merge(state: dict, update: dict) -> None:
        for k, v in update.items():
            if k == "trace":
                state.setdefault("trace", []).extend(v)
            else:
                state[k] = v

    def plan(self, question: str, history: list[dict] | None = None) -> dict:
        state: dict = {"question": question, "history": history or []}
        for _, update in self.plan_stream(question, history):
            self.merge(state, update)
        return state

    # ── generation helpers ────────────────────────────────
    def extractive_answer(self, question: str, hits: list[Hit], max_sentences: int = 3) -> str:
        """No-LLM fallback: pick the sentences from the retrieved passages that best match the question."""
        if not hits:
            return NO_ANSWER
        qtok = set(_content_tokens(question))
        cands = []
        for rank, h in enumerate(hits):
            context = set(_content_tokens(f"{h.chunk.title} {h.chunk.section}"))  # the chunk's title/section give each sentence its context
            for i, sent in enumerate(re.split(r"(?<=[.!?])\s+", h.text)):
                stoks = set(_content_tokens(sent))
                cands.append((len(qtok & (stoks | context)), len(qtok & stoks) - 0.1 * rank, rank, i, sent))
        best = sorted(cands, key=lambda c: (-c[0], -c[1]))[:max_sentences]
        return " ".join(c[4] for c in sorted(best, key=lambda c: (c[2], c[3])))

    def verify(self, answer: str, hits: list[Hit]) -> Verdict:
        """Cheap faithfulness guard: every number / email in the answer must appear in the sources."""
        clean = re.sub(r"\[\d+\]", "", answer)
        ctx_raw = " ".join(h.chunk.embed_text for h in hits).lower()
        ctx = ctx_raw.replace(",", "")
        issues = []
        for num in set(re.findall(r"\d[\d,]*(?:\.\d+)?", clean)):
            n = num.replace(",", "").rstrip(".")
            if n and n not in ctx:
                issues.append(f"number '{num}' not found in sources")
        for mail in set(re.findall(r"[\w.+-]+@[\w-]+\.[\w.]+", clean)):
            if mail.lower().rstrip(".") not in ctx_raw:
                issues.append(f"email '{mail}' not found in sources")
        atok = set(_content_tokens(clean))
        if atok:
            support = len(atok & set(_content_tokens(ctx_raw))) / len(atok)
            if support < 0.5:
                issues.append(f"only {support:.0%} of answer vocabulary is supported by sources")
        return Verdict(ok=not issues, issues=issues)

    def answer(self, question: str, history: list[dict] | None = None) -> dict:
        """Blocking end-to-end call, used by the evaluation harness and the tests."""
        state = self.plan(question, history)
        if state.get("direct"):
            return {"answer": state["direct"], "verified": True, "issues": [], "state": state, "mode": "direct"}
        mode = "extractive"
        text = ""
        if self.llm is not None and self.llm.available():
            try:
                text, mode = self.llm.complete(state["messages"], max_tokens=state.get("max_tokens")), "llm"
            except Exception:
                text = ""
        if text:
            verdict = self.verify(text, state["hits"])
            if not verdict.ok:
                return {"answer": self.extractive_answer(question, state["hits"], 6 if state.get("detail") else 3), "verified": False, "issues": verdict.issues,
                        "state": state, "mode": "extractive-fallback"}
            return {"answer": text, "verified": True, "issues": [], "state": state, "mode": mode}
        return {"answer": self.extractive_answer(question, state["hits"], 6 if state.get("detail") else 3), "verified": True, "issues": [], "state": state, "mode": mode}
