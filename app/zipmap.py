"""ZIP-area map data (display only; never used for routing or district selection).

Center point: U.S. Census 2025 Gazetteer (local SQLite). Boundary: the ZCTA polygon from
the Census TIGERweb service, fetched server-side by ZIP code only (never an address),
cached, with a short timeout. If TIGERweb is unavailable, the map shows the center point.
"""

from __future__ import annotations

from functools import lru_cache

import httpx

from .db import query
from .geo import lookup_zip

TIGERWEB = ("https://tigerweb.geo.census.gov/arcgis/rest/services/TIGERweb/"
            "PUMA_TAD_TAZ_UGA_ZCTA/MapServer/7/query")


@lru_cache(maxsize=512)
def _boundary(zip5: str) -> dict | None:
    params = {"where": f"ZCTA5='{zip5}'", "outFields": "ZCTA5", "returnGeometry": "true", "outSR": "4326",
              "geometryPrecision": "5", "maxAllowableOffset": "0.0005", "f": "geojson"}
    try:
        r = httpx.get(TIGERWEB, params=params, timeout=5)
        r.raise_for_status()
        feats = r.json().get("features") or []
        return feats[0]["geometry"] if feats else None
    except Exception:
        return None


def zip_map(zip5: str) -> dict:
    loc = lookup_zip(zip5)
    pt = query("SELECT lat, lon FROM zcta_point WHERE zcta=?", (zip5,))
    if not loc.found or not pt:
        return {"zip": zip5, "found": False}
    place = loc.town or ""
    state = ", ".join(loc.states)
    label = f"ZIP {zip5} · {place.replace(' city', '').replace(' town', '')}, {state}" if place else f"ZIP {zip5} · {state}"
    notes = []
    if len(loc.cd) > 1:
        notes.append(f"This ZIP area overlaps {len(loc.cd)} congressional districts.")
    if len(loc.ct_lower) > 1:
        notes.append(f"It overlaps {len(loc.ct_lower)} Connecticut House districts.")
    return {
        "zip": zip5, "found": True, "label": label, "lat": pt[0]["lat"], "lon": pt[0]["lon"],
        "boundary": _boundary(zip5), "ambiguity": notes,
        "sources": {"point": "U.S. Census Bureau 2025 Gazetteer (ZCTA internal point)",
                    "boundary": "U.S. Census Bureau TIGERweb, 2020 ZIP Code Tabulation Areas"},
    }
