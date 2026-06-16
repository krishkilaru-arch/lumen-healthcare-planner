# Lumen Healthcare Planner

**An intelligent healthcare infrastructure planning tool for India — built for the DAIS 2026 Apps & Agents for Good Hackathon**

[![Built on Databricks](https://img.shields.io/badge/Built%20on-Databricks-FF3621)](https://databricks.com)
[![Powered by Lakebase](https://img.shields.io/badge/Powered%20by-Lakebase-0B2026)](https://databricks.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

---

## Inspiration

India has 1.4 billion people but no single trustworthy source of truth about its healthcare infrastructure. We watched NGO coordinators spend weeks manually verifying facility claims, saw planners make resource allocation decisions based on data that hadn't been updated since before Telangana existed as a state, and met referral teams who couldn't answer "where should this patient go?" with any confidence.

The Virtue Foundation dataset — 10,088 facilities — crystallized the problem: the data *exists*, but it's riddled with quality issues that make it dangerous to use naively. Clinics claim ICU capabilities with no equipment listed. Facilities in Telangana are still tagged "Andhra Pradesh." Doctor counts are missing for 64% of records. Someone needed to build a tool that doesn't hide these problems — it surfaces them, scores them, and lets planners make informed decisions anyway.

We were inspired by the idea that **transparency about data limitations is more valuable than a polished dashboard that pretends the data is clean**.

---

## What It Does

Lumen Healthcare Planner is a single unified app covering all 4 hackathon tracks, designed for non-technical healthcare planners, NGO coordinators, and policy analysts:

1. **Facility Trust Desk** — Evaluates whether a facility can actually deliver the care it claims. Every assessment comes with a trust score, a signal (Strong/Partial/Weak/No Evidence), and exact citations from the source data. Users can override and annotate.

2. **Medical Desert Planner** — Finds districts where critical care is scarce, cross-references with NFHS-5 health outcomes to distinguish real gaps from data gaps, and maps them with severity and confidence labels.

3. **Referral Copilot** — Ranks facilities for a patient's medical need by relevance, trust, proximity, and capacity. Shows why each facility was recommended and what evidence is missing.

4. **Data Readiness Desk** — Profiles the entire dataset's quality, flags suspicious records (future year established, coordinates outside India, clinics claiming trauma surgery), and provides a review queue where planners can approve, reject, or escalate.

All decisions, notes, overrides, and scenarios persist to Lakebase across sessions.

---

## How We Built It

**Backend**: FastAPI (Python) with 6 route modules — one per track plus persistence and a trust scoring engine. The scoring algorithm weighs completeness (40%), verification (35%), and recency (25%) to produce a 0–1 trust score for every facility.

**Database**: Databricks Lakebase (Postgres-compatible) with OAuth token auto-refresh every 15 minutes via the Databricks SDK. Two schemas — `lakebase_pg_sync` for read-only synced data, `app_data` for user-generated persistence (notes, overrides, shortlists, scenarios, review decisions).

**Data Engineering**: ETL pipeline that normalizes 255 raw state name variants to 35 canonical states, parses JSON-in-string fields at runtime, and fuzzy-matches district names across datasets (difflib, 0.85 cutoff, zero false positives verified).

**Frontend**: Single-page app with Tailwind CSS, Leaflet.js for map visualization, and cascading filter dropdowns (capability → state → district → city) that re-count matching facilities at each level.

**Specialty Normalization**: 2,768 raw camelCase specialty labels mapped to 55 canonical parent specialties via a keyword-matching engine with 224 rules.

**Deployment**: Databricks Apps with `app.yaml` binding to the Lakebase instance.

---

## Challenges We Ran Into

**State separation artifacts**: The 2014 Andhra Pradesh → Telangana split (and earlier Bihar → Jharkhand, UP → Uttarakhand, MP → Chhattisgarh splits) mean facilities are geographically misattributed. We could normalize state *names* but not re-assign facilities to their correct post-split state without district-level geocoding — which the data doesn't consistently support (coordinates are missing for many records). We chose to be transparent about this limitation rather than guess.

**JSON arrays stored as strings**: The `capability`, `procedure`, `equipment`, and `specialties` fields are all JSON arrays encoded as TEXT. Some contain nested objects, some have trailing commas, some are the literal string "null". We built a defensive parser (`safe_json_parse`) that handles all variants without crashing.

**Sparse critical fields**: Only 36% of facilities report doctor counts and 25% report bed capacity. This makes any scoring model inherently uncertain — we addressed this by making uncertainty a first-class concept in the UI rather than imputing values.

**NFHS-5 district name mismatch**: The health indicators dataset uses different district spellings than the facility data. Exact joins miss ~30% of matches. Fuzzy matching at 0.85 cutoff recovered them with zero false positives (verified manually).

**Lakebase token expiry**: OAuth tokens expire after 1 hour. Early in development we hit silent auth failures mid-session. We implemented a 15-minute proactive refresh cycle to stay well within the window.

---

## Accomplishments That We're Proud Of

- **Radical transparency**: Every trust score explains itself. Every desert label shows its confidence. Every referral recommendation lists what evidence is missing. No black boxes.
- **All 4 tracks in one cohesive app** — not 4 separate tools, but a unified workflow where Trust informs Referrals, Deserts drive planning scenarios, and Readiness flags feed back into Trust overrides.
- **2,768 → 55 specialty normalization** — a keyword engine that correctly maps obscure camelCase identifiers like `gastroenterologyAndHepatobiliarySciences` to human-readable parent specialties.
- **Zero false positives on fuzzy district matching** — verified across all 706 NFHS-5 districts against the facility data.
- **Citation engine** — every capability claim is traced back to the exact text snippet in the source data, with field attribution. Planners see *why* the system thinks a facility has ICU capability.
- **Data quality flag engine** — automatically detects 6 categories of suspicious records (future dates, out-of-India coordinates, capability/equipment mismatch, etc.) without manual rules.

---

## What We Learned

- **Data quality problems are domain problems, not engineering problems.** You can't fix the AP → Telangana split with a regex — you need to understand Indian political geography and make judgment calls about what "correct" even means for a facility that was in AP when it registered but is physically in Telangana today.
- **Uncertainty is a feature, not a bug.** Users trust a system more when it says "I'm not sure — here's why" than when it confidently shows a number it can't justify.
- **Self-reported data should be treated as claims, not facts.** The moment we stopped calling `capability` a "feature" and started calling it a "claim," the entire UX design became clearer.
- **Fuzzy matching needs guardrails.** A 0.80 cutoff gives you false positives on Indian district names (e.g., "Pune" matching "Puri"). 0.85 is the sweet spot — empirically verified.
- **Lakebase + FastAPI is a very productive stack** for hackathons — Postgres familiarity with Databricks governance and zero infrastructure management.

---

## What's Next for Lumen Healthcare Planner

- **District-level geocoding** — Use pincode centroids to re-assign facilities to their correct post-split state, resolving the AP/Telangana and Bihar/Jharkhand attribution problems
- **Crowd-sourced verification** — Let field workers confirm or deny facility claims via mobile, building a ground-truth layer over time
- **NFHS-6 integration** — When the next National Family Health Survey drops, auto-update the desert confidence labels
- **Multi-language support** — Hindi, Telugu, Tamil, Marathi interfaces for grassroots health workers
- **ML-based trust scoring** — Train on the overrides that planners have already submitted to improve the heuristic scoring model
- **Real-time data feeds** — Connect to government health portals (NHA, ABDM) for live bed availability and doctor rosters
- **Offline mode** — PWA with local caching for field workers in low-connectivity rural areas
- **Policy simulation** — "What if we add 5 facilities to this desert district?" scenario modeling with projected impact on health outcomes

---

## Why We Built This

India's healthcare data is **fragmented, inconsistent, and riddled with quality issues**. Policymakers, NGO coordinators, and healthcare planners face a critical challenge: *they cannot trust the data they have, and they cannot see the gaps they're missing.*

Consider the scale of the problem:

- **10,088 healthcare facilities** across India, collected from heterogeneous sources
- **255 raw state name variants** that needed normalization to 35 canonical states
- **Critical fields like doctor count (36%) and bed capacity (25%) are largely missing**
- **JSON arrays stored as strings** for capabilities, procedures, and equipment — making analysis nearly impossible without parsing
- **State separation artifacts** — when Andhra Pradesh split into Telangana (2014), records were never properly re-assigned. Facilities physically in Telangana still carry "Andhra Pradesh" as their state, creating phantom coverage in one region and invisible gaps in another. Similar issues exist for Jharkhand/Bihar, Uttarakhand/UP, and Chhattisgarh/MP splits.
- **Conflicting claims** — clinics and dispensaries claiming ICU and trauma capabilities with no supporting equipment data
- **No ground truth** — facility capability fields are self-reported claims, not verified facts

We built the Lumen Healthcare Planner to **make this messy reality navigable** — not by hiding the problems, but by surfacing them transparently with citations, confidence levels, and uncertainty signals at every step.

---

## What This App Achieves

A single Databricks App covering **all 4 hackathon tracks** for a non-technical healthcare planner:

### Track 1: Facility Trust Desk
> *"Can this facility actually do what it claims?"*

- Select a **capability** (ICU, Maternity, Emergency, Oncology, Trauma, NICU, Dialysis, etc.) and a **region**
- See facilities ranked by a composite **trust score** (completeness 40% + verification 35% + recency 25%)
- Each claim is evaluated as **Strong / Partial / Weak / No Evidence** based on corroboration across description, capability, procedure, equipment, and source URL fields
- **Every assessment cites its source text** — the exact snippet from the data that supports or contradicts the claim
- Users can **override assessments** with a note explaining their reasoning (persisted to Lakebase)

### Track 2: Medical Desert Planner
> *"Where are the highest-risk care gaps?"*

- Identify **medical deserts** — districts with critically few facilities for a given capability
- Cross-reference facility density with **NFHS-5 district health indicators** (706 districts) to distinguish:
  - **Confirmed gaps** — low facility count AND poor health outcomes (institutional births < 60%)
  - **Possible gaps** — low facility count but acceptable outcomes
  - **Data-limited** — zero facilities found, but may reflect missing data rather than confirmed absence
- Interactive **map visualization** (Leaflet.js) with severity-coded markers
- Save **planning scenarios** for comparison

### Track 3: Referral Copilot
> *"Where should this patient go?"*

- Enter a medical need (specialty + procedure) and optional patient location
- Get a **ranked shortlist** scored by: relevance (35%) + trust (30%) + proximity (20%) + capacity (15%)
- Each recommendation includes:
  - **Citations** — which text fields mention the specialty
  - **Missing evidence flags** — what data is absent (no equipment listed, no source URL, very short description)
  - **Match reasons** — human-readable explanation of why this facility was ranked here
- Haversine distance calculation for proximity scoring
- **Save facilities to a referral shortlist** for later review

### Track 4: Data Readiness Desk
> *"What needs fixing before this data can be trusted?"*

- **Full dataset profiling** — coverage percentages for all 21 key fields
- **State-by-state completeness** — see which states have the worst data quality
- **Completeness by organization type** — hospitals vs clinics vs dispensaries
- **Flagged record queue** with automatic detection of:
  - Claims high-acuity care but description < 80 characters
  - Year established in the future or before 1900
  - Coordinates outside India's bounding box
  - Clinic/dispensary names claiming ICU/Trauma/NICU capabilities
  - 12+ capability items but zero equipment data (likely copy-paste)
- **Reviewer decisions persisted** — approve, reject, or flag for follow-up

---

## The Data Quality Challenge

### State Separation Problem

India has undergone several state bifurcations that the source data never properly reflected:

| Year | Parent State | New State | Impact |
| --- | --- | --- | --- |
| 2000 | Bihar | Jharkhand | Facilities in Jharkhand districts still tagged "Bihar" |
| 2000 | Uttar Pradesh | Uttarakhand | Hill-district facilities misattributed to UP |
| 2000 | Madhya Pradesh | Chhattisgarh | Eastern MP facilities belong to Chhattisgarh |
| 2014 | Andhra Pradesh | Telangana | Hyderabad-area facilities still listed under AP |

This creates **two simultaneous problems**:
1. **Phantom coverage** — the parent state appears to have more facilities than it actually does
2. **Invisible deserts** — the new state shows fewer facilities than physically exist there

Our ETL pipeline added a `state_normalized` column (255 raw variants → 35 canonical states) but cannot fully resolve geographic misattribution without manual district-level re-mapping. The app communicates this uncertainty explicitly in Track 2 (Desert Planner) through confidence labels.

### Other Data Quality Issues

- **Specialty encoding** — 2,768 raw specialty labels (camelCase identifiers like `gastroenterologyAndHepatobiliarySciences`) normalized to 55 canonical specialties via keyword matching
- **Sparse critical fields** — `numberDoctors` (36%), `capacity` (25%), `yearEstablished` (48%) are mostly empty
- **JSON-in-strings** — `capability`, `procedure`, `equipment`, `specialties` are JSON arrays stored as TEXT columns, requiring runtime parsing
- **Self-reported claims** — no verification against any ground truth; the app treats these as *claims* not *facts*
- **NFHS-5 join complexity** — district names don't match exactly across datasets; we use fuzzy matching (difflib, cutoff 0.85) proven to have zero false positives
- **Pincode table grain** — `india_post_pincode_directory` (165,627 rows) is at post-office level, not pincode level — requires deduplication before joins

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    Databricks App (FastAPI)                       │
│                                                                   │
│  app.py ─── routes_trust.py ─── routes_deserts.py               │
│          ─── routes_referral.py ─── routes_readiness.py          │
│          ─── routes_persistence.py                               │
│          ─── scoring.py (trust engine)                           │
│          ─── db.py (Lakebase connector + token refresh)          │
│                                                                   │
│  static/ ─── index.html (SPA) ─── js/app.js ─── css/styles.css │
└──────────────────────────────┬────────────────────────────────────┘
                               │ psycopg2 + OAuth token
                               ▼
┌─────────────────────────────────────────────────────────────────┐
│              Lakebase (Postgres-compatible)                       │
│              Instance: hackathon-healthcare                       │
│                                                                   │
│  Schema: lakebase_pg_sync (READ)                                │
│    ├── facilities_full          (10,088 rows, 51 columns)        │
│    ├── india_post_pincode_directory  (165,627 rows)              │
│    └── nfhs_5_district_health_indicators (706 rows)              │
│                                                                   │
│  Schema: app_data (READ + WRITE)                                │
│    ├── user_notes              │  trust_scores                   │
│    ├── user_overrides          │  trust_overrides                │
│    ├── shortlists              │  review_decisions               │
│    └── scenarios                                                 │
└─────────────────────────────────────────────────────────────────┘
                               ▲
                               │ Synced from Unity Catalog
                               │
┌─────────────────────────────────────────────────────────────────┐
│              Unity Catalog (dais2026)                             │
│              Source: Virtue Foundation Dataset                    │
│                                                                   │
│  dais2026.healthcare.facilities (CDF-enabled)                    │
│  dais2026.healthcare.india_post_pincode_directory                │
│  dais2026.healthcare.nfhs_5_district_health_indicators           │
└─────────────────────────────────────────────────────────────────┘
```

---

## Tech Stack

| Layer | Technology |
| --- | --- |
| App Framework | FastAPI (Python) |
| Database | Databricks Lakebase (Postgres-compatible) |
| Auth | Databricks SDK OAuth token (auto-refreshed every 15 min) |
| Data Catalog | Unity Catalog (Databricks) |
| Frontend | Tailwind CSS + Leaflet.js maps |
| Deployment | Databricks Apps |
| Design | Databricks brand palette (#FF3621, #0B2026, #EEEDE9, #F9F7F4) |

---

## Trust Scoring Algorithm

Each facility receives a composite trust score (0.0 – 1.0) computed from three dimensions:

**Completeness (40% weight)**
- Critical fields (name, city, state, coordinates, org type, specialties, ID): 50% of completeness
- Important fields (description, phone, capability, procedure, equipment, capacity, doctors): 35%
- Nice-to-have fields (email, websites, year established, social links): 15%

**Verification (35% weight)**
- Source URLs present (+1.0)
- Description length > 200 chars (+1.0) or > 50 chars (+0.5)
- Rich structured data — combined capability + procedure + equipment items / 10 (capped at 1.0)
- Multiple contact methods — phone, email, websites, official phone (/ 3, capped at 1.0)

**Recency (25% weight)**
- Established ≥ 2015: 1.0
- Established ≥ 2000: 0.8
- Established ≥ 1990: 0.6
- Established < 1990: 0.4
- Unknown: 0.3

---

## API Endpoints

### Overview & Filters
- `GET /api/health` — Health check + DB connectivity
- `GET /api/overview` — KPI dashboard (total facilities, states, districts, specialties)
- `GET /api/filters/states` — States list with facility counts (filterable by capability)
- `GET /api/filters/districts` — Districts within state(s)
- `GET /api/filters/cities` — Cities within district/state

### Track 1: Trust
- `GET /api/trust/capabilities` — Available capabilities for evaluation
- `GET /api/trust/scores?capability=ICU&state=MAHARASHTRA` — Ranked facilities with trust signals + citations
- `POST /api/trust/override/{facility_id}` — Save user override with note

### Track 2: Deserts
- `GET /api/deserts/analysis?state=BIHAR&capability=Emergency` — Desert districts with severity + confidence
- `GET /api/deserts/facilities?state=BIHAR&district=Patna` — Drill into facilities in a desert area

### Track 3: Referral
- `GET /api/referral/search?specialty=cardiology&state=KARNATAKA` — Ranked recommendations with citations
- `POST /api/referral/shortlist/{facility_id}` — Save to referral shortlist
- `DELETE /api/referral/shortlist/{facility_id}` — Remove from shortlist

### Track 4: Readiness
- `GET /api/readiness/profile` — Field-level coverage percentages
- `GET /api/readiness/state-summary` — Completeness breakdown by state
- `GET /api/readiness/completeness-by-type` — Completeness by organization type
- `GET /api/readiness/gaps?field=numberDoctors` — Sample facilities missing a field
- `GET /api/readiness/flags` — Facilities with suspicious data quality issues
- `POST /api/readiness/review/{facility_id}` — Submit reviewer decision

### Persistence
- `POST /api/notes` — Save a note on any facility
- `POST /api/shortlist` — Save facility to a track-specific shortlist
- `POST /api/scenarios` — Save a planning scenario

---

## Design Philosophy

1. **Transparency over polish** — Every claim shows its evidence. Every gap is labeled. No score exists without an explanation.
2. **Uncertainty is a feature** — When data is missing or conflicting, the app says so explicitly rather than guessing.
3. **Citations, not conclusions** — The app surfaces source text so human planners can make informed decisions.
4. **Non-technical users first** — Designed for healthcare planners and NGO coordinators, not data engineers.
5. **Persistence enables workflow** — Notes, overrides, shortlists, and scenarios are saved to Lakebase so planners can build on their work across sessions.

---

## Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Set environment variables
export PGHOST=ep-noisy-wave-d2hhvbvx.database.us-east-1.cloud.databricks.com
export PGPORT=5432
export PGUSER=your-email@domain.com

# Run the app
uvicorn app:app --reload --port 8000
```

---

## Deployment

Deployed as a **Databricks App** via `app.yaml`:

```yaml
command: ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
resources:
  - name: lakebase-healthcare
    lakebase:
      instance: hackathon-healthcare
      permission: CAN_QUERY
```

---

## Dataset Attribution

- **Primary dataset**: [Virtue Foundation Healthcare Dataset (DAIS 2026)](https://marketplace.databricks.com) — 10,088 Indian healthcare facility records
- **Supplemental**: India Post Pincode Directory (165,627 records), NFHS-5 District Health Indicators (706 districts)
- **Source catalog**: `databricks_virtue_foundation_dataset_dais_2026.virtue_foundation_dataset`

---

## Hackathon

**Event**: Databricks Apps & Agents for Good 2026 (in partnership with OpenAI)  
**Project Period**: June 15–16, 2026  
**Tracks Covered**: All 4 (Trust, Deserts, Referral, Readiness)  
**Team**: Lumen (Lumenalta)

---

## License

This project is open-source. See [LICENSE](LICENSE) for details.
