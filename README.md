# OneOrigin GTM Engineer Take-Home

Three connected workflows that research a US college, draft outreach grounded in that research and in OneOrigin's own product documents, and answer sales questions from those documents. A human approves everything. Nothing is ever sent.

| Workflow | What it does | Entry point |
|---|---|---|
| 1. Research | Searches the web for one institution, extracts contacts, goals, tech stack and regulatory context into a typed record, then verifies it in code | `run_research.py` |
| 3. Retrieval | Indexes internal documents (type-aware chunking), filters out superseded docs, cuts off weak matches, answers with citations | `test_retrieval.py`, `ask.py` |
| 2. Outreach | Drafts an email and call script for one contact. Every factual sentence carries an evidence ID, and code checks the draft | `run_outreach.py` |

The written answers (design, retrieval, reliability, data handling, operator handoff) are in the separate written submission. Prompts are in `config/prompts/` and `config/personas.yaml`. A running record of what was tried, what broke and what changed is in `LOG.md`.

## Stack

Plain Python, Pydantic schemas, Tavily search, Chroma vector store. LLM calls go through one wrapper (`core/llm.py`) that uses the Gemini free tier first and falls back to a local Ollama model. Plain functions were chosen over n8n or LangGraph because they are easier to test, log and change live.

## Setup (Windows, Command Prompt)

```
python -m venv .venv
.venv\Scripts\activate
pip install openai pydantic tavily-python requests beautifulsoup4 chromadb pyyaml python-dotenv
copy .env.example .env
```

Fill in `.env` (see `.env.example`). You need a Tavily key (free at tavily.com). You need either a Gemini key (free at aistudio.google.com) or a local Ollama model.

Local model: install Ollama, then run `ollama serve` in a second window. The default context is too small for the research prompt, so make a larger variant:

```
echo FROM gemma4:latest> Modelfile
echo PARAMETER num_ctx 16384>> Modelfile
ollama create gemma4-16k -f Modelfile
```

Then set `OLLAMA_MODEL=gemma4-16k`. To run on the local model only, set `PRIMARY_PROVIDER=ollama` and leave `FALLBACK_PROVIDER=` empty. Gemini's free tier allows about 20 requests per day per model, so use the local model while developing.

## Run

```
python make_sample_docs.py                 create the invented sample internal docs (run once)
python test_retrieval.py                   build the index and run retrieval checks
python ask.py "What formats does AIRR accept?" airr
python ask.py "Can I promise a real-time API?" airr --informal

python run_research.py uga                 or: oregon     (Workflow 1)
python run_outreach.py uga                 lists contacts with their suggested persona
python run_outreach.py uga 1               draft for contact number 1
python run_outreach.py uga 0 registrar     force a persona (flagged if it does not match the title)

python eval\run_eval.py                    offline checks, no LLM calls
python show_log.py                         one line per run
```

Outputs are written to `outputs/`. Each outreach draft is saved as `.json` and `.md`, with an evidence table showing the source of every claim. Status `passed_checks` or `ready_for_review` only means the automated checks passed. It does not mean the draft is good, and a person must still read it.

## How to change behaviour (no code)

- `config/personas.yaml`: who each persona is, what they care about, which products lead, which product questions to retrieve, and the banned-phrase list.
- `config/prompts/research_extract.txt` and `config/prompts/outreach_system.txt`: the prompts.
- `core/retrieval.py`: `DEFAULT_MAX_DISTANCE` controls how close a document must be to count as a match.

## Layout

```
core/
  llm.py          model wrapper: provider fallback, retries, disk cache, logging
  schemas.py      Pydantic models (Claim, Contact, ResearchRecord, OutreachDraft)
  research.py     Workflow 1: search, extract, verify
  retrieval.py    Workflow 3: chunking, index, filtered search, direct ticket queries
  qa.py           cited answers for the sales team
  outreach.py     Workflow 2: evidence pack, draft, checks, retry
  logger.py       every call and run is logged
config/           prompts and personas
data/internal_docs/   INVENTED sample documents (each marked SAMPLE)
eval/             offline regression and guardrail tests
submission/       final research files, drafts and logs for review
```

`.env`, `logs/`, `outputs/`, `cache/` and `chroma_db/` are not committed, because logs and outputs contain names scraped from public pages.

## Still needs fixing

Known problems, roughly in order of importance:

1. **Incomplete or malformed JSON from the local model is not handled well.** The local model sometimes omits a whole section (for example the call script) or cuts the JSON off before the closing braces. Today the outreach step crashes or gives up after identical retries. Planned fix, not yet applied: catch the validation error in `outreach.generate()`, send it back to the model as feedback so the retry differs, and repair a missing closing brace in `llm._extract_json()`.
2. **No marketer interface.** Everything runs from the command line. A one-screen app with Approve, Reject and "Flag this claim" is designed but not built.
3. **Oregon research file is from a weak local-model run.** It has 5 contacts, against 14 from the earlier Gemini run, and it was produced before the role filter was added. It should be rerun when Gemini quota is available.
4. **Contact details are almost always missing.** Search snippets rarely contain emails or phone numbers, and none are guessed.
5. **IT roles have no persona.** The brief defines two buyer personas (registrar and enrollment), so IT contacts are skipped with a clear error.
6. **Conflicting contacts are only flagged.** UGA lists two IT leaders and the code warns about it but cannot decide which is current.
7. **The banned-phrase list is a crude word match.** It already produced a false positive on "not a guarantee" (now special-cased) and cannot catch subtle implied problems. The human approval step is the real safeguard.
8. **Retrieval cutoff is a first estimate.** The cutoff of 1.2 was calibrated on six queries and eight sample documents. It must be recalibrated when documents or the embedding model change.
9. **Not built:** public-footprint research (talks, blogs, posts), a suppression and opt-out list, a retention limit, per-customer access control for confidential material, and any test beyond two institutions.
10. **The sample internal documents are invented.** No real OneOrigin or customer material was used.