# Civic Compass — progress checkpoints

## Architecture (plan)
- **Deterministic layer (no LLM):** Census ZCTA→district relationship files (ZIP ambiguity), live Census Geocoder (`ACS2025_Current` vintage = 119th Congress + 2024 CT legislative maps) for optional street addresses, congress-legislators, the official CGA legislator CSV (cross-checked with Open States), and verified agency JSON → `data/civic.db` (SQLite) with provenance.
- **Agent 1 – Civic Routing Agent (gpt-6-luna):** strict JSON schema whose office field is an enum of the verified candidate ids only.
- **Agent 2 – Letter-Writing Agent (gpt-6-luna):** writes subject + body only; the address block, salutation and contact details are assembled by code from the verified record.
- **Safety layer:**
  - input limits and injection screening; untrusted text wrapped in delimiters; instruction-like sentences stripped before the letter step
  - a per-run recipient allow-list
  - a letter checker for unverified contacts, legal citations and "must respond" claims, with one bounded repair and then redaction
  - a rate limit, a daily budget cap, and a usage log that holds no PII

## Checkpoint 1 — vertical slice (verified)
- [x] Live gpt-6-luna call via Portkey (Responses API + strict JSON schema)
- [x] `.env` found in the parent folder (`~/Desktop/AI Class/.env`)
- [x] DB: 539 members of Congress, 187 CT legislators, 50 agency/directory records (18 New Haven, 13 CT, 16 federal, 3 fallback directories)
- [x] End-to-end run in the CLI and in the browser UI

## Checkpoint 2 — tests, safety, tokenomics, evidence (verified)
- [x] 28 offline pytest tests pass (`python -m pytest -q`)
- [x] Live routing eval, run 1: 18/18 (`evidence/eval_optimized_run1.*`)
- [x] Live prompt-injection test SAFE-1: routing held, injection flagged, instructions stripped, letter clean. Finding: Azure's content filter (via Portkey) blocks the unfiltered letter prompt; now handled.
- [x] Benchmark run 1 (`evidence/tokenomics_run1.*`): baseline ≈12.7k routing input tokens/call vs ≈1.28k optimized; routing quality differences documented (a test-definition error on NH-5/CT-5; US-2 genuinely misrouted to a House member)
- [x] Routing-prompt rule tightened (agency is primary, elected official is escalation); eval + benchmark re-run (run 2 files: `evidence/eval_optimized.*`, `evidence/tokenomics.*`)
- [x] 14 real screenshots in `evidence/screenshots/` (Playwright + local Chrome)
- [x] Fresh-clone dry run with `.env` one level up: install, tests and a live route all OK
- [x] README, `.env.example`, `.gitignore`, `docs/competitors.md`, `docs/user_study_protocol.md`
- [x] `scripts/build_deliverables.py` → `report.html` + `slides.html` (numbers computed from evidence)

## Checkpoint 3 — final verification (2026-10-26)
- [x] Run 2 eval: 18/18 routing, 4/4 malformed rejected, 18/18 letters with 0 checker flags
- [x] Run 2 benchmark: baseline / optimized-cold / optimized-warm all 18/18; routing input ≈12.7k → ≈1.3k tokens/call
- [x] report.html prints to 13 US-letter pages (Chrome, Letter); slides.html has 9 slides, no overflow, arrow keys work
- [x] No API key in any committed file; legislators' home and business contact details and birth dates removed from the raw data
- [x] Local git commit prepared (not pushed)

## Not done / needs the author
- [x] GitHub repo created and pushed: https://github.com/shayajannati/civic-compass-mgt409
- [ ] **Run the user study** (`docs/user_study_protocol.md`) with one real person and record the results in `evidence/user_study.json` (format: `{"date", "participant", "table": {...}, "quotes": [...]}`); then re-run `build_deliverables.py`. The report currently says "pending".
- [ ] Optional: 2–3 minute demo video.
- [ ] Python 3.11 not run locally (only 3.14 is installed). Static check: `vermin` reports a minimum of Python 3.9 for app/, scripts/ and tests/.
