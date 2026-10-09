import re, json, pathlib, datetime
from typing import Any
import chromadb
from core.logger import log

DOCS = pathlib.Path("data/internal_docs")
OFFICIAL = ("product_doc", "config")
INFORMAL = ("meeting_transcript", "email_thread")
STALE_DAYS = 365
DEFAULT_MAX_DISTANCE = 1.2   # first guess from 6 test queries; recalibrate if docs or model change
_db = chromadb.PersistentClient(path="chroma_db")


def parse(path: pathlib.Path):
    raw = path.read_text(encoding="utf-8")
    m = re.match(r"---\n(.*?)\n---\n(.*)", raw, re.S)
    if m is None:
        raise ValueError(f"{path.name}: missing the '---' header block at the top of the file")
    meta = {}
    for line in m.group(1).splitlines():
        k, v = line.split(":", 1)
        meta[k.strip()] = v.strip()
    return meta, m.group(2).strip()


def _split_size(text: str, max_chars: int = 700) -> list[str]:
    out, text = [], text.strip()
    while len(text) > max_chars:
        cut = text.rfind(". ", 0, max_chars) + 1 or max_chars
        out.append(text[:cut].strip())
        text = text[cut:].strip()
    if text:
        out.append(text)
    return out


def chunk_sections(body: str) -> list[str]:
    """Docs and configs: one chunk per heading section."""
    out = []
    for sec in re.split(r"\n(?=#+ )", body):
        out += _split_size(sec)
    return out


def chunk_turns(body: str, per: int = 6, overlap: int = 1) -> list[str]:
    """Transcripts: groups of speaker turns with a one-turn overlap."""
    turns = [l.strip() for l in body.splitlines() if l.strip()]
    chunks, i = [], 0
    while i < len(turns):
        chunks.append("\n".join(turns[i:i + per]))
        if i + per >= len(turns):
            break
        i += per - overlap
    return chunks


def chunk_emails(body: str) -> list[str]:
    """Email threads: one chunk per message, each prefixed with the subject."""
    lines = body.strip().splitlines()
    subject = lines[0] if lines and lines[0].startswith("Subject:") else ""
    rest = "\n".join(lines[1:]) if subject else body
    msgs = [m.strip() for m in re.split(r"\n(?=From: )", rest) if m.strip()]
    return [f"{subject}\n{m}" for m in msgs]


CHUNKERS = {
    "product_doc": chunk_sections,
    "config": chunk_sections,
    "meeting_transcript": chunk_turns,
    "email_thread": chunk_emails,
}


def build_index() -> int:
    """Index everything, including superseded docs (filtered out at query time)."""
    try:
        _db.delete_collection("internal")
    except Exception:
        pass
    col = _db.create_collection("internal")
    n = 0
    for p in sorted(DOCS.glob("*.md")):
        meta, body = parse(p)
        for i, c in enumerate(CHUNKERS[meta["doc_type"]](body)):
            col.add(ids=[f"{meta['doc_id']}#{i}"], documents=[c],
                    metadatas=[{**meta, "chunk": i}])
            n += 1
    log("index_built", chunks=n)
    return n


def search(query: str, product: str | None = None, k: int = 4,
           doc_types: tuple = OFFICIAL, include_superseded: bool = False) -> list[dict]:
    col = _db.get_collection("internal")
    conds: list[dict] = []
    if not include_superseded:
        conds.append({"status": "current"})
    if product:
        conds.append({"product": {"$in": [product, "all"]}})
    if doc_types:
        conds.append({"doc_type": {"$in": list(doc_types)}})
    where: Any = None if not conds else (conds[0] if len(conds) == 1 else {"$and": conds})

    max_distance : float | None = DEFAULT_MAX_DISTANCE

    res = col.query(query_texts=[query], n_results=k, where=where)
    ids = (res.get("ids") or [[]])[0]
    metas = (res.get("metadatas") or [[]])[0]
    docs = (res.get("documents") or [[]])[0]
    dists = (res.get("distances") or [[]])[0]

    out = []
    for cite, m, text, dist in zip(ids, metas, docs, dists):

        if max_distance is not None and dist > max_distance:
                    continue
        
        date = str(m["doc_date"])
        age = (datetime.date.today() - datetime.date.fromisoformat(date)).days
        out.append({
            "cite": cite,
            "title": str(m["title"]),
            "doc_type": str(m["doc_type"]),
            "doc_date": date,
            "status": str(m["status"]),
            "stale": age > STALE_DAYS,
            "distance": round(float(dist), 3),
            "text": text,
        })
    log("retrieval", query=query, product=product, hits=[o["cite"] for o in out])
    return out


def find_tickets(product: str | None = None, status: str | None = None) -> list[dict]:
    """Structured data is queried directly, never embedded."""
    rows = json.loads((DOCS / "tickets.json").read_text(encoding="utf-8"))
    return [r for r in rows
            if (not product or r["product"] == product)
            and (not status or r["status"] == status)]