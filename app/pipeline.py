"""Orchestration: validate -> locate -> retrieve candidates -> Agent 1 -> verify -> Agent 2 -> verify.

Server-side state is limited to a short-lived map run_id -> allowed recipient ids, so
the letter step can only address an office that the routing step returned from the
verified directory. No names, addresses or narratives are stored.
"""

from __future__ import annotations

import datetime as dt
import threading
import time
import uuid

from . import config, directory, geo, safety
from .agents import run_letter, run_routing


class InputError(ValueError):
    pass


_runs: dict[str, tuple[float, set[str], dict]] = {}
_runs_lock = threading.Lock()
RUN_TTL = 3600


def _remember(run_id: str, ids: set[str], routing: dict) -> None:
    now = time.time()
    with _runs_lock:
        for k in [k for k, (t, _, _) in _runs.items() if now - t > RUN_TTL]:
            del _runs[k]
        _runs[run_id] = (now, ids, routing)


def validate_form(form: dict) -> dict:
    zip5 = str(form.get("zip", "")).strip()
    if not safety.ZIP_RE.match(zip5):
        raise InputError("Please enter a valid 5-digit ZIP code.")
    category = str(form.get("category", "")).strip()
    if category not in config.CATEGORIES:
        raise InputError("Please choose an issue category.")
    description = safety.clean_text(form.get("description"), config.MAX_DESCRIPTION_CHARS)
    if len(description) < 20:
        raise InputError("Please describe the situation in at least a sentence (20+ characters).")
    outcome = safety.clean_text(form.get("outcome"), config.MAX_OUTCOME_CHARS)
    if len(outcome) < 5:
        raise InputError("Please say what outcome you want.")
    return {
        "name": safety.clean_text(form.get("name"), config.MAX_NAME_CHARS),
        "zip": zip5,
        "street": safety.clean_text(form.get("street"), config.MAX_ADDRESS_CHARS).replace("\n", " "),
        "category": category,
        "description": description,
        "outcome": outcome,
        "extra": safety.clean_text(form.get("extra"), config.MAX_EXTRA_CHARS),
    }


def public_record(r: dict) -> dict:
    keys = ("id", "kind", "name", "role", "level", "jurisdiction", "handles", "phone", "email", "contact_url",
            "website", "complaint_process", "address", "party", "source_url", "date_checked",
            "verified_via", "snapshot_url", "source_id")
    return {k: r.get(k) for k in keys if r.get(k) not in (None, "")}


def route(form: dict, *, variant: str = "optimized", nonce: str | None = None) -> dict:
    data = validate_form(form)
    run_id = uuid.uuid4().hex[:12]
    t0 = time.perf_counter()

    loc = geo.lookup_address(data["street"], data["zip"]) if data["street"] else geo.lookup_zip(data["zip"])
    if not loc.found:
        raise InputError("That ZIP code was not found in Census ZIP Code Tabulation Areas. Please check it.")
    if variant == "optimized":
        candidates = directory.agency_candidates(loc, data["category"])
    else:  # baseline: no deterministic pre-filtering, whole directory goes to the model
        candidates = directory.agency_candidates(loc, "other")
        candidates += [r for r in directory.query_all_agencies() if r["id"] not in {c["id"] for c in candidates}]
    elected = directory.elected_officials(loc)
    lookup_s = time.perf_counter() - t0

    hits = safety.injection_flags(data["description"], data["outcome"], data["extra"], data["name"])
    routing, usage = run_routing(issue=data, location=loc.summary(), candidates=candidates,
                                 officials=elected["unique"], injection_hits=hits, run_id=run_id, variant=variant,
                                 nonce=nonce)

    # ---- verify the agent's choices against the deterministic candidate set ----
    allowed = {r["id"]: r for r in candidates + elected["unique"]}
    checks = []
    primary = allowed.get(routing["primary_id"])
    if primary is None:  # cannot happen with the strict enum, but never trust blindly
        raise RuntimeError("Routing agent selected an office outside the verified candidate list.")
    checks.append("Primary office id is in the verified candidate list")
    if routing["level"] != primary.get("level"):
        checks.append(f"Level corrected from '{routing['level']}' to the office's actual level '{primary['level']}'")
        routing["level"] = primary["level"]
    secondary = [allowed[i] for i in dict.fromkeys(routing["secondary_ids"]) if i in allowed and i != primary["id"]][:2]
    elected_pick = allowed.get(routing["elected_id"]) if routing["elected_id"] != "none" else None
    recipients = [primary] + secondary + ([elected_pick] if elected_pick and elected_pick["id"] != primary["id"] else [])
    _remember(run_id, {r["id"] for r in recipients}, {"rationale": routing["rationale"]})

    return {
        "run_id": run_id,
        "location": loc.summary(),
        "routing": {k: routing[k] for k in ("issue_summary", "level", "rationale", "needs_clarification",
                                            "clarifying_question", "emergency", "injection_suspected")},
        "primary": public_record(primary),
        "secondary": [public_record(r) for r in secondary],
        "elected": public_record(elected_pick) if elected_pick else None,
        "officials": [public_record(r) for r in elected["unique"]],
        "possible_officials": {k: [public_record(r) for r in v] for k, v in elected["possible"].items()},
        "coverage_gaps": elected["gaps"],
        "candidate_count": len(candidates) + len(elected["unique"]),
        "safety": {"injection_flags": hits, "checks": checks},
        "usage": [usage],
        "timing": {"lookup_s": round(lookup_s, 3)},
    }


