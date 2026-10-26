"""Deterministic geography: ZIP -> possible districts, street address -> exact districts.

No LLM is used here. A ZIP code (ZCTA) can overlap several districts; in that case we
report every candidate and never pick one. A street address, if the user volunteers it,
is sent once to the U.S. Census Geocoder and is not stored.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from functools import lru_cache

import httpx

from .db import query

GEOCODER_URL = "https://geocoding.geo.census.gov/geocoder/geographies/address"
# ACS2025 vintage = 119th Congressional Districts + 2024 state legislative districts,
# i.e. the maps under which current officeholders were elected.
GEOCODER_VINTAGE = "ACS2025_Current"
MIN_SHARE = 0.005  # ignore boundary slivers below 0.5% of a ZIP's land area
NEW_HAVEN_PLACE = "0952000"


@dataclass
class Location:
    zip: str
    states: list[str] = field(default_factory=list)
    cd: list[str] = field(default_factory=list)          # districts as "CT-3"
    ct_lower: list[str] = field(default_factory=list)
    ct_upper: list[str] = field(default_factory=list)
    new_haven: str = "no"                                 # "yes" | "partial" | "no"
    town: str | None = None
    method: str = "zip"                                   # "zip" | "address"
    found: bool = True
    notes: list[str] = field(default_factory=list)

    @property
    def state(self) -> str | None:
        return self.states[0] if len(self.states) == 1 else None

    @property
    def coverage(self) -> str:
        if self.new_haven == "yes":
            return "new_haven"
        if self.state == "CT":
            return "connecticut"
        return "national" if self.found else "unknown"

    def summary(self) -> dict:
        return {
            "zip": self.zip, "states": self.states, "congressional_districts": self.cd,
            "ct_house_districts": self.ct_lower, "ct_senate_districts": self.ct_upper,
            "new_haven": self.new_haven, "town": self.town, "method": self.method,
            "coverage": self.coverage, "found": self.found, "notes": self.notes,
        }


def _districts(rows, fmt) -> list[str]:
    return sorted({fmt(r) for r in rows if r["land_share"] >= MIN_SHARE},
                  key=lambda s: [int(x) if x.isdigit() else x for x in re.split(r"(\d+)", s)])


def lookup_zip(zip5: str) -> Location:
    loc = Location(zip=zip5)
    cd_rows = query("SELECT * FROM zcta_cd WHERE zcta=?", (zip5,))
    if not cd_rows:
        loc.found = False
        loc.notes.append("ZIP code not found in Census ZIP Code Tabulation Areas (it may be a PO-box-only or new ZIP).")
        return loc
    loc.cd = _districts(cd_rows, lambda r: f"{r['state']}-{int(r['district']) if r['district'].isdigit() else r['district']}")
    loc.states = sorted({c.split("-")[0] for c in loc.cd}) or sorted({r["state"] for r in cd_rows})
    if "CT" in loc.states:
        sld = query("SELECT * FROM zcta_sld WHERE zcta=?", (zip5,))
        loc.ct_lower = _districts([r for r in sld if r["chamber"] == "lower"], lambda r: r["district"])
        loc.ct_upper = _districts([r for r in sld if r["chamber"] == "upper"], lambda r: r["district"])
        places = query("SELECT * FROM zcta_place WHERE zcta=? ORDER BY land_share DESC", (zip5,))
        nh = next((p["land_share"] for p in places if p["place_geoid"] == NEW_HAVEN_PLACE), 0.0)
        loc.new_haven = "yes" if nh >= 0.95 else "partial" if nh >= MIN_SHARE else "no"
        if places and places[0]["land_share"] >= 0.95:
            loc.town = places[0]["place_name"]
        if loc.new_haven == "partial":
            loc.notes.append("This ZIP code is only partly inside the City of New Haven.")
    return loc


@lru_cache(maxsize=256)
def _geocode(street: str, zip5: str) -> dict | None:
    params = {"street": street, "zip": zip5, "benchmark": "Public_AR_Current",
              "vintage": GEOCODER_VINTAGE, "format": "json"}
    resp = httpx.get(GEOCODER_URL, params=params, timeout=15)
    resp.raise_for_status()
    matches = resp.json().get("result", {}).get("addressMatches", [])
    return matches[0]["geographies"] if matches else None


def _layer(geo: dict, needle: str) -> list[dict]:
    return next((v for k, v in geo.items() if needle in k), [])


def lookup_address(street: str, zip5: str) -> Location:
    """Exact districts for one street address; falls back to ZIP-only on failure."""
    base = lookup_zip(zip5)
    try:
        geo = _geocode(street.strip(), zip5)
    except Exception:
        base.notes.append("The Census address lookup was unavailable, so results use the ZIP code only.")
        return base
    if not geo:
        base.notes.append("The Census Geocoder could not match that street address; results use the ZIP code only.")
        return base
    loc = Location(zip=zip5, method="address")
    state = (_layer(geo, "States") or [{}])[0].get("STUSAB")
    loc.states = [state] if state else base.states
    cd = _layer(geo, "Congressional Districts")
    if cd:
        num = cd[0].get("BASENAME") or cd[0].get("CD119") or ""
        loc.cd = [f"{state}-{int(num) if num.isdigit() else 0}"]
    if state == "CT":
        lower, upper = _layer(geo, "Legislative Districts - Lower"), _layer(geo, "Legislative Districts - Upper")
        loc.ct_lower = [str(int(lower[0]["BASENAME"]))] if lower and lower[0].get("BASENAME", "").isdigit() else []
        loc.ct_upper = [str(int(upper[0]["BASENAME"]))] if upper and upper[0].get("BASENAME", "").isdigit() else []
    place = _layer(geo, "Incorporated Places")
    loc.town = place[0]["NAME"] if place else None
    loc.new_haven = "yes" if place and place[0].get("GEOID") == NEW_HAVEN_PLACE else "no"
    if state and base.states and state not in base.states:
        loc.notes.append("The street address and ZIP code point to different states; please double-check them.")
    return loc
