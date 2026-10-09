from pydantic import BaseModel
from core import llm, retrieval
from core.logger import log, start_run, end_run


class Answer(BaseModel):
    found: bool
    answer: str
    cited: list[str]


SYSTEM = """You answer questions from OneOrigin's sales team using ONLY the numbered SOURCES.
Rules:
1. Every sentence of the answer must end with the id of the source it came from, like [airr-overview#0]. Use only ids shown.
2. If the sources do not answer the question, set found to false and say what is missing. Never guess.
3. Sources of type meeting_transcript or email_thread are internal discussion, not confirmed product facts. If you use one, say it was discussed and never present roadmap items as available today.
4. Do not add facts, numbers or promises that are not in the sources.
5. List every id you used in cited."""


def ask(question: str, product: str | None = None, include_informal: bool = False) -> dict:
    start_run("qa", question=question, product=product, informal=include_informal)
    try:
        types = retrieval.OFFICIAL + (retrieval.INFORMAL if include_informal else ())
        hits = retrieval.search(question, product=product, k=5, doc_types=types)
        if not hits:
            end_run("ok", found=False)
            hint = "" if include_informal else " Try again including informal sources (call notes, email threads)."
            return {"found": False, "answer": "Nothing in the official product docs answers this." + hint,
                    "sources": [], "warnings": []}

        src = "\n\n".join(
            f"[{h['cite']}] ({h['doc_type']}, dated {h['doc_date']}) {h['text']}" for h in hits)
        ans = llm.ask_json(SYSTEM, f"QUESTION: {question}\n\nSOURCES:\n{src}", Answer)

        valid = {h["cite"]: h for h in hits}
        warnings = []
        unknown = [c for c in ans.cited if c not in valid]
        if unknown:
            warnings.append(f"Answer cited ids that were not retrieved: {unknown}")
        used = [valid[c] for c in ans.cited if c in valid]
        for h in used:
            if h["stale"]:
                warnings.append(f"{h['cite']} is older than a year ({h['doc_date']}); verify before use")
            if h["doc_type"] in retrieval.INFORMAL:
                warnings.append(f"{h['cite']} is informal discussion, not a confirmed product fact")
        end_run("ok", found=ans.found, cited=len(used), warnings=len(warnings))
        return {
            "found": ans.found, "answer": ans.answer, "warnings": warnings,
            "sources": [{"cite": h["cite"], "title": h["title"], "date": h["doc_date"]} for h in used],
        }
    except Exception as e:
        end_run("error", error=str(e)[:300])
        raise