def _salutation(r: dict) -> str:
    if r["kind"] != "official":
        return f"Dear {r['name']} staff:"
    parts = [p for p in r["name"].replace(",", "").split() if p.rstrip(".").lower() not in ("jr", "sr", "ii", "iii", "iv")]
    last = parts[-1] if parts else r["name"]
    title = "Senator" if "Senator" in (r.get("role") or "") else "Representative"
    return f"Dear {title} {last}:"


def _recipient_block(r: dict) -> str:
    lines = [r["name"]]
    if r["kind"] == "official" and r.get("role"):
        lines.append(r["role"])
    if r.get("address"):
        lines.append(r["address"])
    return "\n".join(lines)


def draft_letter(payload: dict, *, variant: str = "optimized", nonce: str | None = None) -> dict:
    data = validate_form(payload)
    run_id = str(payload.get("run_id", ""))
    recipient_id = str(payload.get("recipient_id", ""))
    with _runs_lock:
        entry = _runs.get(run_id)
    if not entry or recipient_id not in entry[1]:
        raise InputError("That recipient is not part of a current verified routing result. Please run the routing step again.")
    record = directory.get_record(recipient_id)
    if record is None:
        raise InputError("Recipient record not found in the verified directory.")
    routing = entry[2]

    # Instruction-like sentences never reach the Letter-Writing Agent (they are not facts).
    removed = 0
    for key in ("description", "outcome", "extra"):
        data[key], n = safety.strip_injection(data[key])
        removed += n
    if len(data["description"]) < 10:
        raise InputError("After removing text addressed to the AI, too little description is left. Please describe your situation.")

    user_text = " ".join([data["description"], data["outcome"], data["extra"], data["name"]])
    usages = []
    letter, u = run_letter(issue=data, sender_name=data["name"], recipient=record, routing=routing,
                           run_id=run_id, variant=variant, nonce=nonce)
    usages.append(u)
    issues = safety.check_letter(letter["body"] + "\n" + letter["subject"], user_text=user_text, record=record)
    first_issues = list(issues)
    repaired = False
    if any(i["severity"] == "high" for i in issues):  # one bounded repair attempt, never a loop
        letter2, u2 = run_letter(issue=data, sender_name=data["name"], recipient=record, routing=routing,
                                 run_id=run_id, variant=variant, nonce=nonce,
                                 repair_notes=[f"{i['type']}: {i['detail']}" for i in issues])
        usages.append(u2)
        letter, repaired = letter2, True
        issues = safety.check_letter(letter["body"] + "\n" + letter["subject"], user_text=user_text, record=record)
    body = safety.redact_contacts(letter["body"].strip(), issues)

    address_line = f"{data['street']}, {data['zip']}" if data["street"] else f"[Your street address], {data['zip']}"
    sign_off = "\n".join([data["name"] or "[Your name]", address_line, "[Your phone or email]"])
    full = "\n\n".join([
        dt.date.today().strftime("%B %d, %Y"),
        _recipient_block(record),
        f"Re: {letter['subject'].strip()}",
        _salutation(record),
        body,
        f"Sincerely,\n{sign_off}",
    ])
    return {
        "run_id": run_id,
        "recipient": public_record(record),
        "subject": letter["subject"].strip(),
        "letter": full,
        "placeholders": letter.get("placeholders", []),
        "safety": {"initial_issues": first_issues, "remaining_issues": issues, "repaired": repaired,
                   "removed_instruction_sentences": removed},
        "usage": usages,
    }
