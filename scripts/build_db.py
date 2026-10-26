"""Build data/civic.db from the raw public datasets in data/raw/.

Run:  python scripts/build_db.py            (uses files already in data/raw)
      python scripts/build_db.py --download (re-downloads the public datasets first)

Every table row keeps a source id; the `sources` table records URL and retrieval date.
No LLM is used anywhere in this script.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import sqlite3
import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "data" / "civic.db"

CENSUS_REL = "https://www2.census.gov/geo/docs/maps-data/data/rel2020"
DOWNLOADS = {
    "legislators-current.json": "https://unitedstates.github.io/congress-legislators/legislators-current.json",
    "cga_legislators.csv": "https://www.cga.ct.gov/ftp/pub/data/LegislatorDatabase.csv",
    "openstates_ct.csv": "https://data.openstates.org/people/current/ct.csv",
    "tab20_cd11920_zcta520_natl.txt": f"{CENSUS_REL}/cd-sld/tab20_cd11920_zcta520_natl.txt",
    "tab20_sldl202420_zcta520_st09.txt": f"{CENSUS_REL}/cd-sld/tab20_sldl202420_zcta520_st09.txt",
    "tab20_sldu202420_zcta520_st09.txt": f"{CENSUS_REL}/cd-sld/tab20_sldu202420_zcta520_st09.txt",
    "tab20_zcta520_place20_natl.txt": f"{CENSUS_REL}/zcta520/tab20_zcta520_place20_natl.txt",
}

STATE_FIPS = {
    "01": "AL", "02": "AK", "04": "AZ", "05": "AR", "06": "CA", "08": "CO", "09": "CT", "10": "DE",
    "11": "DC", "12": "FL", "13": "GA", "15": "HI", "16": "ID", "17": "IL", "18": "IN", "19": "IA",
    "20": "KS", "21": "KY", "22": "LA", "23": "ME", "24": "MD", "25": "MA", "26": "MI", "27": "MN",
    "28": "MS", "29": "MO", "30": "MT", "31": "NE", "32": "NV", "33": "NH", "34": "NJ", "35": "NM",
    "36": "NY", "37": "NC", "38": "ND", "39": "OH", "40": "OK", "41": "OR", "42": "PA", "44": "RI",
    "45": "SC", "46": "SD", "47": "TN", "48": "TX", "49": "UT", "50": "VT", "51": "VA", "53": "WA",
    "54": "WV", "55": "WI", "56": "WY", "60": "AS", "66": "GU", "69": "MP", "72": "PR", "78": "VI",
}

SCHEMA = """
CREATE TABLE sources (id TEXT PRIMARY KEY, name TEXT, url TEXT, retrieved TEXT, records INTEGER, notes TEXT);
CREATE TABLE zcta_cd (zcta TEXT, state TEXT, district TEXT, land_share REAL);
CREATE TABLE zcta_sld (zcta TEXT, chamber TEXT, district TEXT, land_share REAL);
CREATE TABLE zcta_place (zcta TEXT, place_geoid TEXT, place_name TEXT, land_share REAL);
CREATE TABLE officials (
  id TEXT PRIMARY KEY, name TEXT, role TEXT, level TEXT, state TEXT, district TEXT, chamber TEXT,
  party TEXT, phone TEXT, email TEXT, contact_url TEXT, website TEXT, address TEXT,
  term_end TEXT, source_id TEXT, source_url TEXT, date_checked TEXT);
CREATE TABLE agencies (
  id TEXT PRIMARY KEY, name TEXT, level TEXT, jurisdiction TEXT, categories TEXT, handles TEXT,
  phone TEXT, email TEXT, contact_url TEXT, complaint_process TEXT, address TEXT,
  source_url TEXT, date_checked TEXT, evidence TEXT, verified_via TEXT, snapshot_url TEXT);
CREATE INDEX i_zcd ON zcta_cd(zcta);
CREATE INDEX i_zsld ON zcta_sld(zcta);
CREATE INDEX i_zpl ON zcta_place(zcta);
CREATE INDEX i_off ON officials(state, chamber, district);
"""


def file_date(path: Path) -> str:
    return dt.date.fromtimestamp(path.stat().st_mtime).isoformat()


def download() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    for name, url in DOWNLOADS.items():
        print(f"downloading {name} ...")
        req = urllib.request.Request(url, headers={"User-Agent": "civic-compass-build/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            (RAW / name).write_bytes(resp.read())
    strip_home_columns(RAW / "cga_legislators.csv")
    trim_openstates(RAW / "openstates_ct.csv")


OPENSTATES_KEEP = ("id", "name", "current_party", "current_district", "current_chamber", "email", "links", "sources")


def trim_openstates(path: Path) -> None:
    """Keep only the columns used for the cross-check (drops birth dates, photos, social handles)."""
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=OPENSTATES_KEEP)
        w.writeheader()
        w.writerows({k: r.get(k, "") for k in OPENSTATES_KEEP} for r in rows)


def strip_home_columns(path: Path) -> None:
    """Remove legislators' home addresses/phones from the stored CGA file (privacy; not needed)."""
    with open(path, encoding="utf-8-sig", errors="replace", newline="") as fh:
        rows = list(csv.DictReader(fh))
    keep = [k for k in rows[0] if not k.lower().startswith(("home ", "business phone"))]
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=keep, quoting=csv.QUOTE_ALL)
        w.writeheader()
        w.writerows({k: r[k] for k in keep} for r in rows)


