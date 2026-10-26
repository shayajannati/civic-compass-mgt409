# Civic Compass

**From your concern to the right government office.**

Civic Compass helps U.S. residents who don't know how government is organized. You describe a problem in plain words ("my landlord won't fix the heat"). The app then:

1. works out whether the problem belongs to your **city, state or federal** government,
2. recommends the **responsible office** (an agency with authority to act, not just an elected official), with verified contact details, the source URL and the date checked,
3. explains **why** that office was chosen, and
4. drafts a **personalized, editable letter** from your facts. You review it, copy or download it, and send it yourself. **Civic Compass never sends anything.**

MGT 409 (AI Foundations for Managers) final project. Yale SOM, fall 2026.

---

## Quick start (about 5 minutes)

Requirements: **Python 3.11 or newer**, and the course `PORTKEY_API_KEY`.

```bash
git clone <this-repo-url> civic-compass
cd civic-compass
python3 -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

Put the key in a file named `.env`, either **in this folder** or **in the folder directly above it**. The app checks this folder first, then the parent:

```bash
cp .env.example .env                 # or ../.env
# edit .env and set PORTKEY_API_KEY=...
```

Run the app:

```bash
uvicorn app.main:app --port 8765
```

Open **http://127.0.0.1:8765**, then click an example chip (for example "No heat — New Haven") and press **Find the right office**.

- `http://127.0.0.1:8765/api/health` shows whether the key was found (`"env_file": "repository folder"` or `"parent folder"`). It never shows the key itself.
- Without a key, the page shows a setup message. Directory lookups still work, but the two AI agents do not.
- The verified directory database `data/civic.db` is committed. No download or build step is needed.

### Tests

```bash
python -m pytest -q                      # 28 offline tests: no model calls, no network
python scripts/run_eval.py               # live routing evaluation (18 cases, about $0.002)
python scripts/benchmark.py              # live tokenomics benchmark (about $0.02)
```

---

## Architecture

```
 browser form ──► FastAPI ──► validate + injection screen (no LLM)
                               │
                               ├─► ZIP → districts (local SQLite, Census relationship files)
                               │   optional street → Census Geocoder (exact districts; address not stored)
                               ├─► verified candidate offices + unique officials (SQLite)
                               │
                               ├─► Agent 1: Civic Routing Agent (gpt-6-luna, strict JSON schema;
                               │            office id must be one of the verified candidate ids)
                               ├─► verify choice, correct level, allow-list recipients for this run
                               │
                               ├─► Agent 2: Letter-Writing Agent (gpt-6-luna; writes subject+body only)
                               ├─► letter checker: invented contacts / legal citations / "must respond"
                               │   claims → one bounded repair → redaction
                               └─► letter assembled with the verified address block → user edits,
                                   ticks "I reviewed this", then copies/downloads
```

| Path | What it is |
|---|---|
| `app/main.py` | FastAPI routes, request-size limit, rate limit, error mapping |
| `app/pipeline.py` | Orchestration and verification between the agents |
| `app/agents.py` | The two agents (prompts and JSON schemas) |
| `app/llm.py` | The only model client: gpt-6-luna via Portkey, token/cost logging, daily budget |
| `app/geo.py`, `app/directory.py` | Deterministic geography and directory lookups (no LLM) |
| `app/safety.py` | Input hygiene, prompt-injection screen, letter checker |
| `scripts/build_db.py` | Rebuilds `data/civic.db` from `data/raw/` (`--download` refreshes public datasets) |
| `scripts/run_eval.py`, `scripts/benchmark.py` | Live evaluation and tokenomics |
| `scripts/capture_screenshots.py` | Captures report screenshots from the running app (dev-only, `requirements-dev.txt`) |
| `evidence/` | Results of real runs: evaluation, benchmark, screenshots |
| `report.html`, `slides.html` | Course deliverables, self-contained |

Model: **gpt-6-luna only**, through Portkey (`https://api.portkey.ai/v1`, OpenAI Responses API), using the course key `PORTKEY_API_KEY`. No other model is called at runtime.

## Data and coverage

| Data | Source | Coverage |
|---|---|---|
| Members of Congress | [unitedstates/congress-legislators](https://github.com/unitedstates/congress-legislators) | Nationwide |
| CT state legislators | [CT General Assembly Legislator Database (CSV)](https://www.cga.ct.gov/ftp/pub/data/LegislatorDatabase.csv), cross-checked against [Open States](https://open.pluralpolicy.com/data/) | All 187 seats |
| ZIP → district overlap | U.S. Census 2020 ZCTA relationship files (119th Congress, 2024 CT legislative districts) | Nationwide (Congress), CT (legislature) |
| Exact districts from an address | [U.S. Census Geocoder](https://geocoding.geo.census.gov/) (`ACS2025_Current` vintage) | Nationwide, live and optional |
| Agencies | Official pages, one record each with `source_url` and `date_checked` (`data/raw/agencies_*.json`) | 18 New Haven, 13 Connecticut, 16 federal, plus 3 fallback directories |

Known limitations:

- **New Haven pages:** newhavenct.gov blocks automated access (HTTP 403). The New Haven city-department records were therefore read from Internet Archive snapshots of the official pages, dated June to October 2026, and each record links its snapshot.
- **Federal pages:** a few federal sites blocked automated reads. Those records come from the agency's official USA.gov directory page.
- **Elected officials:** these reflect who was serving on 2026-10-26, before the November 3, 2026 election.
- **Outside the pilot:** outside Connecticut, state- and city-level results link to official directories. They are clearly labelled as limited coverage.

### Switching or refreshing the dataset

```bash
python scripts/build_db.py              # rebuild from the files in data/raw/
python scripts/build_db.py --download   # re-download Census, congress-legislators, CGA and Open States data
CIVIC_DB_PATH=/path/to/other.db uvicorn app.main:app --port 8765   # point the app at another database
```

To add a city, add a `data/raw/agencies_<city>.json` file in the same format as the others, then rebuild.

## Safety and privacy

- **Office choice:** the agents have no tools and cannot send anything. The routing agent can only choose an office from the verified list for that request, enforced by a JSON-schema enum, and all contact details come from the database.
- **Prompt injection:** issue text is wrapped as quoted data and screened for injection patterns. Sentences that read like instructions to the AI are kept out of the letter prompt. The provider's own content filter is a further layer.
- **Letter checks:** each letter is checked for invented emails, phone numbers and URLs, unsupported legal citations, and claims that officials *must* respond. It gets at most one repair attempt; anything still invalid is redacted.
- **Limits:** 20 KB request limit, 2,000-character description, 45-second API timeout, output-token caps, 12 requests per minute per IP, and a $2/day model budget (`CIVIC_DAILY_BUDGET_USD`).
- **What is stored:** names, addresses and issue text are **not stored**. `data/usage_log.jsonl` keeps only token counts, latency and cost.
- **Legislator data:** the stored CGA and Open States files have legislators' home addresses, home and business phones, and birth dates removed (`scripts/build_db.py` does this on every download).

## License and data credits

The code is for coursework. Directory data comes from the public sources linked above. Check each source's own terms before reusing it.
