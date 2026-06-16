# Lumen Healthcare Planner — Build Plan

**Hackathon:** Databricks Apps & Agents for Good 2026 (in partnership with OpenAI)
**Project Period:** June 15 – June 16, 2026
**Hard Deadline:** June 16, 2026 — 2:30 PM PT (Sponsor clock is official)
**Judging window:** 2:30 PM – 6:00 PM PT | Winners announced ~6:00 PM PT
**Criteria (equally weighted):** Business Applicability · Data Relevance · Creativity · Thoroughness · Well-Architected

---

## What We Are Building

A single Databricks App covering all 4 tracks for a non-technical healthcare planner, NGO coordinator, or analyst working with 10,088 messy Indian healthcare facility records.

| Track | Core Question | Minimum Workflow |
|---|---|---|
| 1 — Facility Trust Desk | Can this facility do what it claims? | Select capability + region → ranked facilities → citations → override with note |
| 2 — Medical Desert Planner | Where are the highest-risk care gaps? | Capability + geography → regional coverage → drill into records → save scenario |
| 3 — Referral Copilot | Where should a patient go? | Location + care need → ranked shortlist with distance + evidence → save to shortlist |
| 4 — Data Readiness Desk | What needs fixing before data can be trusted? | Completeness profile → flagged-record queue → reviewer decisions persisted |

---

## Non-Negotiable Requirements (from rules.md §4.2 and §4.3)

These are hard pass/fail at Stage 1 judging.

- [ ] App runs on Databricks Free Edition
- [ ] App is built on Lakebase (rules.md §4.2 — explicit, not optional)
- [ ] Public GitHub repo — open-source license — commit history must show activity during June 15–16
- [ ] Demo video ≤ 3 minutes — uploaded to YouTube, Vimeo, Facebook Video, or Youku — set to public
- [ ] Devpost submission with: working demo link, text description, GitHub URL, video URL
- [ ] Demo/app publicly accessible OR login credentials provided to judges
- [ ] All submission materials in English

---

## Architecture (Confirmed — Lakebase is Required)

The rules explicitly say "built on Lakebase". The check-list says "sync your clean data to Lakebase using the Sync Tables template". All data access goes through Lakebase via psycopg2.

```
Lakebase (hackathon-healthcare instance)
  database: healthcare
  ├── schema: lakebase_sync_clean     ← synced from dais2026.lakebase_sync_clean (READ)
  │     ├── facilities_clean          ← 10,088 rows, state_normalized added
  │     ├── india_post_pincode_directory
  │     ├── nfhs_5_district_health_indicators
  │     └── geo_hierarchy             ← if created
  └── schema: app_data               ← user persistence (READ + WRITE)
        ├── user_notes
        ├── user_overrides
        ├── shortlists
        ├── scenarios
        ├── trust_scores
        └── trust_overrides
```

App connects via psycopg2 → Lakebase endpoint: ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com
Token auth: SDK generates credential via w.database.generate_database_credential(), refreshed every 15 min.

---

## Dataset Summary

| Source | Location in Lakebase | Rows | Key Use |
|---|---|---|---|
| facilities_clean | lakebase_sync_clean.facilities_clean | 10,088 | All 4 tracks — primary |
| india_post_pincode_directory | lakebase_sync_clean.india_post_pincode_directory | 165,627 | Track 3 — enrich postcodes with district/state. Row grain = post office not pincode — deduplicate before joining |
| nfhs_5_district_health_indicators | lakebase_sync_clean.nfhs_5_district_health_indicators | 706 | Track 2 — district health burden overlay. Asterisk values = NULL not zero. Parenthesized values = low-sample estimates |

**Key field coverage in facilities_clean:**
| Field | Coverage | Notes |
|---|---|---|
| description | ~100% | Free text — primary evidence source |
| capability | 99.7% | JSON array string — treat as claims not ground truth |
| procedure | 92.5% | JSON array string |
| equipment | 77.0% | JSON array string |
| numberDoctors | 36.4% | Sparse — communicate uncertainty |
| capacity | 25.2% | Sparse — communicate uncertainty |
| yearEstablished | 47.8% | |
| state_normalized | 99.0% | Added by ETL — 255 raw variants → 35 canonical states |

---

## Codebase — Current State

**Location:** /Workspace/Users/krish.kilaru@lumenalta.com/lumen-healthcare-planner/

