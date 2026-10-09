import re, json, pathlib, yaml
from core import llm, retrieval
from core.logger import log, start_run, end_run
from core.schemas import OutreachDraft
from urllib.parse import urlparse

CFG = yaml.safe_load(pathlib.Path("config/personas.yaml").read_text(encoding="utf-8"))
PROMPT = pathlib.Path("config/prompts/outreach_system.txt")
MARK = re.compile(r"\s*\[[RP]\d+\]")
IDS = re.compile(r"\[([RP]\d+)\]")


def pick_persona(title: str):
    t = title.lower()
    for name, p in CFG["personas"].items():
        if any(k in t for k in p["title_keywords"]):
            return name
    return None


def build_evidence(rec: dict, persona: str, contact: dict):
    p = CFG["personas"][persona]
    home = ".".join(urlparse(contact["source_url"]).netloc.lower().split(".")[-2:])
    inst, skipped = [], []
    for field in p["evidence_fields"]:
        for cl in rec[field]:
            if cl["status"] != "published_fact":
                continue
            host = urlparse(cl["source_url"] or "").netloc.lower()
            if host.endswith(home) or (field == "regulatory_context" and host.endswith(".gov")):
                inst.append({"text": cl["text"], "source_url": cl["source_url"], "field": field})
            else:
                skipped.append(cl["text"][:80])
    if skipped:
        log("evidence_skipped_offsite", items=skipped)
    inst_ev = {f"R{i + 1}": e for i, e in enumerate(inst[:8])}

    seen, hits = set(), []
    for product in p["lead_products"]:
        for q in p["product_queries"]:
            for h in retrieval.search(q, product=product, k=2):
                if h["cite"] not in seen:
                    seen.add(h["cite"])
                    hits.append(h)
    prod_ev = {
        f"P{i + 1}": {"text": h["text"], "cite": h["cite"], "title": h["title"], "doc_date": h["doc_date"]}
        for i, h in enumerate(hits[:6])
    }
    return inst_ev, prod_ev


def make_prompt(inst, contact, persona, inst_ev, prod_ev, feedback=""):
    p = CFG["personas"][persona]
    lines = [
        f"INSTITUTION: {inst}",
        f"RECIPIENT: {contact['name']}, {contact['title']}",
        f"PERSONA: {persona}. Cares about: {p['cares_about']}",
        f"ANGLE: {p['angle']}",
        "",
        "INSTITUTION EVIDENCE:",
    ]
    lines += [f"[{k}] {v['text']}" for k, v in inst_ev.items()] or ["(none)"]
    lines += ["", "PRODUCT EVIDENCE:"]
    lines += [f"[{k}] {v['text']}" for k, v in prod_ev.items()] or ["(none)"]
    return "\n".join(lines) + feedback


SENT = re.compile(r"(?<=[.!?])\s+")
ASK = re.compile(r"\b(conversation|chat|call|open to)\b", re.I)


def uncited(text: str) -> list[str]:
    out = []
    for s in SENT.split(text.strip()):
        if not s or s.endswith("?") or IDS.search(s) or len(s.split()) < 8 or ASK.search(s):
            continue
        out.append(s[:80])
    return out


def check(d: OutreachDraft, inst_ev: dict, prod_ev: dict) -> list[str]:
    problems = []
    texts = [d.email.subject, d.email.body, d.call.opener,
             *d.call.talking_points, *d.call.discovery_questions]
    joined = " ".join(texts)
    used = set(IDS.findall(joined))

    bad = used - set(inst_ev) - set(prod_ev)
    if bad:
        problems.append(f"unknown evidence ids {sorted(bad)}")
    if inst_ev and not any(u.startswith("R") for u in used):
        problems.append("no institution evidence cited")
    if not any(u.startswith("P") for u in set(IDS.findall(d.email.body))):
        problems.append("email has no cited product statement")

    for t in [d.email.body, d.call.opener, *d.call.talking_points]:
        for s in uncited(t):
            problems.append(f"uncited statement: '{s}'")

    clean = MARK.sub("", joined).lower()
    clean = clean.replace("not a guarantee", "")
    for ph in CFG["banned_phrases"]:
        if ph in clean:
            problems.append(f"banned phrase '{ph}'")

    evidence_text = " ".join(v["text"] for v in [*inst_ev.values(), *prod_ev.values()]).lower()
    for num in set(re.findall(r"\d[\d,.]*%?", clean)):
        if num.rstrip(".,") not in evidence_text:
            problems.append(f"number not in evidence: {num}")

    words = len(MARK.sub("", d.email.body).split())
    if words > 130:
        problems.append(f"email too long ({words} words)")

    if re.search(r"\bI know\b", joined, re.I):
        problems.append("opens by telling the recipient their own job ('I know...')")
    if re.search(r"\bthis is [A-Z][a-z]+ (from|with|at)\b", joined):
        problems.append("invented sender name")
    
    return problems


