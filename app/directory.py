"""Deterministic candidate retrieval from the verified local directory.

The routing agent may only choose among the ids returned here; every contact detail
shown to the user is read from these records, never from model output.
"""

from __future__ import annotations

from .db import query
from .geo import Location

LEVELS = ("municipal", "state", "federal")


def _agencies(level: str, jurisdiction: str, category: str) -> list[dict]:
    rows = query("SELECT * FROM agencies WHERE level=? AND jurisdiction=? ORDER BY name", (level, jurisdiction))
    if category != "other":  # "other" keeps every office at the level so nothing is hidden
        rows = [r for r in rows if category in r["categories"].split(",")]
    for r in rows:
        r["kind"] = "directory" if jurisdiction == "Directory" else "agency"
    return rows


def agency_candidates(loc: Location, category: str) -> list[dict]:
    out: list[dict] = []
    if loc.new_haven in ("yes", "partial"):
        out += _agencies("municipal", "New Haven, CT", category)
    else:
        out += _agencies("municipal", "Directory", category)
    if loc.state == "CT":
        out += _agencies("state", "Connecticut", category)
    else:
        out += _agencies("state", "Directory", category)
    out += _agencies("federal", "United States", category)
    return out


def query_all_agencies() -> list[dict]:
    """Every agency record (used only by the unoptimized baseline for tokenomics)."""
    rows = query("SELECT * FROM agencies ORDER BY level, name")
    for r in rows:
        r["kind"] = "directory" if r["jurisdiction"] == "Directory" else "agency"
    return rows


def _official(where: str, params: tuple) -> list[dict]:
    rows = query(f"SELECT * FROM officials WHERE {where} ORDER BY name", params)
    for r in rows:
        r["kind"] = "official"
    return rows


def elected_officials(loc: Location) -> dict:
    """Unique officials (safe to recommend) and ambiguous possibilities (never auto-chosen)."""
    unique: list[dict] = []
    possible: dict[str, list[dict]] = {}
    gaps: list[str] = []
    if loc.state:
        unique += _official("level='federal' AND chamber='senate' AND state=?", (loc.state,))
    reps = []
    for cd in loc.cd:
        st, num = cd.split("-")
        reps += _official("level='federal' AND chamber='house' AND state=? AND district=?", (st, str(int(num))))
    if len(loc.cd) == 1 and reps:
        unique += reps
    elif len(loc.cd) > 1:
        possible["U.S. House"] = reps
        gaps.append(f"Your ZIP code overlaps {len(loc.cd)} congressional districts ({', '.join(loc.cd)}).")
    if loc.state == "CT":
        for chamber, label, dists in (("lower", "CT House", loc.ct_lower), ("upper", "CT Senate", loc.ct_upper)):
            rows = []
            for d in dists:
                rows += _official("level='state' AND chamber=? AND district=?", (chamber, d))
            if len(dists) == 1:
                unique += rows
            elif len(dists) > 1:
                possible[label] = rows
                gaps.append(f"Your ZIP code overlaps {len(dists)} {label} districts.")
    return {"unique": unique, "possible": possible, "gaps": gaps}


def get_record(record_id: str) -> dict | None:
    rows = query("SELECT * FROM agencies WHERE id=?", (record_id,))
    if rows:
        return {**rows[0], "kind": "directory" if rows[0]["jurisdiction"] == "Directory" else "agency"}
    rows = query("SELECT * FROM officials WHERE id=?", (record_id,))
    return {**rows[0], "kind": "official"} if rows else None


def sources() -> list[dict]:
    return query("SELECT * FROM sources ORDER BY id")


def compact_line(r: dict) -> str:
    """One short line per candidate for the routing prompt (token-lean)."""
    if r["kind"] == "official":
        return f"{r['id']} | elected | {r['name']}, {r['role']}"
    return f"{r['id']} | {r['level']} | {r['name']} | {r.get('handles') or ''}"
