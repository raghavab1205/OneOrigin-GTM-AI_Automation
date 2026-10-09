# LOG

## Setup and tool choices
- Stack: plain Python + Pydantic + Tavily search + Chroma. Considered n8n and LangGraph, dropped
  them because plain functions are easier to test, debug and change live.
- Built in VS Code locally (considered Replit, dropped: deployment not required).
- Claude API: no key available. Switched to an OpenAI-compatible wrapper so any provider works.
- Providers: Gemini free tier primary, local gemma4 via Ollama as fallback.
- Considered Kimi: direct API is paid. Did not use the kimi cloud model in Ollama (untested).

## Errors hit and fixes
- Gemini 404: gemini-2.5-flash no longer available to new keys -> changed model name in .env.
- Ollama "Connection error": server was not running -> ollama serve. Fallback was silently dead.
- Tavily call failed/typed wrong: include_domains must be a list, not None -> pass [].
- Oregon first run failed entirely: Gemini 503 (high demand) twice + Ollama down.
  Fix: retry with backoff on 503/429/timeouts, cache Tavily results, start Ollama.
- Missing Tavily key at first run -> created free key.

## Design decisions
- Every fact is a Claim with status (published_fact / inferred / unknown), source_url, quote.
- Verification is in code, not just the prompt: source URL must be one we retrieved, quote must
  appear in that source text.
- Contact and strategy searches restricted to the official domain; tech and regulatory are not
  (those facts often live on vendor or state sites).
- Retrieval: only status=current docs are searched; superseded docs are excluded (2024 config).
  Tickets are queried directly as structured data, not embedded.
- Sample internal docs are INVENTED by me for this exercise (marked SAMPLE in each file).

## What the first verification missed
- First version dropped 0 items on both institutions. Suspicious, not good news.
- It proved a quote exists but not that the claim follows from it
  (e.g. Oregon "elevate scholarship" not in its quote; UGA DegreeWorks "fact" was just an email row).
- It did not check titles, only names.
- Added: name+title proximity check, claim-vs-quote word overlap warning, conflicting-contact warning.

## Findings on the two institutions
- UGA: two IT leaders listed (Hasko interim VP, Chester CIO from an award article). Flagged
  automatically, not resolved.
- UGA regulatory item came from another school's website; thin.
- Oregon CRM correctly marked inferred (title implies a CRM, vendor unknown); gap listed.
- Contact reach: almost no emails or phones (search snippets rarely contain them). I did not guess.

## Not built / known limitations
- Public footprint (talks, blogs, posts) in Workflow 1.
- Reliable contact info; regulatory coverage is shallow.
- Staleness: no "as of" date check on contacts.

## Prompts
- Research extraction prompt: config/prompts/research_extract.txt
- Every prompt and raw model output is auto-logged in logs/events.jsonl

## 2026-10-09: Workflows 3 and 2

### Workflow 3 (retrieval), built before Workflow 2 because outreach depends on it
- Sample internal docs are INVENTED by me (marked SAMPLE in each file): 6 product/config docs, 1 call
  transcript, 1 email thread, 1 tickets.json.
- Chunking by type: headings for docs/configs, groups of 6 speaker turns (1 overlap) for transcripts,
  one chunk per message (subject prefixed) for emails. Tickets are queried directly, not embedded.
- Staleness: status field (current/superseded) filtered at query time; superseded docs stay indexed
  for audit. doc_date shown on every hit, with a stale flag over 365 days.
- Source authority: outreach searches official docs only. Call notes and emails are opt-in and
  labelled informal. Test case: a call note says a real-time API is "on the roadmap, nothing
  committed". Official-only search returns nothing; informal search returns it with a warning.
- Problem found: vector search always returns the nearest chunks even when nothing is relevant
  ("real-time API" returned unrelated docs). Fix: distance cutoff 1.2. Calibrated on only 6 queries
  (relevant hits at 0.37-1.15, irrelevant at 1.35+). A first estimate, not a proven threshold.
- Result: off-topic queries now return nothing; Q&A makes zero LLM calls when nothing is found.
- First test run wasn't wrapped in start_run/end_run, so it left no RUNS.md line. Fixed.

### Workflow 2 (outreach)
- Design: contact -> persona (title keywords, override allowed) -> evidence pack (verified research
  facts R#, retrieved product facts P#) -> draft with inline evidence ids -> code checks -> retry.
- Checks (in code, not prompt): ids exist, email cites a product fact, banned phrases (pain words,
  guarantee), numbers must appear in evidence, uncited sentences, email length.
- Rejected alternative: asking the model to "be accurate" and trusting it. Kept deterministic checks.
- First drafts looked fine and passed the checks, but reading them showed real problems the checks
  missed:
  - "This process ensures students get clarity" (uncited, overpromises; product doc says estimate)
  - "brief conversation next week" (breaks no-specific-times rule)
  - openers like "I know the Office of the Registrar oversees..." (tells the recipient their own job)
  - a student-clarity claim attributed to a source that only gave a transfer ratio
  - the email itself had no product statement (only the call script did)
  - model-supplied evidence_used list was wrong, so the code now computes it
  - one regulatory fact came from another school's website (Athens Tech) -> now excluded
- Forcing the wrong persona (enrollment VP as registrar) produced a fluent but nonsensical email
  that passed. Added a mismatch flag. This matters for the marketer interface.
- Second round: the better model's draft for the registrar led with the school's own system (Banner)
  tied to a cited capability, which is the specificity the brief asks for.
  Remaining flaws: invented sender name ("this is Alex"), "Dear Nikki Hon". Added rules and checks.
- [FILL IN: whether you applied the patches and what the drafts looked like afterwards]

### Failures and fixes
- Gemini free tier is 20 requests/day per model. Retrying a daily quota is pointless -> stop retrying
  on daily limits, retry only 503/429-style temporary errors with backoff, cache LLM answers on disk.
- Gemini 503 "high demand" plus Ollama not running -> total failure on an Oregon run.
- gemma returned prose instead of JSON on a 40-source prompt (suspected Ollama's small default
  context) -> made a 16k-context variant and truncated source text.
- Missing field (evidence_used) crashed validation on the local model -> made it optional.
- Model choice changes quality: Oregon via Gemini gave 14 contacts, via local gemma gave 5, and
  included irrelevant roles (Payroll, Telecom). Added a role filter. [FILL IN: Oregon rerun result]
- Kimi (considered): direct API is paid; not used.

### Current status
- Working end to end on UGA. [FILL IN: Oregon outreach drafts, once generated]
- Eval harness (eval/run_eval.py): retrieval regression + guardrail tests. [FILL IN: pass/fail output]
- Not built yet: marketer interface, public-footprint search, contact reach details, IT persona.
- Known limits: contact emails/phones almost always missing; IT leaders skipped (no persona defined);
  sample internal docs are invented; nothing tested beyond 2 institutions.