def pipe_rows(name: str):
    with open(RAW / name, encoding="utf-8-sig") as fh:
        yield from csv.DictReader(fh, delimiter="|")


def load_zcta_cd(con) -> int:
    land: dict[str, float] = {}
    rows = []
    for r in pipe_rows("tab20_cd11920_zcta520_natl.txt"):
        z, geoid = r["GEOID_ZCTA5_20"], r["GEOID_CD119_20"]
        if not z or not geoid:
            continue
        part = float(r["AREALAND_PART"] or 0)
        land[z] = land.get(z, 0) + part
        rows.append((z, STATE_FIPS.get(geoid[:2], geoid[:2]), geoid[2:], part))
    con.executemany(
        "INSERT INTO zcta_cd VALUES (?,?,?,?)",
        [(z, st, d, (p / land[z]) if land[z] else 1.0) for z, st, d, p in rows],
    )
    return len(rows)


def load_zcta_sld(con) -> int:
    n = 0
    for chamber, fname, key in (
        ("lower", "tab20_sldl202420_zcta520_st09.txt", "SLDL2024_20"),
        ("upper", "tab20_sldu202420_zcta520_st09.txt", "SLDU2024_20"),
    ):
        land: dict[str, float] = {}
        rows = []
        for r in pipe_rows(fname):
            z, geoid = r["GEOID_ZCTA5_20"], r[f"GEOID_{key}"]
            if not z or not geoid or geoid.endswith("ZZZ"):
                continue
            part = float(r["AREALAND_PART"] or 0)
            land[z] = land.get(z, 0) + part
            rows.append((z, str(int(geoid[2:])), part))
        con.executemany(
            "INSERT INTO zcta_sld VALUES (?,?,?,?)",
            [(z, chamber, d, (p / land[z]) if land[z] else 1.0) for z, d, p in rows],
        )
        n += len(rows)
    return n


def load_zcta_place(con) -> int:
    rows = []
    for r in pipe_rows("tab20_zcta520_place20_natl.txt"):
        z, place = r["GEOID_ZCTA5_20"], r["GEOID_PLACE_20"]
        if not z or not place or not place.startswith("09"):  # Connecticut places only (pilot)
            continue
        zland = float(r["AREALAND_ZCTA5_20"] or 0)
        share = float(r["AREALAND_PART"] or 0) / zland if zland else 0.0
        rows.append((z, place, r["NAMELSAD_PLACE_20"], share))
    con.executemany("INSERT INTO zcta_place VALUES (?,?,?,?)", rows)
    return len(rows)


def load_congress(con, today: str) -> int:
    data = json.loads((RAW / "legislators-current.json").read_text())
    src = "https://unitedstates.github.io/congress-legislators/legislators-current.json"
    rows = []
    for p in data:
        t = p["terms"][-1]
        name = p["name"].get("official_full") or f'{p["name"]["first"]} {p["name"]["last"]}'
        if t["type"] == "sen":
            role, chamber, district = f"U.S. Senator for {t['state']}", "senate", ""
        else:
            d = t.get("district")
            district = str(d) if d is not None else ""
            label = "at-large" if d in (0, None) else f"district {d}"
            role, chamber = f"U.S. Representative, {t['state']} {label}", "house"
        rows.append((
            f"us-{p['id']['bioguide']}", name, role, "federal", t["state"], district, chamber,
            t.get("party"), t.get("phone"), None, t.get("contact_form") or t.get("url"), t.get("url"),
            t.get("address"), t.get("end"), "congress-legislators", src, today,
        ))
    con.executemany(f"INSERT INTO officials VALUES ({','.join('?' * 17)})", rows)
    return len(rows)


