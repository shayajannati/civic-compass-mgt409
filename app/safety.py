"""Deterministic safety layer (no LLM).

1. Input hygiene: length limits, control-character stripping, ZIP validation.
2. Prompt-injection screening: user text is wrapped as quoted data and scanned for
   instruction-like patterns. Detection does not block the request (real complaints
   can contain odd phrases) but it is flagged, logged, and the agents are told.
3. Output verification for letters: contact details must come from the verified
   record or the user's own text; legal citations and "must respond" claims that
   the user never supplied are flagged; unverified contact details are redacted.
"""

from __future__ import annotations

import re
import unicodedata

ZIP_RE = re.compile(r"^\d{5}$")

INJECTION_PATTERNS = [
    r"ignore (all |any |the )?(previous|prior|above|earlier) (instructions|prompts?|rules)",
    r"disregard (all |the |your )?(previous |prior )?(instructions|rules|guidelines)",
    r"(you are|act as|pretend to be) (now )?(a |an )?(different|new|unrestricted|dan\b)",
    r"\b(admin|developer|god|debug) mode\b",
    r"\b(primary_id|elected_id|secondary_ids|recipient_id)\b",
    r"(in|into) the letter,? (tell|say|state|claim|write)",
    r"system prompt|developer message|<\s*/?\s*(system|assistant|instructions?)\s*>",
    r"(reveal|print|show|repeat) (your|the) (instructions|prompt|system|api key|secrets?)",
    r"(address|send|route) (this|the letter|it) to .{0,40}@",
    r"(choose|select|pick|output) (office|recipient|id)\s*[:=]",
    r"\bjailbreak\b|\bprompt injection\b",
    r"api[_ -]?key|portkey",
]
_INJ = [re.compile(p, re.I) for p in INJECTION_PATTERNS]

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
URL_RE = re.compile(r"\b(?:https?://|www\.)[^\s<>()\"']+", re.I)
PHONE_RE = re.compile(r"(?:\+?1[\s.-]?)?\(?\b\d{3}\)?[\s.-]?\d{3}[\s.-]?\d{4}\b")
LEGAL_RE = re.compile(
    r"§|\bU\.?\s?S\.?\s?C\.?\b|\bC\.?\s?F\.?\s?R\.?\b|\bC\.?\s?G\.?\s?S\.?\b|General Statutes|"
    r"\bPublic (Act|Law) (No\.? )?\d|\bSection \d|\bTitle [IVX\d]+\b|\b[A-Z][a-z]+ Act of \d{4}|"
    r"\bordinance (no\.?|number) ?\d|\bcode section\b|\bstatute\b|\bregulations? \d",
    re.I,
)
OBLIGATION_RE = re.compile(
    r"(legally|lawfully) (required|obligated|bound|mandated)|required by law to (respond|reply|act)|"
    r"(must|are obligated to|have to) (respond|reply) (with)?in \d+|obligated to respond",
    re.I,
)


def clean_text(value: str | None, limit: int) -> str:
    if not value:
        return ""
    value = unicodedata.normalize("NFKC", value)
    value = "".join(ch for ch in value if ch in "\n\t" or unicodedata.category(ch)[0] != "C")
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value).strip()
    return value[:limit]


def injection_flags(*texts: str) -> list[str]:
    hits = []
    for text in texts:
        for rx in _INJ:
            m = rx.search(text or "")
            if m:
                hits.append(m.group(0)[:60])
    return hits


def strip_injection(text: str) -> tuple[str, int]:
    """Drop sentences that contain instruction-like text. Returns (clean_text, n_removed)."""
    if not text:
        return text, 0
    sentences = re.split(r"(?<=[.!?])\s+|\n+", text)
    keep = [s for s in sentences if not any(rx.search(s) for rx in _INJ)]
    return " ".join(keep).strip(), len(sentences) - len(keep)


def as_data(label: str, text: str) -> str:
    """Wrap untrusted text so it cannot close our delimiters."""
    safe = text.replace("<<<", "‹‹‹").replace(">>>", "›››")
    return f"<<<{label}\n{safe}\n{label}>>>"


def _digits(s: str) -> str:
    return re.sub(r"\D", "", s)


def check_letter(body: str, *, user_text: str, record: dict) -> list[dict]:
    """Return issues: {"type", "severity": "high"|"medium", "detail"}."""
    issues: list[dict] = []
    verified = " ".join(str(record.get(k) or "") for k in ("phone", "email", "contact_url", "website", "address", "source_url"))
    verified_lower, user_lower = verified.lower(), user_text.lower()
    verified_digits = {_digits(p) for p in PHONE_RE.findall(verified)}
    user_digits = {_digits(p) for p in PHONE_RE.findall(user_text)}

    def contact(detail: str, in_verified: bool, from_user: bool) -> None:
        if in_verified:
            return
        if from_user:  # the resident typed it: keep it, but say it is not a verified government contact
            issues.append({"type": "user_supplied_contact", "severity": "medium",
                           "detail": f"{detail} came from your text and is not in the verified directory; double-check it."})
        else:          # the model produced it: treat as invented
            issues.append({"type": "unverified_contact", "severity": "high", "detail": detail})

    for email in set(EMAIL_RE.findall(body)):
        contact(email, email.lower() in verified_lower, email.lower() in user_lower)
    for url in {u.rstrip(".,;") for u in URL_RE.findall(body)}:
        contact(url, url.lower() in verified_lower, url.lower() in user_lower)
    for phone in set(PHONE_RE.findall(body)):
        contact(phone, _digits(phone) in verified_digits, _digits(phone) in user_digits)
    for m in set(x.group(0) for x in LEGAL_RE.finditer(body)):
        if m.lower() not in user_text.lower():
            issues.append({"type": "unsupported_legal_claim", "severity": "high",
                           "detail": f"Legal reference “{m}” was not in your description."})
    for m in set(x.group(0) for x in OBLIGATION_RE.finditer(body)):
        issues.append({"type": "obligation_claim", "severity": "high",
                       "detail": f"Claims a duty to respond (“{m}”); officials are generally not legally required to answer constituent letters."})
    return issues


def redact_contacts(body: str, issues: list[dict]) -> str:
    for issue in issues:
        if issue["type"] == "unverified_contact":
            body = body.replace(issue["detail"], "[removed: unverified contact detail]")
    return body
