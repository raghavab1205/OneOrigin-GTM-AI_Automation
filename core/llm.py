import os, json, time
from dotenv import load_dotenv
from openai import OpenAI
from core.logger import log

load_dotenv()

PROVIDERS = {
    "ollama": {
        "base_url": os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1"),
        "api_key": "ollama",
        "model": os.getenv("OLLAMA_MODEL", "gemma4:16k"),
    },
    "gemini": {
        "base_url": "https://generativelanguage.googleapis.com/v1beta/openai/",
        "api_key": os.getenv("GEMINI_API_KEY", ""),
        "model": os.getenv("GEMINI_MODEL", "gemini-3.8-flash"),
    },
}

PRIMARY = os.getenv("PRIMARY_PROVIDER", "gemini")
FALLBACK = os.getenv("FALLBACK_PROVIDER", "ollama")

last_provider_used = None


def _extract_json(text: str) -> str:
    start = text.find("{")
    if start == -1:
        return text
    end = text.rfind("}")
    s = text[start:end + 1] if end != -1 else text[start:]
    missing = s.count("{") - s.count("}")
    if missing > 0:
        s += "}" * missing
    return s


def _call(provider: str, system: str, prompt: str):
    cfg = PROVIDERS[provider]
    client = OpenAI(api_key=cfg["api_key"], base_url=cfg["base_url"], timeout=300)
    resp = client.chat.completions.create(
        model=cfg["model"],
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        temperature=0,
        response_format={"type": "json_object"},
    )
    u = resp.usage
    usage = {
        "prompt_tokens": getattr(u, "prompt_tokens", None),
        "completion_tokens": getattr(u, "completion_tokens", None),
    } if u else {}
    return resp.choices[0].message.content or "", usage


def ask_json(system: str, user: str, schema, attempts_per_provider: int = 2):
    global last_provider_used
    prompt = (
        f"{user}\n\nReturn ONLY valid JSON matching this schema:\n"
        f"{json.dumps(schema.model_json_schema())}"
    )
    order = [p for p in [PRIMARY, FALLBACK] if p]
    errors = []
    for provider in order:
        for attempt in range(attempts_per_provider):
            t0, raw, usage = time.time(), "", {}
            base = dict(
                provider=provider,
                model=PROVIDERS[provider]["model"],
                attempt=attempt + 1,
                schema=schema.__name__,
                system_prompt=system,
                user_prompt=user[:3000],
                user_prompt_chars=len(user),
            )
            try:
                raw, usage = _call(provider, system, prompt)
                result = schema.model_validate_json(_extract_json(raw))
                last_provider_used = provider
                log("llm_call", ok=True, seconds=round(time.time() - t0, 2),
                    usage=usage, raw_output=raw, **base)
                return result
            except Exception as e:
                errors.append(f"{provider} attempt {attempt + 1}: {e}")
                log("llm_call", ok=False, error=str(e)[:500],
                    seconds=round(time.time() - t0, 2), usage=usage,
                    raw_output=raw, **base)
    raise RuntimeError("All providers failed:\n" + "\n".join(errors))