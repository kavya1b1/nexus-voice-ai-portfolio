"""Offline test-suite: uses the hashing embedder and a stub LLM, so no downloads or servers are needed."""
import os

os.environ["FORCE_HASHING_EMBEDDER"] = "1"

import pytest

from app.agent import VoiceAgent
from app.chunking import chunk_documents, load_documents
from app.config import Settings
from app.embeddings import get_embedder
from app.ingest import ensure_index
from app.retriever import HybridRetriever, tokenize


class StubLLM:
    def __init__(self, reply="", online=True):
        self.reply, self.online = reply, online

    def available(self):
        return self.online

    def complete(self, messages, max_tokens=None):
        return self.reply

    def stream(self, messages, max_tokens=None):
        for w in self.reply.split(" "):
            yield w + " "


@pytest.fixture(scope="module")
def settings(tmp_path_factory):
    return Settings(data_dir=tmp_path_factory.mktemp("data"), force_hashing_embedder=True)


@pytest.fixture(scope="module")
def retriever(settings):
    emb = get_embedder(settings)
    r = HybridRetriever(settings, emb)
    ensure_index(settings, emb, r, force=True)
    return r


@pytest.fixture()
def agent(retriever, settings):
    return VoiceAgent(retriever, StubLLM(online=False), settings)


# ── chunking ──────────────────────────────────────────────
def test_chunks_keep_metadata(settings):
    chunks = chunk_documents(load_documents(settings.knowledge_dir), 700, 80)
    assert len(chunks) > 15
    contact = [c for c in chunks if "contact" in c.tags]
    assert contact and all(c.anchor == "#contact" for c in contact)
    assert any(l["href"].startswith("mailto:") for c in contact for l in c.links)


def test_smaller_chunk_size_gives_more_chunks(settings):
    docs = load_documents(settings.knowledge_dir)
    assert len(chunk_documents(docs, 120, 20)) > len(chunk_documents(docs, 700, 80))


# ── retrieval regressions ─────────────────────────────────
@pytest.mark.parametrize("question,expected_title", [
    ("give me her email ID", "Contact, availability and resume"),   # the bug reported from the first version
    ("how can I reach her", "Contact, availability and resume"),
    ("which certifications does she have", "Certifications"),
    ("tell me about safesphere", "SafeSphere.AI moderation engine"),
    ("what is the proposal evaluator accuracy", "AI Proposal Evaluation System"),
    ("how does the n8n chrome extension work", "n8n Workflow Generator Chrome Extension"),
    ("what is her cgpa", "About Kavya"),
])
def test_top_hit_is_right_document(agent, question, expected_title):
    state = agent.plan(question)
    assert state["relevant"], state["trace"]
    assert state["hits"][0].chunk.title == expected_title


@pytest.mark.parametrize("question", ["what is the weather today", "who is the prime minister of india", "what is her favourite food"])
def test_off_topic_is_refused_without_calling_llm(agent, question):
    result = agent.answer(question)
    assert result["state"]["relevant"] is False
    assert "don't have that" in result["answer"]


def test_email_answer_contains_real_address(agent):
    assert "kavya1b1@gmail.com" in agent.answer("give me her email ID")["answer"]


# ── agent behaviour ───────────────────────────────────────
def test_smalltalk_skips_retrieval(agent):
    state = agent.plan("hello")
    assert state["route"] == "smalltalk" and "hits" not in state


def test_rewrite_loop_runs_once_then_stops(agent):
    state = agent.plan("what is her favourite food")
    nodes = [t["node"] for t in state["trace"]]
    assert nodes.count("rewrite") == 1 and nodes[-1] == "compose"


def test_followup_is_resolved_with_history(agent):
    history = [{"role": "user", "content": "tell me about safesphere"}, {"role": "assistant", "content": "SafeSphere is a moderation engine."}]
    state = agent.plan("what databases does it use", history)
    assert state["route"] == "followup" and [t["node"] for t in state["trace"]][:2] == ["route", "contextualize"]
    assert any("SafeSphere" in h.chunk.title for h in state["hits"])


def test_github_route_degrades_gracefully(agent, monkeypatch):
    import app.tools as tools
    monkeypatch.setattr(tools, "github_repos", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("offline")))
    state = agent.plan("show me her latest github repos")
    assert state["route"] == "github" and "couldn't reach GitHub" in state["direct"]


# ── verification guard ────────────────────────────────────
def test_verifier_catches_invented_numbers(agent, retriever):
    hits = retriever.search("proposal evaluator accuracy")
    assert agent.verify("The model reaches 91.3% accuracy [1].", hits).ok
    bad = agent.verify("The model reaches 99.9% accuracy [1].", hits)
    assert not bad.ok and any("99.9" in i for i in bad.issues)


def test_verifier_catches_invented_email(agent, retriever):
    hits = retriever.search("contact email")
    assert not agent.verify("Write to fake.person@example.com", hits).ok


def test_hallucinated_llm_answer_is_replaced(retriever, settings):
    lying = VoiceAgent(retriever, StubLLM("Kavya scored 99.9% accuracy and won a Nobel prize in physics."), settings)
    result = lying.answer("what is the proposal evaluator accuracy")
    assert result["mode"] == "extractive-fallback" and result["verified"] is False
    assert "91.3" in result["answer"]


def test_faithful_llm_answer_passes(retriever, settings):
    good = VoiceAgent(retriever, StubLLM("The ensemble model reaches 91.3% prediction accuracy [1]."), settings)
    result = good.answer("what is the proposal evaluator accuracy")
    assert result["mode"] == "llm" and result["verified"]


def test_tokenizer_handles_cpp():
    assert "cpp" in tokenize("Does she know C++?")


# ── detailed answers for broad project questions ──────────
def test_broad_project_question_gets_full_writeup(agent, retriever):
    state = agent.plan("tell me about safesphere")
    assert state["detail"] is True and state["max_tokens"] > 220
    assert len(state["hits"]) == len(retriever.doc_chunks("13-safesphere.md")) >= 3
    assert "full write-up" in state["trace"][-1]["detail"]


@pytest.mark.parametrize("question", [
    "what is the proposal evaluator accuracy", "which databases does safesphere use", "how fast is the moderation engine",
    "what is her cgpa", "does she know pytorch"])
def test_narrow_questions_stay_short(agent, question):
    assert agent.plan(question)["detail"] is False


def test_explicit_request_for_detail_on_a_non_project(agent):
    assert agent.plan("tell me about her skills in detail")["detail"] is True


def test_help_question_lists_topics(agent):
    result = agent.answer("what can I ask?")
    assert result["state"]["route"] == "smalltalk" and "ColdMail" in result["answer"] and "contact" in result["answer"]


def test_templates_are_not_indexed(settings):
    assert not any(c.source.startswith("_") for c in chunk_documents(load_documents(settings.knowledge_dir), 700, 80))
