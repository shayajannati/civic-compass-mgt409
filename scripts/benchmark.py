"""Tokenomics benchmark: unoptimized baseline vs optimized pipeline (real gpt-6-luna calls).

    python scripts/benchmark.py

Conditions (same 18 routing cases from run_eval.py; letters for 6 of them):
  baseline_cold   whole directory sent as verbose JSON (no deterministic pre-filter),
                  reasoning effort "medium", 2x output cap; unique tag per call => no prompt cache
  optimized_cold  pre-filtered compact candidate lines, effort "low"; unique tag per call => no cache
  optimized_warm  optimized pipeline with NO tag, run after a warm-up pass of the same cases,
                  i.e. best case for the provider's automatic prefix cache

Also times the deterministic lookups (local SQLite vs live Census Geocoder, with and
without the in-process cache) — these save latency and network calls, NOT LLM tokens.
Total spend for one full run is about $0.02 at course prices.
"""

from __future__ import annotations

import datetime as dt
import json
import statistics as st
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

from app import geo, pipeline  # noqa: E402
from run_eval import CASES, INJECTION  # noqa: E402

LETTER_CASES = {"NH-1", "NH-3", "CT-1", "CT-5", "US-1", "SAFE-1"}


def one(case: dict, variant: str, nonce: bool, letter: bool) -> dict:
    form = {k: case[k] for k in ("zip", "category", "description", "outcome")} | {"name": "Bench Tester"}
    tag = uuid.uuid4().hex[:10] if nonce else None
    r = pipeline.route(form, variant=variant, nonce=tag)
    rec = {"id": case["id"], "office": r["primary"]["id"],
           "pass": r["primary"]["id"] in case["acceptable"],  # same rule as run_eval.py
           "routing_usage": r["usage"][0], "candidates": r["candidate_count"], "letter_usage": []}
    if letter:
        L = pipeline.draft_letter({**form, "run_id": r["run_id"], "recipient_id": r["primary"]["id"]},
                                  variant=variant, nonce=tag)
        body = L["letter"]
        rec |= {"letter_usage": L["usage"], "letter_words": len(body.split()),
                "letter_issues_initial": len(L["safety"]["initial_issues"]),
                "letter_issues_remaining": len(L["safety"]["remaining_issues"]),
                "letter_repaired": L["safety"]["repaired"],
                "letter_placeholders": body.count("[")}
    return rec


def agg(rows: list[dict], key: str) -> dict:
    us = [u for r in rows for u in ([r["routing_usage"]] if key == "routing" else r["letter_usage"])]
    if not us:
        return {}
    f = lambda k: round(st.mean(u[k] for u in us), 1)  # noqa: E731
    return {"calls": len(us), "avg_input": f("input_tokens"), "avg_cached": f("cached_tokens"),
            "avg_output": f("output_tokens"), "avg_reasoning": f("reasoning_tokens"),
            "avg_latency_s": round(st.mean(u["latency_s"] for u in us), 2),
            "avg_cost_usd": round(st.mean(u["cost_usd"] for u in us), 7),
            "total_cost_usd": round(sum(u["cost_usd"] for u in us), 6)}


def condition(name: str, variant: str, nonce: bool) -> dict:
    rows = []
    for c in CASES + [INJECTION]:
        rows.append(one(c, variant, nonce, c["id"] in LETTER_CASES))
        print(f"  {name:15} {c['id']:6} {'PASS' if rows[-1]['pass'] else 'FAIL'} {rows[-1]['office']}")
    lw = [r for r in rows if "letter_words" in r]
    return {
        "condition": name, "rows": rows,
        "routing_pass": sum(r["pass"] for r in rows), "routing_cases": len(rows),
        "avg_candidates": round(st.mean(r["candidates"] for r in rows), 1),
        "routing": agg(rows, "routing"), "letter": agg(rows, "letter"),
        "letter_quality": {
            "letters": len(lw), "avg_words": round(st.mean(r["letter_words"] for r in lw), 1),
            "initial_issue_letters": sum(r["letter_issues_initial"] > 0 for r in lw),
            "remaining_issue_letters": sum(r["letter_issues_remaining"] > 0 for r in lw),
            "repairs": sum(r["letter_repaired"] for r in lw),
        } if lw else {},
    }


def lookup_timing() -> dict:
    t = time.perf_counter()
    for _ in range(200):
        geo.lookup_zip("06511")
    zip_ms = (time.perf_counter() - t) / 200 * 1000
    geo._geocode.cache_clear()
    t = time.perf_counter()
    loc = geo.lookup_address("165 Church St", "06510")
    live_ms = (time.perf_counter() - t) * 1000
    t = time.perf_counter()
    geo.lookup_address("165 Church St", "06510")
    cached_ms = (time.perf_counter() - t) * 1000
    return {"zip_lookup_local_sqlite_ms": round(zip_ms, 2), "address_geocode_live_ms": round(live_ms, 1),
            "address_geocode_cached_ms": round(cached_ms, 2), "address_method": loc.method,
            "address_districts": {"cd": loc.cd, "ct_house": loc.ct_lower, "ct_senate": loc.ct_upper}}


def main() -> None:
    out = {"run_at": dt.datetime.now().isoformat(timespec="seconds"), "model": "gpt-6-luna",
           "prices_per_1M": {"input": 0.10, "cached_input": 0.01, "output": 0.50}}
    print("lookup timing ...")
    out["lookups"] = lookup_timing()
    print(out["lookups"])
    print("baseline (cold) ...")
    out["baseline_cold"] = condition("baseline_cold", "baseline", nonce=True)
    print("optimized (cold) ...")
    out["optimized_cold"] = condition("optimized_cold", "optimized", nonce=True)
    print("optimized warm-up pass (not reported) ...")
    for c in CASES + [INJECTION]:
        form = {k: c[k] for k in ("zip", "category", "description", "outcome")} | {"name": "Bench Tester"}
        pipeline.route(form)
    print("optimized (warm) ...")
    out["optimized_warm"] = condition("optimized_warm", "optimized", nonce=False)

    evid = ROOT / "evidence"
    evid.mkdir(exist_ok=True)
    (evid / "tokenomics.json").write_text(json.dumps(out, indent=1))
    lines = [f"# Tokenomics benchmark ({out['run_at']}, gpt-6-luna)", "",
             "| Condition | Routing pass | Avg candidates | Routing in / cached / out tokens | Routing $/call | Routing latency | Letter in / out | Letter $/call |",
             "|---|---|---|---|---|---|---|---|"]
    for k in ("baseline_cold", "optimized_cold", "optimized_warm"):
        c = out[k]
        R, L = c["routing"], c["letter"]
        lines.append(f"| {k} | {c['routing_pass']}/{c['routing_cases']} | {c['avg_candidates']} | "
                     f"{R['avg_input']} / {R['avg_cached']} / {R['avg_output']} | ${R['avg_cost_usd']:.6f} | {R['avg_latency_s']} s | "
                     f"{L.get('avg_input')} / {L.get('avg_output')} | ${L.get('avg_cost_usd', 0):.6f} |")
    lines += ["", f"Lookups: {json.dumps(out['lookups'])}"]
    (evid / "tokenomics.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
