import json, collections

runs = collections.OrderedDict()
for line in open("logs/events.jsonl", encoding="utf-8"):
    e = json.loads(line)
    runs.setdefault(e["run_id"], []).append(e)

for rid, evs in runs.items():
    start = next((e for e in evs if e["event"] == "run_start"), {})
    end = next((e for e in evs if e["event"] == "run_end"), {})
    calls = [e for e in evs if e["event"] == "llm_call"]
    fails = [c for c in calls if not c["ok"]]
    tokens = sum((c.get("usage") or {}).get("completion_tokens") or 0 for c in calls)
    secs = round(sum(c["seconds"] for c in calls), 1)
    provs = sorted({c["provider"] for c in calls if c["ok"]})
    print(f"{rid} | {start.get('workflow')} | {start.get('institution', '')} | "
          f"{end.get('status', 'unfinished')} | llm calls {len(calls)} "
          f"(failed {len(fails)}) | out tokens {tokens} | {secs}s | {provs}")