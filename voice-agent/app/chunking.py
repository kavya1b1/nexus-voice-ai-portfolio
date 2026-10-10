"""Document loading and chunking.

Knowledge lives in ./knowledge as Markdown (with optional YAML front matter),
plain text, or PDF (drop your resume in there). Markdown is split on `##`
headings first, then recursively by size, so every chunk stays on one topic.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class Chunk:
    id: str
    text: str                      # what is shown / spoken / cited
    title: str                     # document title
    section: str                   # heading inside the document
    source: str                    # file name
    tags: list[str] = field(default_factory=list)
    anchor: str = ""
    links: list[dict] = field(default_factory=list)

    @property
    def embed_text(self) -> str:
        """Title and section are prepended so short chunks keep their context."""
        return f"{self.title} - {self.section}\n{self.text}"

    def to_metadata(self) -> dict:
        # Chroma metadata must be flat scalars
        return {"title": self.title, "section": self.section, "source": self.source,
                "tags": ",".join(self.tags), "anchor": self.anchor, "links": json.dumps(self.links)}

    @classmethod
    def from_store(cls, cid: str, text: str, meta: dict) -> "Chunk":
        return cls(id=cid, text=text, title=meta.get("title", ""), section=meta.get("section", ""),
                   source=meta.get("source", ""), tags=[t for t in meta.get("tags", "").split(",") if t],
                   anchor=meta.get("anchor", ""), links=json.loads(meta.get("links") or "[]"))


_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)


def _parse_markdown(raw: str) -> tuple[dict, str]:
    m = _FRONT.match(raw)
    if not m:
        return {}, raw
    return (yaml.safe_load(m.group(1)) or {}), raw[m.end():]


def _read_pdf(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join((p.extract_text() or "") for p in PdfReader(str(path)).pages)


def load_documents(directory: Path) -> list[tuple[Path, dict, str]]:
    docs = []
    for path in sorted(directory.glob("*")):
        if path.name.startswith(("_", ".")):  # templates and hidden files are not knowledge
            continue
        if path.suffix.lower() == ".md":
            meta, body = _parse_markdown(path.read_text(encoding="utf-8"))
        elif path.suffix.lower() == ".txt":
            meta, body = {}, path.read_text(encoding="utf-8")
        elif path.suffix.lower() == ".pdf":
            meta, body = {"tags": ["resume"]}, _read_pdf(path)
        else:
            continue
        if body.strip():
            meta.setdefault("title", path.stem.replace("-", " ").replace("_", " ").title())
            docs.append((path, meta, body))
    return docs


def _split_sections(body: str) -> list[tuple[str, str]]:
    parts = re.split(r"^##\s+(.*)$", body, flags=re.M)
    if len(parts) == 1:
        return [("Overview", body.strip())]
    out = []
    lead = parts[0].strip()
    if lead:
        out.append(("Overview", lead))
    for i in range(1, len(parts), 2):
        out.append((parts[i].strip(), parts[i + 1].strip()))
    return out


def _recursive_split(text: str, size: int, overlap: int) -> list[str]:
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) <= size:
        return [text] if text else []
    sentences = re.split(r"(?<=[.!?])\s+", text)
    chunks, cur = [], ""
    for s in sentences:
        if cur and len(cur) + len(s) + 1 > size:
            chunks.append(cur)
            cur = cur[-overlap:].split(" ", 1)[-1] + " " + s if overlap else s
        else:
            cur = f"{cur} {s}".strip()
    if cur:
        chunks.append(cur)
    return chunks


def chunk_documents(docs, size: int = 700, overlap: int = 80) -> list[Chunk]:
    chunks: list[Chunk] = []
    for path, meta, body in docs:
        slug = re.sub(r"[^a-z0-9]+", "-", path.stem.lower()).strip("-")
        n = 0
        for section, text in _split_sections(body):
            for piece in _recursive_split(text, size, overlap):
                chunks.append(Chunk(
                    id=f"{slug}-{n}", text=piece, title=str(meta["title"]), section=section, source=path.name,
                    tags=[str(t) for t in meta.get("tags", [])], anchor=str(meta.get("anchor", "")),
                    links=list(meta.get("links") or [])))
                n += 1
    return chunks


def knowledge_fingerprint(directory: Path, embed_name: str, size: int, overlap: int) -> str:
    h = hashlib.sha256(f"{embed_name}|{size}|{overlap}".encode())
    for p in sorted(directory.glob("*")):
        if p.is_file():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]