| File | Status | Notes |
|---|---|---|
| app.py | Works — needs SYNCED_SCHEMA fix | References geo_hierarchy table that may not exist yet |
| db.py | 2 bugs blocking all routes | See Step 1 below |
| scoring.py | OK | Trust scoring engine — field presence checks only, no SQL |
| routes_trust.py | OK — needs SYNCED_SCHEMA fix | Already updated to facilities_clean + state_normalized |
| routes_deserts.py | OK — needs SYNCED_SCHEMA fix | Already updated to facilities_clean + state_normalized |
| routes_referral.py | OK — needs SYNCED_SCHEMA fix | Already updated to facilities_clean + state_normalized |
| routes_readiness.py | OK — needs SYNCED_SCHEMA fix | Already using state_normalized + facilities_clean |
| routes_persistence.py | OK | Uses APP_SCHEMA only |
| app.yaml | Partial | Has lakebase binding, missing env var exposure |
| requirements.txt | Needs addition | Missing any spatial lib if geo joins needed |
| static/index.html | Placeholder | Needs full React SPA |

---

## Step 1 — Fix db.py (BLOCKER — all routes fail without this)

Two bugs in db.py prevent any route from working:

**Bug 1:** `DB_USER = os.environ.get("PGUSER", "")` — empty default string breaks all psycopg2 connections.
- Fix: `DB_USER = os.environ.get("PGUSER", "token")`

**Bug 2:** `SYNCED_SCHEMA = "data"` — wrong schema name. User has synced clean data to `dais2026.lakebase_sync_clean` in UC. The Postgres schema in Lakebase will match the UC schema name.
- Fix: `SYNCED_SCHEMA = "lakebase_sync_clean"`

- [ ] Change `DB_USER` default to `"token"`
- [ ] Change `SYNCED_SCHEMA` to `"lakebase_sync_clean"` (verify actual schema name after syncing)
- [ ] Verify `DB_NAME = "healthcare"` matches the Lakebase logical database name

---

## Step 2 — Fix app.yaml (BLOCKER — env vars not exposed to app)

The lakebase resource binding is present but the env vars are not mapped to what db.py reads (PGHOST, PGUSER, PGPORT).

- [ ] Confirm app.yaml exposes PGHOST, PGUSER, PGPORT from the lakebase-healthcare resource
- [ ] If not, add explicit env var mappings so the app picks them up at runtime

---

## Step 3 — Verify Synced Schema Name

Before assuming `lakebase_sync_clean` is the correct Postgres schema name:

- [ ] Connect to Lakebase and run: `SELECT schema_name FROM information_schema.schemata;`
- [ ] Confirm tables `facilities_clean`, `india_post_pincode_directory`, `nfhs_5_district_health_indicators` are present
- [ ] If schema name differs, update `SYNCED_SCHEMA` in db.py accordingly

---

## Step 4 — Test All 4 Tracks End-to-End

- [ ] `/api/health` returns `{"status": "healthy", "db": "connected"}`
- [ ] `/api/overview` returns total_facilities, total_states, total_districts, total_specialties
- [ ] `/api/filters/states` returns states list with facility counts
- [ ] `/api/filters/districts?state=MAHARASHTRA` returns districts
- [ ] **Track 1:** `/api/trust/scores?capability=ICU&state=MAHARASHTRA` returns ranked facilities with trust signals and citations
- [ ] **Track 2:** `/api/deserts/analysis?state=BIHAR` returns desert coverage map
- [ ] **Track 2:** `/api/deserts/nfhs-overlay` joins NFHS-5 health burden data
- [ ] **Track 3:** `/api/referral/search?specialty=cardiology&state=KARNATAKA` returns ranked candidates with distance
- [ ] **Track 4:** `/api/readiness/profile` returns field coverage percentages
- [ ] **Track 4:** `/api/readiness/state-summary` returns completeness by state
- [ ] **Persistence:** `POST /api/notes` writes note to Lakebase app_data
- [ ] **Persistence:** `POST /api/shortlist` saves facility to shortlist
- [ ] **Persistence:** `POST /api/trust/override/{id}` saves override with note
- [ ] **Persistence:** `POST /api/scenarios` saves a planning scenario

---

## Step 5 — Build the Frontend (Biggest time investment)

Replace the static `index.html` placeholder with a full React SPA.

**Stack:** Vite + React + Tailwind CSS + shadcn/ui
**Palette:** `#FF3621` (Databricks red) · `#0B2026` (dark) · `#EEEDE9` (off-white) · `#F9F7F4` (background)

**Pages required:**

- [ ] Home / Overview — KPI counters (facilities, states, specialties) + 4-track navigation cards
- [ ] Track 1 — Facility Trust Desk
  - Capability selector (ICU, maternity, emergency, oncology, trauma, NICU, dialysis)
  - State + district filters
  - Ranked facility table with trust signal badges (Strong / Partial / Weak / No claim)
  - Expandable citation panel showing raw text from description, capability, procedure
  - Override form — planner can change signal + add note
- [ ] Track 2 — Medical Desert Planner
  - Capability + geography selectors (state/district/city/pincode)
  - Regional coverage table with desert severity indicator
  - NFHS-5 health burden overlay (high burden + low facility = highest priority)
  - Save scenario button → stores filters + results to Lakebase
