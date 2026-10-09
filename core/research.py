import os, re, json, pathlib, datetime
from dotenv import load_dotenv
from tavily import TavilyClient
from core import llm
from core.schemas import ResearchRecord

from core.logger import log, start_run, end_run

load_dotenv()
tavily = TavilyClient(api_key=os.environ["TAVILY_API_KEY"])
PROMPT_PATH = pathlib.Path("config/prompts/research_extraction.txt")

CACHE = pathlib.Path("cache")

ROLE_WORDS = ("registrar", "enrollment", "admission", "transfer", "articulation", "evaluat",
              "records", "credential", "information technology", "chief information", "cio",
              "provost", "student services", "student success")

def gather_sources_cached(inst: str, domain: str, state: str) -> list[dict]:
    CACHE.mkdir(exist_ok=True)
    slug = re.sub(r"\W+", "_", inst.lower())
    f = CACHE / f"{slug}_sources.json"
    if f.exists():
        log("sources_cache_hit", file=str(f))
        return json.loads(f.read_text(encoding="utf-8"))
    sources = gather_sources(inst, domain, state)
    f.write_text(json.dumps(sources), encoding="utf-8")
    return sources

QUERIES = {
    "contacts": [
        "{inst} registrar office staff directory",
        "{inst} transfer credit evaluation staff",
        "{inst} enrollment management leadership",
        "{inst} chief information officer IT leadership",
    ],
    "strategy": [
        "{inst} strategic plan enrollment transfer students",
        "{inst} administrative efficiency modernization initiative",
    ],
    "tech": [
        "{inst} student information system Banner PeopleSoft Colleague",
        "{inst} admissions CRM Slate Salesforce",
    ],
    "regulatory": [
        "{state} public university transfer credit law policy",
        "{state} statewide articulation agreement community college transfer",
    ],
}
DOMAIN_ONLY = {"contacts", "strategy"}  # restrict these to the official site


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").lower().strip()


def gather_sources(inst: str, domain: str, state: str) -> list[dict]:
    seen, sources = set(), []
    for cat, templates in QUERIES.items():
        for t in templates:
            q = t.format(inst=inst, state=state)
            domains = [domain] if cat in DOMAIN_ONLY else []
            try:
                res = tavily.search(query=q, max_results=4, include_domains=domains)
                log("search", category=cat, query=q, results=len(res.get("results", [])))
            except Exception as e:
                print(f"  search failed: {q} -> {e}")
                log("search_error", category=cat, query=q, error=str(e)[:300])
                continue
            for r in res.get("results", []):
                if r["url"] in seen:
                    continue
                seen.add(r["url"])
                sources.append({
                    "id": len(sources) + 1,
                    "category": cat,
                    "url": r["url"],
                    "title": r.get("title", ""),
                    "content": (r.get("content") or "")[:1500],
                })
    return sources


def extract(inst: str, sources: list[dict]) -> ResearchRecord:
    system = PROMPT_PATH.read_text(encoding="utf-8")
    blocks = "\n\n".join(
        f"[SOURCE {s['id']}] url: {s['url']}\ntitle: {s['title']}\n{s['content']}"
        for s in sources
    )
    user = f"Institution: {inst}\n\nSOURCES:\n{blocks}"
    return llm.ask_json(system, user, ResearchRecord)


def strip_interim(t: str) -> str:
    return norm(re.sub(r"\b(interim|acting)\b", "", norm(t)))


def title_near_name(name: str, title: str, text: str) -> bool:
    i = text.find(norm(name))
    if i == -1:
        return False
    window = text[max(0, i - 250): i + len(name) + 250]
    words = re.findall(r"[a-z]{4,}", norm(title))
    return not words or sum(w in window for w in words) / len(words) >= 0.5


def claim_supported(claim: str, quote: str) -> bool:
    words = set(re.findall(r"[a-z]{5,}", norm(claim)))
    q = norm(quote)
    return not words or sum(w in q for w in words) / len(words) >= 0.5


def verify(rec: ResearchRecord, sources: list[dict]):
    by_url = {s["url"]: norm(s["content"]) for s in sources}
    dropped, warnings = [], []

    kept = []
    for c in rec.contacts:
        text = by_url.get(c.source_url)
        if text is None or not title_near_name(c.name, c.title, text):
            dropped.append(f"contact '{c.name}' ({c.title}): name/title not found together in cited source")
            continue
        if not any(w in c.title.lower() for w in ROLE_WORDS):
            dropped.append(f"contact '{c.name}' ({c.title}): role not relevant to our buyers")
            continue
        if c.contact_info and norm(c.contact_info) not in text:
            c.contact_info = None
        kept.append(c)
    rec.contacts = kept

    titles = [(c.name, strip_interim(c.title)) for c in rec.contacts]
    for i in range(len(titles)):
        for j in range(i + 1, len(titles)):
            a, b = titles[i][1], titles[j][1]
            if a and b and (a in b or b in a):
                warnings.append(f"Possible conflicting/outdated contacts: {titles[i][0]} vs {titles[j][0]}")

    for field in ("strategic_goals", "tech_stack", "regulatory_context"):
        kept = []
        for cl in getattr(rec, field):
            if cl.status == "published_fact":
                text = by_url.get(cl.source_url or "")
                if text is None or not cl.quote or norm(cl.quote) not in text:
                    dropped.append(f"{field}: '{cl.text[:70]}' (quote/source not verified)")
                    continue
                if not claim_supported(cl.text, cl.quote):
                    warnings.append(f"{field}: claim goes beyond its quote -> '{cl.text[:70]}'")
            kept.append(cl)
        setattr(rec, field, kept)
        if not kept:
            rec.gaps.append(f"No verified items for {field}")
    if not rec.contacts:
        rec.gaps.append("No verified contacts found")
    return rec, dropped, warnings


def research(inst: str, domain: str, state: str) -> dict:
    start_run("research", institution=inst, domain=domain, state=state)
    try:
        print(f"[1/3] Searching for {inst}...")
        sources = gather_sources_cached(inst, domain, state)
        print(f"      {len(sources)} sources")
        log("sources_gathered", count=len(sources), urls=[s["url"] for s in sources])

        print("[2/3] Extracting...")
        rec = extract(inst, sources)

        print("[3/3] Verifying...")
        rec, dropped, warnings = verify(rec, sources)
        log("verification", dropped=dropped, warnings=warnings, gaps=rec.gaps)

        out = {
            "record": rec.model_dump(),
            "dropped_unverified": dropped,
            "sources": sources,
            "model_used": llm.last_provider_used,
            "warnings_for_review": warnings,
            "run_at": datetime.datetime.now().isoformat(timespec="seconds"),
        }
        pathlib.Path("outputs").mkdir(exist_ok=True)
        slug = re.sub(r"\W+", "_", inst.lower())
        pathlib.Path(f"outputs/{slug}_research.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8")
        end_run("ok", institution=inst, sources=len(sources),
                contacts=len(rec.contacts), dropped=len(dropped), 
                model=llm.last_provider_used)
        return out
    except Exception as e:
        end_run("error", institution=inst, error=str(e)[:300])
        raise