def render_md(out: dict) -> str:
    c = out["clean"]
    md = [f"# DRAFT (not approved): {out['institution']} / {out['contact']['name']}",
          f"Persona: {out['persona']} | Status: {out['status']} | Model: {out['model_used']}", ""]
    if out["problems"]:
        md += ["**Problems found by checks:** " + "; ".join(out["problems"]), ""]
    md += ["## Email", f"**Subject:** {c['email']['subject']}", "", c["email"]["body"], "",
           "## Call script", f"**Opener:** {c['call']['opener']}", "", "**Talking points**"]
    md += [f"- {t}" for t in c["call"]["talking_points"]]
    md += ["", "**Discovery questions**"] + [f"- {q}" for q in c["call"]["discovery_questions"]]
    md += ["", "## Evidence behind each claim"]
    for k, v in out["evidence"]["institution"].items():
        md.append(f"- [{k}] {v['text']} (source: {v['source_url']})")
    for k, v in out["evidence"]["product"].items():
        md.append(f"- [{k}] {v['text'][:140]} (doc: {v['cite']}, dated {v['doc_date']})")
    return "\n".join(md)


def generate(research_out: dict, contact_name: str, persona: str | None = None) -> dict:
    rec = research_out["record"]
    inst = rec["institution"]
    contact = next(c for c in rec["contacts"] if c["name"] == contact_name)
    override = persona
    auto = pick_persona(contact["title"])
    persona = override or auto
    if not persona:
        raise ValueError(f"No persona matches '{contact['title']}'. Pass one explicitly.")

    start_run("outreach", institution=inst, contact=contact_name, persona=persona)
    try:
        inst_ev, prod_ev = build_evidence(rec, persona, contact)
        log("evidence_built", institution_ids=list(inst_ev), product_ids=list(prod_ev))
        system = PROMPT.read_text(encoding="utf-8")

        feedback, problems, draft = "", [], None
        for attempt in range(3):
            draft = llm.ask_json(system, make_prompt(inst, contact, persona, inst_ev, prod_ev, feedback),
                                 OutreachDraft)
            problems = check(draft, inst_ev, prod_ev)
            log("outreach_check", attempt=attempt + 1, problems=problems)
            if not problems:
                break
            feedback = ("\n\nYOUR PREVIOUS DRAFT WAS REJECTED FOR: " + "; ".join(problems)
                        + ". Rewrite it fixing these, keeping all other rules.")

        if draft is None:
            raise RuntimeError("No draft was produced")

        draft.evidence_used = sorted(set(IDS.findall(json.dumps(draft.model_dump()))))

        cited = draft.model_dump()
        clean = json.loads(MARK.sub("", json.dumps(cited)))
        if override and auto and override != auto:
            problems.append(f"persona override '{override}' differs from title-based '{auto}'")
        status = "ready_for_review" if not problems else "needs_attention"
        out = {
            "approval": "DRAFT - NOT APPROVED",
            "status": status, "problems": problems,
            "institution": inst, "contact": contact, "persona": persona,
            "cited": cited, "clean": clean,
            "evidence": {"institution": inst_ev, "product": prod_ev},
            "model_used": llm.last_provider_used,
        }
        slug = re.sub(r"\W+", "_", f"{inst}_{contact_name}_{persona}".lower())
        pathlib.Path("outputs").mkdir(exist_ok=True)
        pathlib.Path(f"outputs/outreach_{slug}.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
        md_path = f"outputs/outreach_{slug}.md"
        pathlib.Path(md_path).write_text(render_md(out), encoding="utf-8")
        out["markdown_path"] = md_path
        end_run(status, institution=inst, contact=contact_name, persona=persona, problems=len(problems))
        return out
    except Exception as e:
        end_run("error", error=str(e)[:300])
        raise