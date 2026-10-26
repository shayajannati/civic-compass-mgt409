"""The only place the app talks to a model: gpt-6-luna through Portkey (course key).

* Structured outputs: every call uses a strict JSON schema.
* Instrumentation: each call appends one JSON line to data/usage_log.jsonl with token
  counts, latency and estimated cost. No names, addresses or issue text are logged.
* Spend guard: calls are refused once today's logged spend reaches DAILY_BUDGET_USD.
"""

from __future__ import annotations

import datetime as dt
import json
import threading
import time
from dataclasses import dataclass

from openai import OpenAI

from . import config


class SetupError(RuntimeError):
    """The model cannot be called (missing key) — shown to the user as a setup message."""


class BudgetError(RuntimeError):
    pass


class ModelError(RuntimeError):
    pass


class ContentFilterError(ModelError):
    """The provider (Azure OpenAI behind Portkey) refused the prompt as unsafe/jailbreak."""


_lock = threading.Lock()
_client: OpenAI | None = None


def client() -> OpenAI:
    global _client
    key = config.api_key()
    if not key:
        raise SetupError(
            "PORTKEY_API_KEY is not set. Create a .env file containing PORTKEY_API_KEY=... in the "
            "repository folder or the folder directly above it (see .env.example), then restart."
        )
    if _client is None:
        _client = OpenAI(
            api_key="portkey",  # placeholder; Portkey authenticates with the header below
            base_url=config.PORTKEY_BASE_URL,
            timeout=config.API_TIMEOUT_SECONDS,
            max_retries=1,
            default_headers={
                "x-portkey-api-key": key,
                "x-portkey-provider": "openai",
                # never serve a stale gateway-cached answer: token meters must reflect real calls
                "x-portkey-cache-force-refresh": "true",
            },
        )
    return _client


def cost_usd(inp: int, cached: int, cache_write: int, out: int) -> float:
    p = config.PRICES_PER_M
    plain = max(inp - cached - cache_write, 0)
    return (plain * p["input"] + cached * p["cached"] + cache_write * p["cache_write"] + out * p["output"]) / 1e6


def spent_today() -> float:
    if not config.USAGE_LOG.exists():
        return 0.0
    today = dt.date.today().isoformat()
    total = 0.0
    with open(config.USAGE_LOG) as fh:
        for line in fh:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("ts", "").startswith(today):
                total += rec.get("cost_usd", 0.0)
    return total


@dataclass
class Usage:
    agent: str
    input_tokens: int
    cached_tokens: int
    cache_write_tokens: int
    output_tokens: int
    reasoning_tokens: int
    latency_s: float
    cost_usd: float

    def as_dict(self) -> dict:
        return self.__dict__.copy()


def call_json(*, agent: str, instructions: str, user_input: str, schema: dict, schema_name: str,
              max_output_tokens: int, run_id: str, variant: str = "optimized",
              effort: str | None = None, cache_key: str | None = None) -> tuple[dict, Usage]:
    if spent_today() >= config.DAILY_BUDGET_USD:
        raise BudgetError(f"Daily model budget of ${config.DAILY_BUDGET_USD:.2f} reached; try again tomorrow.")
    kwargs = dict(
        model=config.MODEL_NAME,
        instructions=instructions,
        input=user_input,
        max_output_tokens=max_output_tokens,
        reasoning={"effort": effort or config.REASONING_EFFORT},
        text={"format": {"type": "json_schema", "name": schema_name, "strict": True, "schema": schema}},
        store=False,
    )
    if cache_key:
        kwargs["prompt_cache_key"] = cache_key
    t0 = time.perf_counter()
    try:
        resp = client().responses.create(**kwargs)
    except SetupError:
        raise
    except Exception as exc:  # network, auth, timeout — never echo request content
        if "content_filter" in str(exc):
            _log({"ts": dt.datetime.now().isoformat(timespec="seconds"), "run_id": run_id, "variant": variant,
                  "model": config.MODEL_NAME, "status": "blocked_by_provider_filter", "agent": agent,
                  "input_tokens": 0, "cached_tokens": 0, "cache_write_tokens": 0, "output_tokens": 0,
                  "reasoning_tokens": 0, "latency_s": round(time.perf_counter() - t0, 3), "cost_usd": 0.0})
            raise ContentFilterError(
                "The AI provider's safety filter blocked this text because parts of it read like instructions to the AI. "
                "Please describe only your situation and try again.") from None
        raise ModelError(f"The language model call failed ({type(exc).__name__}). Please try again.") from None
    latency = time.perf_counter() - t0

    u = resp.usage
    in_det = getattr(u, "input_tokens_details", None)
    out_det = getattr(u, "output_tokens_details", None)
    cached = int(getattr(in_det, "cached_tokens", 0) or 0)
    cwrite = int(getattr(in_det, "cache_write_tokens", 0) or 0)
    usage = Usage(
        agent=agent, input_tokens=u.input_tokens, cached_tokens=cached, cache_write_tokens=cwrite,
        output_tokens=u.output_tokens, reasoning_tokens=int(getattr(out_det, "reasoning_tokens", 0) or 0),
        latency_s=round(latency, 3), cost_usd=0.0,
    )
    usage.cost_usd = round(cost_usd(u.input_tokens, cached, cwrite, u.output_tokens), 8)
    _log({"ts": dt.datetime.now().isoformat(timespec="seconds"), "run_id": run_id, "variant": variant,
          "model": config.MODEL_NAME, "status": resp.status, **usage.as_dict()})

    if resp.status != "completed":
        raise ModelError("The model response was incomplete (output limit reached). Please shorten the description and retry.")
    try:
        return json.loads(resp.output_text), usage
    except (json.JSONDecodeError, TypeError):
        raise ModelError("The model returned malformed output. Please retry.") from None


def _log(record: dict) -> None:
    config.USAGE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with _lock, open(config.USAGE_LOG, "a") as fh:
        fh.write(json.dumps(record) + "\n")
