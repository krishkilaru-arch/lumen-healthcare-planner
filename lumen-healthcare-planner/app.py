"""Lumen Healthcare Planner - Main Application."""

import logging
import os
import re

from fastapi import FastAPI, Request, Query
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from typing import List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Lumen Healthcare Planner",
    description="Healthcare intelligence - Trust, Deserts, Referrals, Readiness",
    version="1.0.0",
)

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Return error details as JSON instead of generic 500."""
    import traceback
    return JSONResponse(status_code=500, content={
        "error": str(exc),
        "path": str(request.url.path),
        "trace": traceback.format_exc()[-300:]
    })


# Register routers at module level (before catch-all)
from routes_trust import router as trust_router
from routes_deserts import router as deserts_router
from routes_referral import router as referral_router
from routes_readiness import router as readiness_router
from routes_persistence import router as persistence_router
app.include_router(trust_router)
app.include_router(deserts_router)
app.include_router(referral_router)
app.include_router(readiness_router)
app.include_router(persistence_router)
logger.info("All route modules registered")


@app.on_event("startup")
async def startup():
    """Initialize on startup."""
    logger.info(f"Starting Lumen Healthcare Planner...")
    logger.info(f"PGHOST={os.environ.get('PGHOST', 'NOT SET')}")
    logger.info(f"PGDATABASE={os.environ.get('PGDATABASE', 'NOT SET')}")
    logger.info(f"PGUSER={os.environ.get('PGUSER', 'NOT SET')}")
    try:
        from db import init_app_schema
        init_app_schema()
        logger.info("App schema initialized")
    except Exception as e:
        logger.warning(f"DB init deferred: {e}")


# ---------------------------------------------------------------------------
# Specialty normalisation — tested against live data (2,768 raw labels → 55 canonical)
# ---------------------------------------------------------------------------

def _camel_to_words(s: str) -> str:
    spaced = re.sub(r'([A-Z])', r' \1', s).strip()
    return spaced.title()

# Keyword (lowercase substring) → canonical parent specialty
# Ordered: longer / more specific keys first to avoid partial-match shadowing
_CANONICAL_KW = [
    ('cardiothoracic',          'Cardiac Surgery'),
    ('cardiac surgery',         'Cardiac Surgery'),
    ('cardiac surg',            'Cardiac Surgery'),
    ('cardiology',              'Cardiology'),
    ('cardiac',                 'Cardiology'),
    ('interventional cardiology','Cardiology'),
    ('neurosurgery',            'Neurosurgery'),
    ('neuro surg',              'Neurosurgery'),
    ('brain surg',              'Neurosurgery'),
    ('skull base',              'Neurosurgery'),
    ('cranio',                  'Neurosurgery'),
    ('neurolog',                'Neurology'),
    ('headache',                'Neurology'),
    ('epilepsy',                'Neurology'),
    ('spine surg',              'Orthopaedics'),
    ('joint replacement',       'Orthopaedics'),
    ('orthop',                  'Orthopaedics'),
    ('arthroscop',              'Orthopaedics'),
    ('sports med',              'Sports Medicine'),
    ('sport',                   'Sports Medicine'),
    ('cataract',                'Ophthalmology'),
    ('cornea',                  'Ophthalmology'),
    ('retina',                  'Ophthalmology'),
    ('vitreo',                  'Ophthalmology'),
    ('ophthal',                 'Ophthalmology'),
    ('squint',                  'Ophthalmology'),
    ('binocular',               'Ophthalmology'),
    ('gynecolog',               'Obstetrics & Gynaecology'),
    ('gynaecolog',              'Obstetrics & Gynaecology'),
    ('obstetrics',              'Obstetrics & Gynaecology'),
    ('maternity',               'Obstetrics & Gynaecology'),
    ('maternal fetal',          'Obstetrics & Gynaecology'),
    ('perinatol',               'Obstetrics & Gynaecology'),
    ('perinatal',               'Obstetrics & Gynaecology'),
    ('ivf',                     'Reproductive Medicine'),
    ('reproduct',               'Reproductive Medicine'),
    ('fertility',               'Reproductive Medicine'),
    ('family planning',         'Reproductive Medicine'),
    ('neonatal',                'Neonatology'),
    ('neonatol',                'Neonatology'),
    ('pediatric surg',          'Paediatrics'),
    ('paediatric surg',         'Paediatrics'),
    ('paediatr',                'Paediatrics'),
    ('pediatr',                 'Paediatrics'),
    ('child',                   'Paediatrics'),
    ('oncolog',                 'Oncology'),
    ('cancer',                  'Oncology'),
    ('chemotherapy',            'Oncology'),
    ('radiother',               'Oncology'),
    ('radiosurg',               'Oncology'),
    ('bone marrow',             'Haematology'),
    ('haematol',                'Haematology'),
    ('hematol',                 'Haematology'),
    ('blood',                   'Haematology'),
    ('gastroenter',             'Gastroenterology'),
    ('hepatopancreato',         'Gastroenterology'),
    ('colorectal',              'Gastroenterology'),
    ('hepatol',                 'Hepatology'),
    ('liver',                   'Hepatology'),
    ('pulmonol',                'Pulmonology'),
    ('respirat',                'Pulmonology'),
    ('thoracic',                'Pulmonology'),
    ('lung',                    'Pulmonology'),
    ('urology',                 'Urology'),
    ('urolog',                  'Urology'),
    ('nephr',                   'Nephrology'),
    ('dialysis',                'Nephrology'),
    ('kidney',                  'Nephrology'),
    ('renal',                   'Nephrology'),
    ('endocrin',                'Endocrinology'),
    ('diabetes',                'Endocrinology'),
    ('thyroid',                 'Endocrinology'),
    ('metabol',                 'Endocrinology'),
    ('cosmet',                  'Dermatology'),
    ('dermatol',                'Dermatology'),
    ('skin',                    'Dermatology'),
    ('hair and nail',           'Dermatology'),
    ('bariatric',               'Bariatric Surgery'),
    ('minimal',                 'Minimally Invasive Surgery'),
    ('laparoscop',              'General Surgery'),
    ('general surgery',         'General Surgery'),
    ('breast surg',             'General Surgery'),
    ('internal medicine',       'Internal Medicine'),
    ('general medicine',        'Internal Medicine'),
    ('family medicine',         'Internal Medicine'),
    ('community med',           'Community Medicine'),
    ('preventive',              'Preventive Medicine'),
    ('public health',           'Preventive Medicine'),
    ('otolaryngol',             'ENT'),
    ('maxillofacial',           'Oral & Maxillofacial Surgery'),
    ('oral surg',               'Oral & Maxillofacial Surgery'),
    ('ent',                     'ENT'),
    ('ear',                     'ENT'),
    ('psychiatr',               'Psychiatry'),
    ('mental health',           'Psychiatry'),
    ('psychology',              'Psychiatry'),
    ('behavioural',             'Psychiatry'),
    ('anaesthes',               'Anaesthesiology'),
    ('anesthes',                'Anaesthesiology'),
    ('anaesthesia',             'Anaesthesiology'),
    ('critical care',           'Critical Care'),
    ('intensive care',          'Critical Care'),
    ('icu',                     'Critical Care'),
    ('radiol',                  'Radiology'),
    ('imaging',                 'Radiology'),
    ('nuclear med',             'Nuclear Medicine'),
    ('pet scan',                'Nuclear Medicine'),
    ('pathol',                  'Pathology'),
    ('laborat',                 'Pathology'),
    ('microbiol',               'Pathology'),
    ('biochemistr',             'Pathology'),
    ('emergency',               'Emergency Medicine'),
    ('trauma',                  'Emergency Medicine'),
    ('casualty',                'Emergency Medicine'),
    ('accident',                'Emergency Medicine'),
    ('plastic surg',            'Plastic Surgery'),
    ('reconstruct',             'Plastic Surgery'),
    ('burn',                    'Plastic Surgery'),
    ('vascular',                'Vascular Surgery'),
    ('arterio',                 'Vascular Surgery'),
    ('transplant',              'Transplant Surgery'),
    ('rheumatol',               'Rheumatology'),
    ('arthritis',               'Rheumatology'),
    ('physiother',              'Physiotherapy'),
    ('physio',                  'Physiotherapy'),
    ('rehabil',                 'Rehabilitation'),
    ('pain med',                'Pain Management'),
    ('pain manag',              'Pain Management'),
    ('sleep med',               'Sleep Medicine'),
    ('prosthodont',             'Dentistry'),
    ('periodont',               'Dentistry'),
    ('endodont',                'Dentistry'),
    ('pedodont',                'Dentistry'),
    ('orthodont',               'Dentistry'),
    ('dental',                  'Dentistry'),
    ('dentist',                 'Dentistry'),
    ('oral med',                'Dentistry'),
    ('immunol',                 'Immunology'),
    ('allergy',                 'Immunology'),
    ('geriatric',               'Geriatrics'),
    ('elderly',                 'Geriatrics'),
    ('palliative',              'Palliative Care'),
    ('hospice',                 'Palliative Care'),
    ('infect',                  'Infectious Disease'),
    ('hiv',                     'Infectious Disease'),
    ('androl',                  'Andrology'),
    ('sexol',                   'Sexology'),
    ('podiatr',                 'Podiatry'),
    ('ayurved',                 'Ayurveda'),
    ('homoeopath',              'Homoeopathy'),
    ('homeopath',               'Homoeopathy'),
    ('naturopath',              'Naturopathy'),
]

def _normalise_spec(s: str):
    """Map any raw specialty string to a canonical parent. Returns None if unrecognised."""
    if not s or not isinstance(s, str):
        return None
    # Convert camelCase to words first, then lowercase for matching
    readable = _camel_to_words(s.strip())
    ll = readable.lower()
    for kw, parent in _CANONICAL_KW:
        if kw in ll:
            return parent
    return None  # unrecognised — excluded from count

# Legacy dict kept for routes that still reference _SPEC_PARENTS
_SPEC_PARENTS = {
    'gastroenterology':'Gastroenterology','hepatology':'Hepatology',
    'colorectalSurgery':'Gastroenterology',
    'gastroenterologyAndHepatobiliarySciences':'Gastroenterology',
    'pulmonology':'Pulmonology','respiratoryMedicine':'Pulmonology','thoracicSurgery':'Pulmonology',
    'generalSurgery':'General Surgery','laparoscopy':'General Surgery',
    'bariatricSurgery':'General Surgery','minimallyInvasiveSurgery':'General Surgery',
    'internalMedicine':'Internal Medicine','familyMedicine':'Internal Medicine',
    'generalMedicine':'Internal Medicine','communityMedicine':'Internal Medicine',
    'obstetrics':'Obstetrics & Gynaecology','gynecology':'Obstetrics & Gynaecology',
    'obstetricsAndGynecology':'Obstetrics & Gynaecology',
    'foetalMedicine':'Obstetrics & Gynaecology',
    'familyPlanningAndComplexContraception':'Obstetrics & Gynaecology',
    'pediatrics':'Paediatrics','neonatal':'Paediatrics',
    'paediatricIntensiveCare':'Paediatrics','pediatricSurgery':'Paediatrics',
    'dermatology':'Dermatology','cosmeticDermatology':'Dermatology',
    'urology':'Urology','nephrology':'Nephrology','dialysis':'Nephrology',
    'otolaryngology':'ENT','ent':'ENT','headAndNeckSurgery':'ENT',
    'psychiatry':'Psychiatry','mentalHealth':'Psychiatry','behavioralHealth':'Psychiatry',
    'anesthesia':'Anaesthesiology','anesthesiology':'Anaesthesiology',
    'criticalCareMedicine':'Critical Care','intensiveCare':'Critical Care',
    'emergencyMedicine':'Emergency Medicine','trauma':'Emergency Medicine',
    'radiology':'Radiology','diagnosticRadiology':'Radiology','interventionalRadiology':'Radiology',
    'pathology':'Pathology','laboratoryMedicine':'Pathology',
    'physiotherapy':'Physiotherapy','rehabilitation':'Physiotherapy',
    'dentistry':'Dentistry','endodontics':'Dentistry','orthodontics':'Dentistry',
    'aestheticDentistry':'Dentistry','periodontology':'Dentistry',
    'plasticSurgery':'Plastic Surgery','breastSurgery':'Plastic Surgery',
    'burnAndTraumaPlasticSurgery':'Plastic Surgery',
    'endocrinology':'Endocrinology','endocrinologyAndDiabetesAndMetabolism':'Endocrinology',
    'rheumatology':'Rheumatology','immunology':'Immunology',
    'geriatrics':'Geriatrics','palliativeCare':'Palliative Care',
    'infectiousDisease':'Infectious Disease','vascularSurgery':'Vascular Surgery',
    'transplantSurgery':'Transplant Surgery',
}
_SM_SUBSTR = {k: v for k, v in _SPEC_PARENTS.items() if len(k) > 4}

def _normalise_spec(s: str) -> str:
    """Map camelCase specialty to a known parent category.
    Returns None for unrecognised sub-specialties so they are excluded from counts.
    """
    if not s or not isinstance(s, str):
        return None
    if s in _SPEC_PARENTS:
        return _SPEC_PARENTS[s]
    sl = s.lower()
    for k, v in _SM_SUBSTR.items():
        if k.lower() in sl:
            return v
    return None   # unrecognised → exclude from count (not a fallback guess)


# ---------------------------------------------------------------------------
# Overview
# ---------------------------------------------------------------------------

@app.get("/api/overview")
async def overview_stats():
    """Dashboard metrics."""
    try:
        from db import query, SYNCED_SCHEMA
        from scoring import safe_json_parse
        total     = query(f'SELECT COUNT(*) as cnt FROM {SYNCED_SCHEMA}.facilities_full')
        states    = query(f"SELECT COUNT(DISTINCT state_normalized) as cnt FROM {SYNCED_SCHEMA}.facilities_full WHERE state_normalized IS NOT NULL")
        districts = query(f"SELECT COUNT(DISTINCT address_city) as cnt FROM {SYNCED_SCHEMA}.facilities_full WHERE address_city IS NOT NULL")
        specs_raw = query(f"SELECT specialties FROM {SYNCED_SCHEMA}.facilities_full WHERE specialties IS NOT NULL AND specialties != '[]'")
        all_specs = set()
        for r in specs_raw:
            for s in safe_json_parse(r['specialties']):
                norm = _normalise_spec(s)
                if norm:
                    all_specs.add(norm)
        return {
            "total_facilities": total[0]["cnt"] if total else 0,
            "total_states":     states[0]["cnt"] if states else 0,
            "total_districts":  districts[0]["cnt"] if districts else 0,
            "total_specialties": len(all_specs),
        }
    except Exception as e:
        import traceback
        return {"error": str(e), "trace": traceback.format_exc()[-500:]}


# ---------------------------------------------------------------------------
# Cascading filters  State → District → City
# ---------------------------------------------------------------------------

def _capability_where(capability: str) -> tuple:
    """Return (sql_fragment, params) for a capability keyword search.
    Accepts comma-separated capabilities — results use OR logic across all.
    """
    try:
        from routes_trust import CAPABILITY_KEYWORDS
        caps     = [c.strip() for c in capability.split(',') if c.strip()]
        keywords = []
        for cap in caps:
            for kw in CAPABILITY_KEYWORDS.get(cap, [cap.lower()])[:3]:
                if kw not in keywords:
                    keywords.append(kw)
    except Exception:
        keywords = [capability.lower()]

    kw_conditions, params = [], []
    for kw in keywords[:9]:   # up to 3 per capability, OR across all
        kw_conditions.append(
            "(LOWER(COALESCE(description,'')) || ' ' || LOWER(COALESCE(capability,'')) || ' ' "
            "|| LOWER(COALESCE(procedure,'')) || ' ' || LOWER(COALESCE(specialties,''))) ILIKE %s"
        )
        params.append(f'%{kw}%')
    fragment = '(' + ' OR '.join(kw_conditions) + ')' if kw_conditions else 'TRUE'
    return fragment, params


@app.get("/api/filters/states")
async def filter_states(capability: str = Query(None), procedure: str = Query(None)):
    """States with facility counts, alphabetical.
    Counts only facilities matching capability AND/OR procedure when given.
    """
    from db import query, SYNCED_SCHEMA

    where_parts, params = ["state_normalized IS NOT NULL"], []
    if capability:
        cap_sql, cap_params = _capability_where(capability)
        where_parts.append(cap_sql)
        params.extend(cap_params)
    if procedure:
        where_parts.append("procedure ILIKE %s")
        params.append(f"%{procedure}%")

    where_sql = 'WHERE ' + ' AND '.join(where_parts)
    rows = query(f"""
        SELECT state_normalized AS name,
               state_normalized AS value,
               COUNT(*)         AS count
        FROM {SYNCED_SCHEMA}.facilities_full
        {where_sql}
        GROUP BY state_normalized
        ORDER BY state_normalized ASC
    """, tuple(params))
    return {'states': rows}


@app.get("/api/filters/districts")
async def filter_districts(
    state:      str = Query(None),
    capability: str = Query(None),
    procedure:  str = Query(None),
):
    """Districts in a state, alphabetical.
    Counts only facilities matching capability AND/OR procedure when given.
    """
    from db import query, SYNCED_SCHEMA
    if not state:
        return {'districts': []}

    state_list   = [s.strip().upper() for s in state.split(',')]
    placeholders = ','.join(['%s'] * len(state_list))
    where_parts  = [
        f'UPPER(state_normalized) IN ({placeholders})',
        'address_city IS NOT NULL',
    ]
    params = list(state_list)

    if capability:
        cap_sql, cap_params = _capability_where(capability)
        where_parts.append(cap_sql)
        params.extend(cap_params)
    if procedure:
        where_parts.append("procedure ILIKE %s")
        params.append(f"%{procedure}%")

    where_sql = 'WHERE ' + ' AND '.join(where_parts)
    rows = query(f"""
        SELECT address_city AS name,
               address_city AS value,
               COUNT(*)     AS count
        FROM {SYNCED_SCHEMA}.facilities_full
        {where_sql}
        GROUP BY address_city
        ORDER BY address_city ASC
    """, tuple(params))
    return {'districts': rows}


@app.get("/api/filters/cities")
async def filter_cities(
    state:      str = Query(None),
    district:   str = Query(None),
    capability: str = Query(None),
    procedure:  str = Query(None),
):
    """Cities scoped to the selected district (or state if no district given).
    Counts only facilities matching capability AND/OR procedure when given.
    """
    from db import query, SYNCED_SCHEMA
    if not state and not district:
        return {'cities': []}

    where_parts = []
    params      = []

    if district:
        where_parts.append('address_city = %s')
        params.append(district)
    elif state:
        state_list   = [s.strip().upper() for s in state.split(',')]
        placeholders = ','.join(['%s'] * len(state_list))
        where_parts.append(f'UPPER(state_normalized) IN ({placeholders})')
        params.extend(state_list)

    if capability:
        cap_sql, cap_params = _capability_where(capability)
        where_parts.append(cap_sql)
        params.extend(cap_params)
    if procedure:
        where_parts.append("procedure ILIKE %s")
        params.append(f"%{procedure}%")
    where_parts.append('address_city IS NOT NULL')
    where_parts.append("address_city != ''")
    where_sql = 'WHERE ' + ' AND '.join(where_parts)

    rows = query(f"""
        SELECT address_city AS name, COUNT(*) AS count
        FROM {SYNCED_SCHEMA}.facilities_full
        {where_sql}
        GROUP BY address_city
        ORDER BY address_city ASC
    """, tuple(params))
    return {'cities': rows}


@app.get("/api/health")
async def health_check():
    try:
        from db import query
        query("SELECT 1 as ok")
        return {"status": "healthy", "db": "connected"}
    except Exception as e:
        return {"status": "starting", "db": str(e)}


# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/{path:path}")
async def serve_spa(path: str):
    """Serve the SPA for all non-API routes (catch-all, registered last)."""
    if path.startswith("api/"):
        return {"error": "Not found", "path": path}
    return FileResponse("static/index.html")
