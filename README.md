# Lumen Healthcare Planner

**An intelligent healthcare infrastructure planning tool for India — built for the DAIS 2026 Apps & Agents for Good Hackathon**

[![Built on Databricks](https://img.shields.io/badge/Built%20on-Databricks-FF3621)](https://databricks.com)
[![Powered by Lakebase](https://img.shields.io/badge/Powered%20by-Lakebase-0B2026)](https://databricks.com)
[![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

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
