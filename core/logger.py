import json, uuid, pathlib, datetime, contextvars

LOG_DIR = pathlib.Path("logs")
LOG_DIR.mkdir(exist_ok=True)
_run_id = contextvars.ContextVar("run_id", default="no-run")


def _now() -> str:
    return datetime.datetime.now().isoformat(timespec="seconds")


def log(event: str, **data):
    rec = {"ts": _now(), "run_id": _run_id.get(), "event": event, **data}
    with open(LOG_DIR / "events.jsonl", "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, default=str) + "\n")


def start_run(workflow: str, **meta) -> str:
    rid = datetime.datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
    _run_id.set(rid)
    log("run_start", workflow=workflow, **meta)
    return rid


def end_run(status: str = "ok", **summary):
    log("run_end", status=status, **summary)
    line = f"- {_now()} | {_run_id.get()} | {status} | {json.dumps(summary, default=str)}\n"
    with open(LOG_DIR / "RUNS.md", "a", encoding="utf-8") as f:
        f.write(line)