def load_ct_legislators(con, today: str) -> tuple[int, list[str]]:
    """Official CGA file is primary. Home addresses/phones are deliberately NOT loaded."""
    src = "https://www.cga.ct.gov/ftp/pub/data/LegislatorDatabase.csv"
    with open(RAW / "cga_legislators.csv", encoding="utf-8-sig", errors="replace") as fh:
        cga = list(csv.DictReader(fh))
    with open(RAW / "openstates_ct.csv", encoding="utf-8") as fh:
        os_rows = {(r["current_chamber"], r["current_district"]): r for r in csv.DictReader(fh)}
    mismatches, rows = [], []
    for r in cga:
        chamber = "upper" if r["office code"].strip().upper() == "S" else "lower"
        district = str(int(r["dist"]))
        first = (r["commonly used name"] or r["first name"]).strip()
        name = " ".join(x for x in (first, r["last name"].strip(), r["suffix"].strip()) if x)
        title = "State Senator" if chamber == "upper" else "State Representative"
        other = os_rows.get((chamber, district))
        if other is None or r["last name"].strip().lower() not in other["name"].lower():
            mismatches.append(f"{chamber} {district}: CGA={name!r} OpenStates={other['name'] if other else None!r}")
        email, contact = r["email"].strip() or None, r["URL"].strip() or None
        if email and email.lower().startswith("http"):  # some rows hold a contact-form URL here
            email, contact = None, r["email"].strip()
        room = " ".join(x.strip() for x in (r["room"], r["room number"]) if x.strip())
        address = ", ".join(x.strip() for x in (r["capitol street address"], room, r["capitol city"]) if x.strip())
        rows.append((
            f"ct-{chamber}-{district}", name, f"Connecticut {title}, District {district}", "state", "CT",
            district, chamber, r["party"].strip(), r["capitol phone"].strip() or None,
            email, contact, r["URL"].strip() or None,
            address or None, None, "cga-legislator-db", src, today,
        ))
    con.executemany(f"INSERT INTO officials VALUES ({','.join('?' * 17)})", rows)
    return len(rows), mismatches


def load_agencies(con) -> int:
    n = 0
    for f in sorted(RAW.glob("agencies_*.json")):
        for a in json.loads(f.read_text()):
            con.execute(
                f"INSERT OR REPLACE INTO agencies VALUES ({','.join('?' * 16)})",
                (a["id"], a["name"], a["level"], a["jurisdiction"], ",".join(a["categories"]),
                 a.get("handles"), a.get("phone"), a.get("email"), a.get("contact_url"),
                 a.get("complaint_process"), a.get("address"), a["source_url"],
                 a.get("date_checked"), a.get("evidence"),
                 a.get("verified_via") or "Live official page", a.get("snapshot_url")),
            )
            n += 1
    return n


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--download", action="store_true")
    args = ap.parse_args()
    if args.download:
        download()
    tmp = DB.with_suffix(".tmp")
    tmp.unlink(missing_ok=True)
    con = sqlite3.connect(tmp)
    con.executescript(SCHEMA)

    def src(id_, name, fname, records, notes=""):
        con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?)",
                    (id_, name, DOWNLOADS.get(fname, ""), file_date(RAW / fname), records, notes))

    src("census-zcta-cd119", "U.S. Census Bureau 2020 ZCTA to 119th Congressional District relationship file",
        "tab20_cd11920_zcta520_natl.txt", load_zcta_cd(con), "ZIP-level ambiguity detection only")
    src("census-zcta-sld2024-ct", "U.S. Census Bureau 2020 ZCTA to 2024 CT State Legislative District relationship files",
        "tab20_sldl202420_zcta520_st09.txt", load_zcta_sld(con), "House and Senate; CT only")
    src("census-zcta-place-ct", "U.S. Census Bureau 2020 ZCTA to Place relationship file (CT rows)",
        "tab20_zcta520_place20_natl.txt", load_zcta_place(con), "Used to detect New Haven coverage")
    leg_file = RAW / "legislators-current.json"
    n_cong = load_congress(con, file_date(leg_file))
    src("congress-legislators", "unitedstates/congress-legislators (current members)",
        "legislators-current.json", n_cong, "Public-domain dataset maintained by the @unitedstates project")
    n_ct, mism = load_ct_legislators(con, file_date(RAW / "cga_legislators.csv"))
    src("cga-legislator-db", "Connecticut General Assembly official Legislator Database (CSV)",
        "cga_legislators.csv", n_ct,
        f"Cross-checked against Open States CT ({len(mism)} name mismatches). Home addresses excluded.")
    n_ag = load_agencies(con)
    con.execute("INSERT INTO sources VALUES (?,?,?,?,?,?)",
                ("agency-directory", "Civic Compass verified agency directory (official .gov pages)",
                 "data/raw/agencies_*.json", dt.date.today().isoformat(), n_ag,
                 "Each record carries its own source_url and date_checked"))
    con.commit()
    con.close()
    tmp.replace(DB)
    print(f"congress={n_cong} ct_legislators={n_ct} agencies={n_ag} -> {DB}")
    for m in mism:
        print("  cross-check mismatch:", m)
    if n_ag == 0:
        print("WARNING: no agency files found in data/raw/agencies_*.json", file=sys.stderr)


if __name__ == "__main__":
    main()