- [ ] Track 3 — Referral Copilot
  - Specialty input + location/state input
  - Ranked candidate list with: distance, trust signal, matching evidence, missing evidence warnings
  - Add to shortlist button per candidate
  - Shortlist sidebar showing saved candidates
- [ ] Track 4 — Data Readiness Desk
  - Field coverage bar chart (all 21 profiled fields)
  - State completeness heatmap
  - Flagged record queue (facilities with contradictions or suspicious claims)
  - Reviewer decision buttons (Accept / Flag / Reject) that persist to Lakebase

**Cross-cutting UI requirements from requirements.md:**
- [ ] Every score, ranking, or claim must cite the underlying facility text
- [ ] Uncertainty must be communicated — never present weak evidence as fact
  - Show evidence count: "Based on 1 field" vs "Based on 4 fields"
  - Show when a field is sparse (e.g. numberDoctors only 36% coverage)
- [ ] Non-technical user friendly — no jargon, clear labels, simple workflows

---

## Step 6 — Deploy to Databricks Apps

- [ ] Run `databricks apps deploy` from the lumen-healthcare-planner directory
- [ ] Check startup logs: `databricks apps logs lumen-healthcare-planner`
- [ ] Verify `/api/health` returns healthy on the deployed URL
- [ ] Test at least one full workflow per track on the deployed app
- [ ] Save the public app URL — needed for Devpost

---

## Step 7 — GitHub Repository

- [ ] Create a **new public** GitHub repository (not existing — rules §4.8 prohibits prior projects)
- [ ] Push all code — commit history must show activity during June 15–16
- [ ] Add an open-source license file (MIT recommended)
- [ ] Write README.md covering: what the app does, how to run it, architecture diagram, dataset credits
- [ ] Do NOT commit: .env files, credentials, tokens, PGPASSWORD
- [ ] Verify repo is publicly visible and URL is accessible

---

## Step 8 — Demo Video

- [ ] Screen record — max 3 minutes (hard limit — longer = Stage 1 fail)
- [ ] Show the app functioning: complete at least 2 full track workflows
- [ ] Demonstrate: evidence citations, uncertainty display, saving a note/shortlist/scenario
- [ ] Upload to YouTube or Vimeo — set to **public**
- [ ] Copy the video URL

---

## Step 9 — Devpost Submission

- [ ] Go to https://dais-for-good-2026.devpost.com/
- [ ] One representative submits on behalf of the team
- [ ] Fill in: project name, text description (features + what problem it solves)
- [ ] Add: working demo/app URL, GitHub repo URL, video URL
- [ ] Submit **before 2:30 PM PT on June 16** — no changes after this

---

## Judging Criteria — How We Hit Each One

| Criterion | How We Satisfy It |
|---|---|
| Business Applicability | Directly serves NGO planners and coordinators making real healthcare decisions in India — a documented gap in public health planning tools |
| Data Relevance | Uses Virtue Foundation facilities dataset, NFHS-5 district health indicators, India Post pincode directory — all enriched and synced via Lakebase as required |
| Creativity | Trust scoring with evidence citations and uncertainty signals; state normalization via ai_classify; combining supply-side (facilities) with demand-side (NFHS-5) data |
| Thoroughness | All 4 tracks with complete non-technical workflows; every claim cited; confidence levels shown; reviewer decisions persisted |
| Well-Architected | Single psycopg2 connection layer to Lakebase for all reads and writes; stateless FastAPI; token auto-refresh; clean separation of synced data schema vs app persistence schema |

---

## Data Quality Notes (Do Not Lose)

- `india_post_pincode_directory`: row grain = **post office, not pincode**. A single PIN can appear on multiple rows. Always deduplicate before joining on pincode or rows will fan out.
- `nfhs_5_district_health_indicators`: asterisk `*` values = suppressed data → treat as NULL, not zero. Parenthesized values like `(29.5)` = low-sample estimates → flag as uncertain in UI.
- `facilities_clean`: capability, procedure, equipment are JSON arrays stored as strings → parse before display. `state_normalized` covers 99.0% of rows; 96 rows have NULL (genuine garbage in source).
- District name matching across datasets is unreliable — prefer spatial join on lat/lon over string matching.

---

## Time Estimate

| Step | Effort |
|---|---|
| Fix db.py (2 bugs) | 15 min |
| Fix app.yaml env vars | 15 min |
| Verify synced schema name | 10 min |
| Test all 4 tracks | 30 min |
| Build frontend (React SPA) | 3–4 hrs |
| Deploy + smoke test | 30 min |
| GitHub repo + README | 20 min |
| Demo video (record + upload) | 30 min |
| Devpost submission | 15 min |
| **Total** | **~6.5 hrs** |
